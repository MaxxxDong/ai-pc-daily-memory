from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from ingest_dingtalk_cli import (
    calendar_event_args,
    cli_style,
    read_dingtalk,
    run_cli as run_dingtalk_cli,
    sources_from_calendar,
    sources_from_todos,
    todo_open_args,
)
from memory_store import append_import_record, append_sources, ensure_memory_home, import_record_log, load_memory_sources, resolve_memory_home, source_from_text
from prepare_daily_context import prepare_context
from prepare_wiki_context import prepare_wiki_context
from source_loader import SourceItem, _markdown_title, _sources_from_markdown_dir, content_hash


def load_config(path: str | Path) -> tuple[Path, dict[str, Any]]:
    config_path = Path(path).expanduser().resolve()
    value = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("sync config must be a JSON object")
    return config_path, value


def resolve_config_path(value: str, base_dir: Path) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = base_dir / path
    return path.resolve()


def require_memory_home(config: dict[str, Any], base_dir: Path, override: str = "") -> Path:
    configured = override or str(config.get("memoryHome") or "")
    if not configured:
        raise ValueError("memoryHome is required; set the exact local work-memory directory before syncing sources")
    if override:
        return resolve_memory_home(configured)
    return resolve_config_path(configured, base_dir)


def validate_source_dir(path: Path, label: str) -> None:
    if not path.exists():
        raise ValueError(f"{label} does not exist: {path}")
    if not path.is_dir():
        raise ValueError(f"{label} must be a directory: {path}")
    if path == path.parent or str(path) in {"/", str(Path.home())}:
        raise ValueError(f"{label} is too broad and is not allowed: {path}")


def selected_items(config: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = config.get(key) or []
    if isinstance(value, dict):
        value = [value]
    if not isinstance(value, list):
        raise ValueError(f"{key} must be a list")
    result = []
    for item in value:
        if isinstance(item, str):
            result.append({"path": item, "enabled": True})
        elif isinstance(item, dict) and item.get("enabled", True):
            result.append(item)
    return result


def date_from_mtime(path: Path, timezone_name: str) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, ZoneInfo(timezone_name)).date().isoformat()


def source_from_path(path: Path, source_kind: str, date: str) -> SourceItem:
    body = path.read_text(encoding="utf-8", errors="replace")
    title = _markdown_title(body) or path.stem
    return SourceItem(
        id=f"file:{content_hash(title, body)[:12]}",
        title=title,
        body=body,
        source_kind=source_kind,
        source_date=date,
        path=str(path),
    )


def configured_markdown_sources(item: dict[str, Any], base_dir: Path, date: str, source_kind: str, label: str, exclude_dirs: set[str] | None = None) -> list[SourceItem]:
    path = resolve_config_path(str(item["path"]), base_dir)
    validate_source_dir(path, label)
    mode = str(item.get("mode") or "all")
    timezone_name = str(item.get("timezone") or "Asia/Shanghai")
    explicit_files = [resolve_config_path(str(value), path) for value in item.get("files") or []]
    sources: list[SourceItem] = []
    seen_paths: set[Path] = set()

    if mode not in {"all", "modifiedToday", "explicitFiles"}:
        raise ValueError(f"{label}.mode must be all, modifiedToday, or explicitFiles")

    if mode != "explicitFiles":
        for source in _sources_from_markdown_dir(path, source_kind, exclude_dirs=exclude_dirs):
            source_path = Path(source.path)
            if mode == "modifiedToday" and date_from_mtime(source_path, timezone_name) != date:
                continue
            seen_paths.add(source_path.resolve())
            sources.append(
                source.__class__(
                    id=source.id,
                    title=source.title,
                    body=source.body,
                    source_kind=source.source_kind,
                    source_date=source.source_date or date,
                    path=source.path,
                    url=source.url,
                    metadata={"sourceSystem": source_kind, "syncMode": mode, **source.metadata},
                )
            )

    for explicit_path in explicit_files:
        if not explicit_path.is_file():
            raise ValueError(f"{label}.files item must be a file: {explicit_path}")
        if explicit_path.resolve() in seen_paths:
            continue
        sources.append(source_from_path(explicit_path, source_kind, date))
    return sources


def record_imports(sources: list[SourceItem], source_system: str, memory_home: Path) -> None:
    for source in sources:
        append_import_record(
            source_system=source_system,
            source_kind=source.source_kind,
            title=source.title,
            memory_home=memory_home,
            path=source.path,
            url=source.url,
            metadata=source.metadata,
        )


