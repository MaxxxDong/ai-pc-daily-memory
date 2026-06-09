from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from source_loader import _markdown_title, _sources_from_markdown_dir, load_request_sources


def test_load_request_sources_dedupes_content(tmp_path: Path) -> None:
    notes_dir = tmp_path / "notes"
    notes_dir.mkdir()
    (notes_dir / "one.md").write_text("# Same\n\n待办：完成 demo。", encoding="utf-8")
    (notes_dir / "two.md").write_text("# Same\n\n待办：完成 demo。", encoding="utf-8")
    request_path = tmp_path / "request.json"
    request_path.write_text(
        json.dumps(
            {
                "id": "demo",
                "notes": [
                    {"id": "n1", "title": "Same", "body": "待办：完成 demo。"},
                    {"id": "n2", "title": "Same", "body": "待办：完成 demo。"},
                ],
                "notesDirs": ["notes"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    _, sources = load_request_sources(request_path)

    assert len(sources) == 2
    assert {source.source_kind for source in sources} == {"note"}


def test_obsidian_vault_scan_skips_obsidian_config(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    config = vault / ".obsidian"
    config.mkdir(parents=True)
    (vault / "daily.md").write_text("# Daily\n\n待办：整理笔记。", encoding="utf-8")
    (config / "workspace.json.md").write_text("# Internal config", encoding="utf-8")

    sources = list(_sources_from_markdown_dir(vault, "obsidian", exclude_dirs={".obsidian"}))

    assert len(sources) == 1
    assert sources[0].title == "Daily"
    assert sources[0].source_kind == "obsidian"


def test_markdown_title_strips_wrapping_emphasis() -> None:
    assert _markdown_title("# **快速了解钉钉文档**\n\n正文") == "快速了解钉钉文档"
