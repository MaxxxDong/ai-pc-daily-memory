from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from memory_store import load_memory_sources, resolve_memory_home
from rag_retriever import retrieve_context
from wiki_store import load_wiki_items


WIKI_ITEM_SCHEMA = {
    "items": [
        {
            "kind": "topic | claim | entity | workflow | decision | task-pattern",
            "title": "string",
            "summary": "string",
            "sourceId": "string",
            "sourceTitle": "string",
            "sourceDate": "string",
            "tags": ["string"],
            "related": ["string"],
        }
    ]
}


def prepare_wiki_context(
    memory_home: str | Path | None = None,
    date: str = "",
    objective: str = "Extract durable LLM WIKI knowledge from local work memory.",
    top_k: int = 12,
) -> str:
    sources = load_memory_sources(resolve_memory_home(memory_home))
    if date:
        sources = [source for source in sources if not source.source_date or source.source_date.startswith(date)]
    existing = load_wiki_items(memory_home)
    query = "\n".join([objective, date, *(item.title for item in existing[:20])])
    retrieved = retrieve_context(query, sources, limit=top_k)
    blocks = [
        "# LLM WIKI Extraction Context",
        "",
        "Extract only durable, reusable knowledge items. Do not copy raw logs, empty notes, timestamps, or low-value fragments.",
        "",
        "## Output Shape",
        "",
        json.dumps(WIKI_ITEM_SCHEMA, ensure_ascii=False, indent=2),
        "",
        "## Rules",
        "",
        "- Keep personal work-memory, decisions, recurring task patterns, workflows, and useful concepts.",
        "- Reject trivial timestamps, one-off noise, empty notes, duplicated phrasing, and raw source markers.",
        "- Do not create wiki items for ordinary task lines unless the task reveals a reusable workflow or decision.",
        "- Reuse existing item titles when a new source supports the same concept instead of creating near-duplicates.",
        "",
        "## Existing Accepted LLM WIKI Items",
    ]
    for item in existing[:30]:
        blocks.extend(["", f"- [{item.kind}] {item.title}: {item.summary}"])
    blocks.extend(["", "## Retrieved Local Sources"])
    for index, source in enumerate(retrieved, start=1):
        blocks.extend(["", f"<!-- source {index} -->", source.prompt_block()])
    return "\n".join(blocks).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare local context for LLM WIKI extraction by the calling agent.")
    parser.add_argument("--output", required=True, help="Markdown context output path.")
    parser.add_argument("--memory-home", help="Local memory store directory.")
    parser.add_argument("--date", default="", help="Optional source date filter.")
    parser.add_argument("--objective", default="Extract durable LLM WIKI knowledge from local work memory.")
    parser.add_argument("--top-k", type=int, default=12)
    args = parser.parse_args()

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        prepare_wiki_context(args.memory_home, date=args.date, objective=args.objective, top_k=args.top_k),
        encoding="utf-8",
    )
    print(f"OK: wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
