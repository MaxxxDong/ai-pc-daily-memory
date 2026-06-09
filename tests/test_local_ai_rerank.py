from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import local_ai_rerank
from memory_store import append_sources, source_from_text


def test_token_backend_reranks_memory_sources(tmp_path: Path) -> None:
    memory_home = tmp_path / ".memory"
    append_sources(
        [
            source_from_text("产品例会", "讨论 AI PC Skill 今日提交和演示材料。", "note", "2026-06-09"),
            source_from_text("做饭记录", "晚上买菜和准备晚饭。", "note", "2026-06-09"),
        ],
        memory_home,
    )

    result = local_ai_rerank.rerank_memory_sources(
        memory_home=memory_home,
        query="AI PC Skill 提交",
        backend="token",
        top_k=1,
    )

    assert result["backend"] == "token"
    assert result["localOnly"] is True
    assert result["results"][0]["title"] == "产品例会"


def test_embedding_endpoint_requires_localhost() -> None:
    with pytest.raises(ValueError, match="localhost"):
        local_ai_rerank.validate_local_endpoint("https://api.example.com/v1/embeddings")
