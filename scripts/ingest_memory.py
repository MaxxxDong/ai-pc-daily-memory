from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from memory_store import append_sources, ensure_memory_home, source_from_text
from source_loader import _sources_from_markdown_dir


def feishu_source_kind(value: str) -> str:
    if value == "calendar":
        return "schedule"
    if value == "task":
        return "task"
    return f"feishu-{value}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Store local notes or documents in the skill-owned work-memory store.")
    parser.add_argument("--memory-home", help="Local memory store directory. Defaults to .aipc-work-memory or AIPC_WORK_MEMORY_HOME.")
    parser.add_argument("--text", help="Text to store.")
    parser.add_argument("--file", action="append", default=[], help="Text or Markdown file to store.")
    parser.add_argument("--dir", action="append", default=[], help="Directory of Markdown/text files to store.")
    parser.add_argument("--local-markdown-dir", action="append", default=[], help="Alias for --dir with source kind local-markdown.")
    parser.add_argument("--obsidian-vault", action="append", default=[], help="Obsidian vault directory. Scans Markdown/text files and skips .obsidian and hidden folders.")
    parser.add_argument("--feishu-file", action="append", default=[], help="Markdown/text exported from Feishu/Lark docs or minutes.")
    parser.add_argument("--feishu-dir", action="append", default=[], help="Directory containing Markdown/text exported from Feishu/Lark.")
    parser.add_argument("--feishu-text", help="Manually pasted Feishu/Lark content.")
    parser.add_argument("--feishu-kind", default="document", choices=["document", "meeting", "calendar", "task", "message"], help="Feishu/Lark content type.")
    parser.add_argument("--title", default="", help="Title for --text or single-file input.")
    parser.add_argument("--kind", default="note", choices=["note", "journal", "task", "schedule", "source-document", "local-markdown", "obsidian", "feishu-document", "feishu-meeting", "feishu-calendar", "feishu-task", "feishu-message"], help="Source kind.")
    parser.add_argument("--date", default="", help="Source date, for example 2026-06-08.")
    args = parser.parse_args()

    home = ensure_memory_home(args.memory_home)
    sources = []
    if args.text:
        sources.append(source_from_text(args.title, args.text, args.kind, args.date))
    if args.feishu_text:
        sources.append(source_from_text(args.title or f"Feishu {args.feishu_kind}", args.feishu_text, feishu_source_kind(args.feishu_kind), args.date))
    for file_value in args.file:
        path = Path(file_value)
        body = path.read_text(encoding="utf-8", errors="replace")
        title = args.title or path.stem
        sources.append(source_from_text(title, body, args.kind, args.date, path=str(path)))
    for file_value in args.feishu_file:
        path = Path(file_value)
        body = path.read_text(encoding="utf-8", errors="replace")
        title = args.title or path.stem
        sources.append(source_from_text(title, body, feishu_source_kind(args.feishu_kind), args.date, path=str(path)))
    for dir_value in args.dir:
        sources.extend(_sources_from_markdown_dir(Path(dir_value), args.kind))
    for dir_value in args.local_markdown_dir:
        sources.extend(_sources_from_markdown_dir(Path(dir_value), "local-markdown"))
    for dir_value in args.obsidian_vault:
        sources.extend(_sources_from_markdown_dir(Path(dir_value), "obsidian", exclude_dirs={".obsidian", ".trash", ".git"}))
    for dir_value in args.feishu_dir:
        sources.extend(_sources_from_markdown_dir(Path(dir_value), feishu_source_kind(args.feishu_kind)))

    if not sources:
        raise SystemExit("no input provided; use --text, --file, or --dir")

    stats = append_sources(sources, home)
    print(json.dumps({"memoryHome": str(home), **stats}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
