from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from memory_store import append_sources, load_memory_sources, save_daily_result, source_from_text
from prepare_daily_context import prepare_context
from ingest_memory import feishu_source_kind


def test_skill_owned_memory_store_dedupes_and_prepares_context(tmp_path: Path) -> None:
    home = tmp_path / "memory"
    source = source_from_text("参赛记录", "待办：写一版本地工作记忆 Skill 演示。", "note", "2026-06-08")

    first = append_sources([source], home)
    second = append_sources([source], home)
    sources = load_memory_sources(home)
    context = prepare_context(memory_home=home, date="2026-06-08")

    assert first["added"] == 1
    assert second["skipped"] == 1
    assert len(sources) == 1
    assert "参赛记录" in context
    assert "agent-owned-local-memory" in context


def test_save_daily_result_writes_validated_result(tmp_path: Path) -> None:
    result = {
        "requestId": "daily-test",
        "summary": "ok",
        "themes": [],
        "ideas": [],
        "tasks": [],
        "taskReferences": [],
        "schedule": [],
        "defer": [],
        "links": [],
        "dailySynthesis": [],
        "kindleCard": {"title": "ok", "body": "ok"},
    }

    path = save_daily_result(result, "2026-06-08", tmp_path)

    assert path.exists()
    assert json.loads(path.read_text(encoding="utf-8"))["requestId"] == "daily-test"


def test_feishu_kind_maps_calendar_and_task_to_structured_sources() -> None:
    assert feishu_source_kind("calendar") == "schedule"
    assert feishu_source_kind("task") == "task"
    assert feishu_source_kind("document") == "feishu-document"
