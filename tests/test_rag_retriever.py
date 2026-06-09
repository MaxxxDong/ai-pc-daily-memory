from __future__ import annotations

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from rag_retriever import retrieve_context
from source_loader import SourceItem


def test_retrieve_context_prefers_matching_source() -> None:
    sources = [
        SourceItem(id="a", title="会议纪要", body="讨论营销排期。"),
        SourceItem(id="b", title="AIPC Skill", body="本地 RAG 每日整理和工作记忆。"),
    ]

    result = retrieve_context("本地 RAG 工作记忆", sources, limit=1)

    assert result[0].id == "b"