def sync_local_sources(config: dict[str, Any], base_dir: Path, date: str, memory_home: Path) -> dict[str, int]:
    sources = []
    for item in selected_items(config, "localMarkdownDirs"):
        item_sources = configured_markdown_sources(item, base_dir, date, "local-markdown", "localMarkdownDirs.path")
        record_imports(item_sources, "local-markdown", memory_home)
        sources.extend(item_sources)
    for item in selected_items(config, "obsidianVaults"):
        item_sources = configured_markdown_sources(item, base_dir, date, "obsidian", "obsidianVaults.path", exclude_dirs={".obsidian", ".trash", ".git"})
        record_imports(item_sources, "obsidian", memory_home)
        sources.extend(item_sources)
    if not sources:
        return {"added": 0, "skipped": 0}
    dated_sources = [
        source.__class__(
            id=source.id,
            title=source.title,
            body=source.body,
            source_kind=source.source_kind,
            source_date=source.source_date or date,
            path=source.path,
            url=source.url,
            metadata=source.metadata,
        )
        for source in sources
    ]
    return append_sources(dated_sources, memory_home)


def sync_links(config: dict[str, Any], date: str, memory_home: Path) -> dict[str, int]:
    sources = []
    for item in selected_items(config, "links"):
        url = str(item.get("url") or item.get("href") or "")
        if not url:
            continue
        title = str(item.get("title") or url)
        body = str(item.get("summary") or item.get("body") or item.get("text") or title)
        source = source_from_text(title, body, "link", date, url=url)
        source = source.__class__(
            id=source.id,
            title=source.title,
            body=source.body,
            source_kind=source.source_kind,
            source_date=source.source_date,
            path=source.path,
            url=source.url,
            metadata={"sourceSystem": "link", "status": "configured"},
        )
        sources.append(source)
    record_imports(sources, "link", memory_home)
    return append_sources(sources, memory_home) if sources else {"added": 0, "skipped": 0}


def resolve_cli(value: str, base_dir: Path) -> str:
    if not value:
        return value
    if "/" not in value and "\\" not in value:
        return value
    return str(resolve_config_path(value, base_dir))


def sync_dingtalk(config: dict[str, Any], base_dir: Path, date: str, memory_home: Path) -> dict[str, Any]:
    dingtalk = config.get("dingtalk") or {}
    if not isinstance(dingtalk, dict) or not dingtalk.get("enabled", False):
        return {"enabled": False, "added": 0, "skipped": 0, "details": []}
    cli = resolve_cli(str(dingtalk.get("cli") or "dws"), base_dir)
    style = cli_style(cli, str(dingtalk.get("cliStyle") or "auto"))
    sources = []
    details: list[dict[str, Any]] = []

    for item in selected_items(dingtalk, "documents"):
        node = str(item.get("nodeId") or item.get("node") or item.get("url") or "")
        if not node:
            continue
        title, body, metadata = read_dingtalk(cli, style, node_id=node)
        source = source_from_text(str(item.get("title") or title), body, "dingtalk-document", date, url=metadata.get("url", ""))
        sources.append(source.__class__(**{**source.__dict__, "metadata": {"adapter": style, **metadata}}))
        details.append({"type": "document", "title": source.title})

    for item in selected_items(dingtalk, "sheets"):
        node = str(item.get("nodeId") or item.get("node") or item.get("url") or "")
        if not node:
            continue
        title, body, metadata = read_dingtalk(cli, style, workbook_node_id=node, workbook_range=str(item.get("range") or ""))
        source = source_from_text(str(item.get("title") or title), body, "dingtalk-document", date)
        sources.append(source.__class__(**{**source.__dict__, "metadata": {"adapter": style, **metadata}}))
        details.append({"type": "sheet", "title": source.title})

    calendar = dingtalk.get("calendar") or {}
    if isinstance(calendar, dict) and calendar.get("enabled", False):
        start = str(calendar.get("start") or "")
        end = str(calendar.get("end") or "")
        calendar_id = str(calendar.get("calendarId") or "primary")
        raw = run_dingtalk_cli(cli, calendar_event_args(style, start, end, calendar_id))
        calendar_sources = sources_from_calendar(raw, date, calendar_id)
        sources.extend(calendar_sources)
        details.append({"type": "calendar", "addedCandidates": len(calendar_sources), "calendarId": calendar_id})

    todos = dingtalk.get("todos") or {}
    if isinstance(todos, dict) and todos.get("enabled", False):
        raw = run_dingtalk_cli(cli, todo_open_args(style, size=str(todos.get("size") or "20")))
        todo_sources = sources_from_todos(raw, date)
        sources.extend(todo_sources)
        details.append({"type": "todo", "addedCandidates": len(todo_sources)})

    stats = append_sources(sources, memory_home) if sources else {"added": 0, "skipped": 0}
    record_imports(sources, "dingtalk", memory_home)
    return {"enabled": True, **stats, "details": details}


