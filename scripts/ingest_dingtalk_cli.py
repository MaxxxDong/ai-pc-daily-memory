from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from memory_store import append_sources, ensure_memory_home, source_from_text
from source_loader import _markdown_title


def run_cli(cli: str, args: list[str], timeout: int = 120) -> str:
    if not shutil.which(cli):
        raise RuntimeError(f"{cli} not found. Install and configure dingtalk-cli first.")
    process = subprocess.run(
        [cli, *args],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    if process.returncode != 0:
        stderr = process.stderr.strip() or process.stdout.strip()
        raise RuntimeError(f"{cli} {' '.join(args)} failed with exit code {process.returncode}: {stderr}")
    return process.stdout


def extract_content(raw: str) -> tuple[str, dict[str, Any]]:
    text = raw.strip()
    if not text:
        return "", {}
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return text, {}
    content = _find_text(value)
    return content or json.dumps(value, ensure_ascii=False, indent=2), value if isinstance(value, dict) else {"value": value}


def _find_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("markdown", "content", "body", "text", "data", "result"):
            if key in value:
                found = _find_text(value[key])
                if found:
                    return found
    if isinstance(value, list):
        parts = [_find_text(item) for item in value]
        return "\n\n".join(part for part in parts if part)
    return ""


def cli_style(cli: str, explicit: str = "auto") -> str:
    if explicit != "auto":
        return explicit
    name = Path(cli).name.lower()
    if name.startswith("dws"):
        return "dws"
    return "dingtalk-cli"


def json_prefix(style: str) -> list[str]:
    if style == "dws":
        return ["-f", "json"]
    return ["--json"]


def doc_read_args(style: str, node: str) -> list[str]:
    if style == "dws":
        return [*json_prefix(style), "doc", "read", "--node", node]
    return [*json_prefix(style), "doc", "read", "--node-id", node]


def workbook_read_args(style: str, node: str, workbook_range: str = "") -> list[str]:
    if style == "dws":
        args = [*json_prefix(style), "sheet", "range", "read", "--node", node]
    else:
        args = [*json_prefix(style), "workbook", "read", "--node-id", node]
    if workbook_range:
        args.extend(["--range", workbook_range])
    return args


def calendar_event_args(style: str, start: str = "", end: str = "", calendar_id: str = "primary") -> list[str]:
    if style != "dws":
        raise RuntimeError("calendar events require official dws; legacy dingtalk-cli is not supported")
    args = [*json_prefix(style), "calendar", "event", "list"]
    if calendar_id:
        args.extend(["--calendar-id", calendar_id])
    if start:
        args.extend(["--start", start])
    if end:
        args.extend(["--end", end])
    return args


def todo_open_args(style: str, page: str = "1", size: str = "20") -> list[str]:
    if style != "dws":
        raise RuntimeError("DingTalk todo import requires official dws; legacy dingtalk-cli is not supported")
    return [*json_prefix(style), "todo", "task", "list", "--page", page, "--size", size, "--status", "false"]


def records_from_json(raw: str, preferred_keys: tuple[str, ...]) -> list[dict[str, Any]]:
    try:
        value = json.loads(raw.strip() or "{}")
    except json.JSONDecodeError:
        return []
    for key in preferred_keys:
        found = _value_at_key(value, key)
        if isinstance(found, list):
            return [item for item in found if isinstance(item, dict)]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def _value_at_key(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        if key in value:
            return value[key]
        for child in value.values():
            found = _value_at_key(child, key)
            if found is not None:
                return found
    if isinstance(value, list):
        for child in value:
            found = _value_at_key(child, key)
            if found is not None:
                return found
    return None


def value_text(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("dateTime", "date", "timestamp", "time", "value"):
            if value.get(key):
                return str(value[key])
    if value is None:
        return ""
    return str(value)


def title_from_record(record: dict[str, Any], fallback: str) -> str:
    for key in ("summary", "title", "subject", "taskName", "content", "name"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return fallback


def sources_from_calendar(raw: str, date: str, calendar_id: str = "primary") -> list[Any]:
    records = records_from_json(raw, ("items", "events", "eventList", "list", "result"))
    sources = []
    for index, record in enumerate(records, start=1):
        title = title_from_record(record, f"DingTalk calendar event {index}")
        start = value_text(record.get("start") or record.get("startTime"))
        end = value_text(record.get("end") or record.get("endTime"))
        body = json.dumps(record, ensure_ascii=False, indent=2)
        source = source_from_text(title, body, "schedule", date)
        sources.append(
            source.__class__(
                id=source.id,
                title=source.title,
                body=source.body,
                source_kind=source.source_kind,
                source_date=source.source_date,
                path=source.path,
                url=str(record.get("url") or record.get("link") or ""),
                metadata={"adapter": "dws", "calendarId": calendar_id, "start": start, "end": end, "record": record},
            )
        )
    return sources


def sources_from_todos(raw: str, date: str) -> list[Any]:
    records = records_from_json(raw, ("todoCards", "items", "tasks", "list", "result"))
    sources = []
    for index, record in enumerate(records, start=1):
        title = title_from_record(record, f"DingTalk todo {index}")
        body = title if title else json.dumps(record, ensure_ascii=False, indent=2)
        source = source_from_text(title, body, "task", date)
        sources.append(
            source.__class__(
                id=source.id,
                title=source.title,
                body=source.body,
                source_kind=source.source_kind,
                source_date=source.source_date,
                path=source.path,
                url=str(record.get("url") or record.get("link") or ""),
                metadata={"adapter": "dws", "record": record},
            )
        )
    return sources


def read_dingtalk(
    cli: str,
    style: str,
    doc_url: str = "",
    doc_key: str = "",
    node_id: str = "",
    workbook_node_id: str = "",
    workbook_range: str = "",
) -> tuple[str, str, dict[str, Any]]:
    if doc_url:
        raw = run_cli(cli, doc_read_args(style, doc_url))
        body, metadata = extract_content(raw)
        return _markdown_title(body) or "DingTalk document", body, {"url": doc_url, **metadata}
    if doc_key:
        raw = run_cli(cli, doc_read_args(style, doc_key))
        body, metadata = extract_content(raw)
        return _markdown_title(body) or f"DingTalk doc {doc_key}", body, {"docKey": doc_key, **metadata}
    if node_id:
        raw = run_cli(cli, doc_read_args(style, node_id))
        body, metadata = extract_content(raw)
        return _markdown_title(body) or f"DingTalk node {node_id}", body, {"nodeId": node_id, **metadata}
    if workbook_node_id:
        raw = run_cli(cli, workbook_read_args(style, workbook_node_id, workbook_range))
        body, metadata = extract_content(raw)
        return _markdown_title(body) or f"DingTalk workbook {workbook_node_id}", body, {"nodeId": workbook_node_id, "range": workbook_range, **metadata}
    raise RuntimeError("provide --doc-url, --doc-key, --node-id, or --workbook-node-id")


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest DingTalk documents through an already configured dws or dingtalk-cli login.")
    parser.add_argument("--memory-home", help="Local memory store directory.")
    parser.add_argument("--cli", default="dws", help="DingTalk CLI executable name or path. Prefer official dws; dingtalk-cli is also supported.")
    parser.add_argument("--cli-style", default="auto", choices=["auto", "dws", "dingtalk-cli"], help="Command style. Auto detects from --cli name.")
    parser.add_argument("--doc-url", help="DingTalk document URL.")
    parser.add_argument("--doc-key", help="DingTalk document key.")
    parser.add_argument("--node-id", help="DingTalk document node id.")
    parser.add_argument("--workbook-node-id", help="DingTalk workbook node id.")
    parser.add_argument("--range", default="", help="Workbook range, for example A1:Z80.")
    parser.add_argument("--title", default="", help="Override stored title.")
    parser.add_argument("--date", default="", help="Source date.")
    parser.add_argument("--kind", default="dingtalk-document", choices=["dingtalk-document", "dingtalk-meeting", "dingtalk-calendar", "dingtalk-task", "dingtalk-message"], help="Stored source kind.")
    parser.add_argument("--auth-status", action="store_true", help="Only check dingtalk-cli auth status.")
    parser.add_argument("--calendar-events", action="store_true", help="Import DingTalk calendar events for a date range through dws.")
    parser.add_argument("--calendar-id", default="primary", help="DingTalk calendar id for --calendar-events.")
    parser.add_argument("--start", default="", help="Calendar range start, ISO-8601.")
    parser.add_argument("--end", default="", help="Calendar range end, ISO-8601.")
    parser.add_argument("--todo-open", action="store_true", help="Import current user's open DingTalk todos through dws.")
    args = parser.parse_args()

    style = cli_style(args.cli, args.cli_style)

    try:
        if args.auth_status:
            print(run_cli(args.cli, ["auth", "status"]))
            return 0

        ensure_memory_home(args.memory_home)
        sources = []
        if args.calendar_events:
            raw = run_cli(args.cli, calendar_event_args(style, args.start, args.end, args.calendar_id))
            sources.extend(sources_from_calendar(raw, args.date, args.calendar_id))
        if args.todo_open:
            raw = run_cli(args.cli, todo_open_args(style))
            sources.extend(sources_from_todos(raw, args.date))
        if args.doc_url or args.doc_key or args.node_id or args.workbook_node_id:
            title, body, metadata = read_dingtalk(
                args.cli,
                style,
                doc_url=args.doc_url or "",
                doc_key=args.doc_key or "",
                node_id=args.node_id or "",
                workbook_node_id=args.workbook_node_id or "",
                workbook_range=args.range or "",
            )
            source = source_from_text(args.title or title, body, args.kind, args.date)
            sources.append(
                source.__class__(
                    id=source.id,
                    title=source.title,
                    body=source.body,
                    source_kind=source.source_kind,
                    source_date=source.source_date,
                    path=source.path,
                    url=metadata.get("url", ""),
                    metadata={"adapter": style, **metadata},
                )
            )
        if not sources:
            raise RuntimeError("no DingTalk source selected; use --doc-url, --node-id, --workbook-node-id, --calendar-events, or --todo-open")
        stats = append_sources(sources, args.memory_home)
        print(json.dumps({"adapter": style, **stats}, ensure_ascii=False))
        return 0
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
