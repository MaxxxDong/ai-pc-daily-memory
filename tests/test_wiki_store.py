from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from memory_store import append_sources, source_from_text
from prepare_daily_context import prepare_context
from prepare_wiki_context import prepare_wiki_context
from save_wiki_items import load_items
from wiki_store import WikiItem, append_wiki_items, load_wiki_items


def test_wiki_store_dedupes_and_daily_context_includes_items(tmp_path: Path) -> None:
    item = WikiItem(
        id="wiki:llm-wiki",
        kind="topic",
        title="LLM WIKI 知识库",
        summary="把碎片资料沉淀成 agent 可读的长期知识条目。",
        source_id="mem:1",
        source_title="测试来源",
    )

    first = append_wiki_items([item], tmp_path)
    second = append_wiki_items([item], tmp_path)
    context = prepare_context(memory_home=tmp_path, date="2026-06-08")

    assert first["added"] == 1
    assert second["skipped"] == 1
    assert len(load_wiki_items(tmp_path)) == 1
    assert "LLM WIKI 知识库" in context
    assert "Accepted LLM WIKI Knowledge" in context


def test_prepare_wiki_context_includes_sources_and_existing_items(tmp_path: Path) -> None:
    append_sources([source_from_text("今天的判断", "这个工作流应该作为长期能力沉淀。", "note", "2026-06-08")], tmp_path)
    append_wiki_items([WikiItem(id="wiki:workflow", kind="workflow", title="每日整理", summary="从本地资料生成当天建议。")], tmp_path)

    context = prepare_wiki_context(tmp_path, date="2026-06-08")

    assert "LLM WIKI Extraction Context" in context
    assert "每日整理" in context
    assert "今天的判断" in context


def test_load_items_accepts_agent_output_shape(tmp_path: Path) -> None:
    path = tmp_path / "wiki-items.json"
    path.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "kind": "decision",
                        "title": "未来日期事项",
                        "summary": "明天跟进是未来待办，不是暂缓。",
                        "sourceTitle": "整理规则",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    items = load_items(path)

    assert len(items) == 1
    assert items[0].id.startswith("wiki:")
    assert items[0].summary.endswith("不是暂缓。")