def sync_feishu(config: dict[str, Any], base_dir: Path, date: str, memory_home: Path) -> dict[str, Any]:
    feishu = config.get("feishu") or {}
    if not isinstance(feishu, dict) or not feishu.get("enabled", False):
        return {"enabled": False, "added": 0, "skipped": 0, "details": []}
    cli = resolve_cli(str(feishu.get("cli") or "lark-cli"), base_dir)
    commands: list[list[str]] = []
    base = [sys.executable, str(SCRIPT_DIR / "ingest_feishu_cli.py"), "--cli", cli, "--memory-home", str(memory_home), "--date", date]
    if feishu.get("agenda", False):
        commands.append([*base, "--agenda"])
    if feishu.get("taskList", False):
        commands.append([*base, "--task-list"])
    for token in feishu.get("docTokens") or []:
        commands.append([*base, "--doc-token", str(token)])
    for token in feishu.get("minutesTokens") or []:
        commands.append([*base, "--minutes-token", str(token)])
    details = []
    added = skipped = 0
    for command in commands:
        process = subprocess.run(command, check=False, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if process.returncode != 0:
            raise RuntimeError((process.stderr or process.stdout).strip())
        value = json.loads(process.stdout)
        added += int(value.get("added") or 0)
        skipped += int(value.get("skipped") or 0)
        details.append({"command": command[-2:] if len(command) > 2 else command, "added": value.get("added"), "skipped": value.get("skipped")})
    return {"enabled": True, "added": added, "skipped": skipped, "details": details}


def render_daily_markdown_draft(date: str, memory_home: Path) -> str:
    sources = load_memory_sources(memory_home)
    lines = [
        f"# 今日工作记忆 {date}",
        "",
        "这是一份由 Skill 根据已同步来源生成的本地草稿。最终版应由调用方 AI PC agent 读取 dailyContext 后生成 DailyResult，再用 save_daily_result.py 写回。",
        "",
        "## 今日日程",
    ]
    schedules = [source for source in sources if source.source_kind == "schedule" and (not date or source.source_date == date)]
    if schedules:
        for source in schedules:
            start = source.metadata.get("start") or source.source_date
            lines.append(f"- {start} {source.title}".strip())
    else:
        lines.append("- 暂无已同步日程。")
    lines.extend(["", "## 今日待办线索"])
    tasks = [source for source in sources if source.source_kind == "task" and (not date or source.source_date == date)]
    if tasks:
        for source in tasks:
            lines.append(f"- {source.title}")
    else:
        lines.append("- 暂无已同步待办。")
    lines.extend(["", "## 今天看的文章和资料"])
    documents = [source for source in sources if source.source_kind not in {"schedule", "task"} and (not date or source.source_date == date)]
    if documents:
        for source in documents:
            ref = source.url or source.path or source.id
            lines.append(f"- {source.title} ({source.source_kind}) - {ref}")
    else:
        lines.append("- 暂无已同步资料。")
    return "\n".join(lines).rstrip() + "\n"


def write_context_outputs(config: dict[str, Any], date: str, memory_home: Path, base_dir: Path) -> dict[str, str]:
    outputs = config.get("outputs") or {}
    if not isinstance(outputs, dict):
        return {}
    written: dict[str, str] = {}
    wiki_path = outputs.get("wikiContext")
    if wiki_path:
        path = resolve_config_path(str(wiki_path), base_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(prepare_wiki_context(memory_home=memory_home, date=date), encoding="utf-8")
        written["wikiContext"] = str(path)
    daily_path = outputs.get("dailyContext")
    if daily_path:
        path = resolve_config_path(str(daily_path), base_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(prepare_context(memory_home=memory_home, date=date), encoding="utf-8")
        written["dailyContext"] = str(path)
    daily_markdown_path = outputs.get("dailyMarkdown")
    if daily_markdown_path:
        path = resolve_config_path(str(daily_markdown_path), base_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render_daily_markdown_draft(date, memory_home), encoding="utf-8")
        written["dailyMarkdown"] = str(path)
    return written


def run_sync(config_path: str | Path, date_override: str = "", memory_home_override: str = "") -> dict[str, Any]:
    config_file, config = load_config(config_path)
    base_dir = config_file.parent
    date = date_override or str(config.get("date") or "")
    if not date:
        raise ValueError("date is required in config or --date")
    memory_home = require_memory_home(config, base_dir, memory_home_override)
    ensure_memory_home(memory_home)
    local_stats = sync_local_sources(config, base_dir, date, memory_home)
    link_stats = sync_links(config, date, memory_home)
    dingtalk_stats = sync_dingtalk(config, base_dir, date, memory_home)
    feishu_stats = sync_feishu(config, base_dir, date, memory_home)
    outputs = write_context_outputs(config, date, memory_home, base_dir)
    return {
        "memoryHome": str(memory_home),
        "date": date,
        "importRecords": str(import_record_log(memory_home)),
        "local": local_stats,
        "links": link_stats,
        "dingtalk": dingtalk_stats,
        "feishu": feishu_stats,
        "outputs": outputs,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync explicitly configured local, Obsidian, Feishu, and DingTalk sources into AI PC work memory.")
    parser.add_argument("--config", required=True, help="Explicit source config JSON. Broad or implicit scans are not supported.")
    parser.add_argument("--date", default="", help="Override config date.")
    parser.add_argument("--memory-home", default="", help="Override config memoryHome.")
    args = parser.parse_args()

    try:
        print(json.dumps(run_sync(args.config, args.date, args.memory_home), ensure_ascii=False, indent=2))
        return 0
    except (RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
