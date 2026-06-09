from __future__ import annotations

import argparse
import json
import math
import sys
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from memory_store import load_memory_sources
from rag_retriever import retrieve_context, tokenize
from source_loader import SourceItem


LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def validate_local_endpoint(endpoint: str) -> None:
    parsed = urlparse(endpoint)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in LOCAL_HOSTS:
        raise ValueError("embedding endpoint must be localhost, 127.0.0.1, or ::1")


def cosine(left: list[float], right: list[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if not left_norm or not right_norm:
        return 0.0
    return numerator / (left_norm * right_norm)


def token_vector(text: str) -> dict[str, float]:
    vector: dict[str, float] = {}
    for token in tokenize(text):
        vector[token] = vector.get(token, 0.0) + 1.0
    return vector


def sparse_cosine(left: dict[str, float], right: dict[str, float]) -> float:
    keys = set(left).intersection(right)
    numerator = sum(left[key] * right[key] for key in keys)
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    if not left_norm or not right_norm:
        return 0.0
    return numerator / (left_norm * right_norm)


def token_rerank(query: str, sources: list[SourceItem], top_k: int) -> list[tuple[float, SourceItem]]:
    query_vector = token_vector(query)
    scored = [(sparse_cosine(query_vector, token_vector(source.text)), source) for source in sources]
    scored = [item for item in scored if item[0] > 0]
    if not scored:
        scored = [(1.0 / (index + 1), source) for index, source in enumerate(retrieve_context(query, sources, limit=top_k))]
    return sorted(scored, key=lambda item: item[0], reverse=True)[:top_k]


def localhost_embeddings(endpoint: str, model: str, texts: list[str]) -> list[list[float]]:
    validate_local_endpoint(endpoint)
    payload: dict[str, Any] = {"model": model, "input": texts}
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        value = json.loads(response.read().decode("utf-8"))
    if isinstance(value, dict) and isinstance(value.get("data"), list):
        return [list(map(float, item["embedding"])) for item in value["data"]]
    if isinstance(value, dict) and isinstance(value.get("embeddings"), list):
        return [list(map(float, item)) for item in value["embeddings"]]
    if isinstance(value, dict) and isinstance(value.get("embedding"), list):
        return [list(map(float, value["embedding"]))]
    raise RuntimeError("localhost embedding endpoint returned an unsupported shape")


def openvino_embeddings(model_path: str, texts: list[str]) -> list[list[float]]:
    path = Path(model_path).expanduser().resolve()
    if not path.exists():
        raise ValueError(f"OpenVINO model path does not exist: {path}")
    try:
        import numpy as np
        from transformers import AutoTokenizer
        from optimum.intel.openvino import OVModelForFeatureExtraction
    except ImportError as exc:
        raise RuntimeError("OpenVINO backend requires optimum-intel, openvino, transformers, and numpy installed locally") from exc

    tokenizer = AutoTokenizer.from_pretrained(path, local_files_only=True)
    model = OVModelForFeatureExtraction.from_pretrained(path, local_files_only=True)
    encoded = tokenizer(texts, padding=True, truncation=True, return_tensors="np")
    outputs = model(**encoded)
    hidden = outputs.last_hidden_state
    mask = encoded["attention_mask"][..., None]
    pooled = (hidden * mask).sum(axis=1) / np.maximum(mask.sum(axis=1), 1)
    norms = np.linalg.norm(pooled, axis=1, keepdims=True)
    pooled = pooled / np.maximum(norms, 1e-12)
    return pooled.astype(float).tolist()


def embedding_rerank(query: str, sources: list[SourceItem], top_k: int, backend: str, endpoint: str = "", model: str = "") -> list[tuple[float, SourceItem]]:
    texts = [query, *(source.text for source in sources)]
    if backend == "localhost-embeddings":
        embeddings = localhost_embeddings(endpoint, model, texts)
    elif backend == "openvino":
        embeddings = openvino_embeddings(model, texts)
    else:
        raise ValueError(f"unsupported embedding backend: {backend}")
    if len(embeddings) != len(texts):
        raise RuntimeError("embedding count does not match input count")
    query_embedding = embeddings[0]
    scored = [(cosine(query_embedding, embedding), source) for embedding, source in zip(embeddings[1:], sources)]
    return sorted(scored, key=lambda item: item[0], reverse=True)[:top_k]


def result_record(score: float, source: SourceItem) -> dict[str, Any]:
    return {
        "score": round(float(score), 6),
        "id": source.id,
        "title": source.title,
        "sourceKind": source.source_kind,
        "sourceDate": source.source_date,
        "path": source.path,
        "url": source.url,
    }


def rerank_memory_sources(
    memory_home: str | Path,
    query: str,
    backend: str = "token",
    top_k: int = 8,
    endpoint: str = "http://localhost:11434/v1/embeddings",
    model: str = "",
) -> dict[str, Any]:
    sources = load_memory_sources(memory_home)
    if backend == "token":
        scored = token_rerank(query, sources, top_k)
    else:
        scored = embedding_rerank(query, sources, top_k, backend=backend, endpoint=endpoint, model=model)
    return {
        "backend": backend,
        "localOnly": True,
        "query": query,
        "sourceCount": len(sources),
        "results": [result_record(score, source) for score, source in scored],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run local-only semantic rerank over skill-owned work memory sources.")
    parser.add_argument("--memory-home", default=".aipc-work-memory", help="Local work memory directory.")
    parser.add_argument("--query", required=True, help="Rerank query.")
    parser.add_argument("--output", required=True, help="JSON output path.")
    parser.add_argument("--backend", default="token", choices=["token", "localhost-embeddings", "openvino"], help="Local AI backend. token is deterministic for tests; use localhost/openvino for AI PC demos.")
    parser.add_argument("--endpoint", default="http://localhost:11434/v1/embeddings", help="Localhost embedding endpoint for localhost-embeddings backend.")
    parser.add_argument("--model", default="", help="Local embedding model name for localhost endpoint, or local OpenVINO model directory.")
    parser.add_argument("--top-k", type=int, default=8, help="Number of sources to return.")
    args = parser.parse_args()

    try:
        result = rerank_memory_sources(
            memory_home=args.memory_home,
            query=args.query,
            backend=args.backend,
            top_k=args.top_k,
            endpoint=args.endpoint,
            model=args.model,
        )
    except (RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK: wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
