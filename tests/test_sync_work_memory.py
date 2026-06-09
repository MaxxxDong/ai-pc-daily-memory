from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import sync_work_memory
from memory_store import load_memory_sources


def write_fake_dws(path: Path) -> None:
    path.write_text(
        """#!/usr/bin/env python3
import json
import sys

args = sys.argv[1:]
if "doc" in args and "read" in args:
    print(json.dumps({"content": "# 钉钉项目文档\\n\\n待办：补充比赛提交说明。"}, ensure_ascii=False))
elif "calendar" in args and "event" in args and "list" in args:
    print(json.dumps({"result": [{"summary": "产品例会", "start": {"dateTime": "2026-06-08T10:00:00+08:00"}, "end": {"dateTime": "2026-06-08T11:00:00+08:00"}}]}, ensure_ascii=False))
elif "todo" in args and "task" in args and "list" in args:
    print(json.dumps({"result": {"todoCards": [{"taskName": "整理今日资料"}]}}, ensure_ascii=False))
else:
    print(json.dumps({"ok": True}, ensure_ascii=False))
""",
        encoding="utf-8",
    )
    path.chmod(path.stat().st_mode | 0o111)


def test_sync_configured_sources_into_daily_context(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin" / "dws"
    fake_bin.parent.mkdir()
    write_fake_dws(fake_bin)

    local_dir = tmp_path / "notes"
    local_dir.mkdir()
    (local_dir / "today.md").write_text("# 今天看的文章\n\n关注 AI PC Agent Skills 参赛要求。", encoding="utf-8")

    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    (vault / ".obsidian" / "ignored.md").write_text("不应进入记忆库", encoding="utf-8")
    (vault / "meeting.md").write_text("# Obsidian 会议\n\n结论：今天要跑完整同步链路。", encoding="utf-8")

    config_path = tmp_path / "work-memory-config.json"
    config_path.write_text(
        json.dumps(
            {
                "memoryHome": ".memory",
                "date": "2026-06-08",
                "localMarkdownDirs": [{"path": "notes"}],
                "obsidianVaults": [{"path": "vault"}],
                "dingtalk": {
                    "enabled": True,
                    "cli": "./bin/dws",
                    "documents": [{"nodeId": "demo-node"}],
                    "calendar": {
                        "enabled": True,
                        "calendarId": "primary",
                        "start": "2026-06-08T00:00:00+08:00",
                        "end": "2026-06-09T00:00:00+08:00",
                    },
                    "todos": {"enabled": True, "size": 20},
                },
                "outputs": {"dailyContext": "out/daily_context.md", "wikiContext": "out/wiki_context.md"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = sync_work_memory.run_sync(config_path)
    sources = load_memory_sources(tmp_path / ".memory")
    kinds = {source.source_kind for source in sources}
    titles = {source.title for source in sources}

    assert result["memoryHome"] == str(tmp_path / ".memory")
    assert result["local"]["added"] == 2
    assert result["dingtalk"]["added"] == 3
    assert {"local-markdown", "obsidian", "dingtalk-document", "schedule", "task"} <= kinds
    assert "ignored" not in "\n".join(titles)
    assert (tmp_path / "out" / "daily_context.md").read_text(encoding="utf-8").startswith("# Local Work Memory Context")
    assert (tmp_path / "out" / "wiki_context.md").exists()
    import_records_path = tmp_path / ".memory" / "import_records.jsonl"
    records = [json.loads(line) for line in import_records_path.read_text(encoding="utf-8").splitlines()]
    assert {record["sourceSystem"] for record in records} >= {"local-markdown", "obsidian", "dingtalk"}
    assert all(record["status"] == "imported" for record in records)


def test_sync_requires_explicit_memory_home(tmp_path: Path) -> None:
    config_path = tmp_path / "work-memory-config.json"
    config_path.write_text(json.dumps({"date": "2026-06-08"}), encoding="utf-8")

    with pytest.raises(ValueError, match="memoryHome is required"):
        sync_work_memory.run_sync(config_path)


def test_sync_rejects_broad_source_directory(tmp_path: Path) -> None:
    config_path = tmp_path / "work-memory-config.json"
    config_path.write_text(
        json.dumps(
            {
                "memoryHome": ".memory",
                "date": "2026-06-08",
                "localMarkdownDirs": [{"path": str(Path.home())}],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="too broad"):
        sync_work_memory.run_sync(config_path)


def test_sync_filters_local_dirs_by_modified_today_and_explicit_files(tmp_path: Path) -> None:
    local_dir = tmp_path / "notes"
    local_dir.mkdir()
    today = local_dir / "today.md"
    yesterday = local_dir / "yesterday.md"
    explicit = local_dir / "explicit.md"
    today.write_text("# 今天资料\n\n待办：处理今天资料。", encoding="utf-8")
    yesterday.write_text("# 旧资料\n\n不应该默认进入今天。", encoding="utf-8")
    explicit.write_text("# 显式资料\n\n手动选入。", encoding="utf-8")
    ts_today = datetime(2026, 6, 8, 12, 0, tzinfo=ZoneInfo("Asia/Shanghai")).timestamp()
    ts_yesterday = datetime(2026, 6, 7, 12, 0, tzinfo=ZoneInfo("Asia/Shanghai")).timestamp()
    today.touch()
    yesterday.touch()
    explicit.touch()
    os.utime(today, (ts_today, ts_today))
    os.utime(yesterday, (ts_yesterday, ts_yesterday))
    os.utime(explicit, (ts_yesterday, ts_yesterday))

    config_path = tmp_path / "work-memory-config.json"
    config_path.write_text(
        json.dumps(
            {
                "memoryHome": ".memory",
                "date": "2026-06-08",
                "localMarkdownDirs": [{"path": "notes", "mode": "modifiedToday", "files": ["explicit.md"]}],
                "outputs": {"dailyContext": "out/daily_context.md"},
            }
        ),
        encoding="utf-8",
    )

    sync_work_memory.run_sync(config_path)
    titles = {source.title for source in load_memory_sources(tmp_path / ".memory")}

    assert titles == {"今天资料", "显式资料"}


def test_sync_imports_configured_links_and_writes_daily_markdown_placeholder(tmp_path: Path) -> None:
    config_path = tmp_path / "work-memory-config.json"
    config_path.write_text(
        json.dumps(
            {
                "memoryHome": ".memory",
                "date": "2026-06-08",
                "links": [{"url": "https://example.com/article", "title": "今天看的文章", "summary": "这篇文章讨论本地 AI PC 工作流。"}],
                "outputs": {"dailyContext": "out/daily_context.md", "dailyMarkdown": "out/daily_memory.md"},
            }
        ),
        encoding="utf-8",
    )

    result = sync_work_memory.run_sync(config_path)
    sources = load_memory_sources(tmp_path / ".memory")
    daily_markdown = tmp_path / "out" / "daily_memory.md"

    assert sources[0].source_kind == "link"
    assert sources[0].url == "https://example.com/article"
    assert "今天看的文章" in daily_markdown.read_text(encoding="utf-8")
    assert result["outputs"]["dailyMarkdown"] == str(daily_markdown)
