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


def run_cli(cli: str, args: list[str], cwd: Path | None = None, timeout: int = 180) -> str:
    if not shutil.which(cli):
        raise RuntimeError(f"{cli} not found. Install and log in to lark-cli first.")
    process = subprocess.run(
        [cli, *args],
        cwd=str(cwd) if cwd else None,
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


def extract_body(raw: str) -> tuple[str, dict[str, Any]]:
    text = raw.strip()
    if not text:
        return "", {}
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return text, {}
    body = _find_text(value)
    return body or json.dumps(value, ensure_ascii=False, indent=2), value if isinstance(value, dict) else {"value": value}


def _find_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("markdown", "content", "summary", "transcript", "todos", "data", "result"):
            if key in value:
                found = _find_text(value[key])
                if found:
                    return found
    if isinstance(value, list):
        parts = [_find_text(item) for item in value]
        return "\n\n".join(part for part in parts if part)
    return ""


def exported_markdown_files(directory: Path) -> list[Path]:
    return sorted(path for path in directory.rglob("*") if path.suffix.lower() in {".md", ".markdown", ".txt", ".json"})


def source_kind(value: str) -> str:
    if value == "calendar":
        return "schedule"
    if value == "task":
        return "task"
    return f"feishu-{value}"


def ingest_doc_export(cli: str, token: str, doc_type: str, export_dir: Path, date: str) -> list[Any]:
    export_dir.mkdir(parents=True, exist_ok=True)
    output_name = f"{token}.md"
    run_cli(
        cli,
        [
            "drive",
            "+export",
            "--token",
            token,
            "--doc-type",
            doc_type,
            "--file-extension",
            "markdown",
            "--output",
            output_name,
            "--overwrite",
        ],
        cwd=export_dir,
    )
    path = export_dir / output_name
    if not path.exists():
        files = exported_markdown_files(export_dir)
        if not files:
            raise RuntimeError(f"lark-cli export succeeded but no markdown file was found in {export_dir}")
        path = files[-1]
    body = path.read_text(encoding="utf-8", errors="replace")
    return [source_from_text(_markdown_title(body) or path.stem, body, "feishu-document", date, path=str(path))]


def ingest_minutes(cli: str, token: str, export_dir: Path, date: str) -> list[Any]:
    export_dir.mkdir(parents=True, exist_ok=True)
    raw = run_cli(
        cli,
        ["vc", "+notes", "--minute-tokens", token, "--format", "json", "--output-dir", ".", "--overwrite"],
        cwd=export_dir,
    )
    body, metadata = extract_body(raw)
    if not body:
        files = exported_markdown_files(export_dir)
        if files:
            path = files[-1]
            body = path.read_text(encoding="utf-8", errors="replace")
            title = _markdown_title(body) or path.stem
            return [source_from_text(title, body, "feishu-meeting", date, path=str(path))]
    source = source_from_text(f"Feishu minutes {token}", body, "feishu-meeting", date)
    return [
        source.__class__(
            id=source.id,
            title=source.title,
            body=source.body,
            source_kind=source.source_kind,
            source_date=source.source_date,
            path=source.path,
            url=f"https://www.feishu.cn/minutes/{token}",
            metadata={"adapter": "lark-cli", "token": token, **metadata},
        )
    ]


def ingest_cli_stdout(cli: str, args: list[str], kind: str, title: str, date: str) -> list[Any]:
    raw = run_cli(cli, args)
    body, metadata = extract_body(raw)
    source = source_from_text(title, body, source_kind(kind), date)
    return [
        source.__class__(
            id=source.id,
            title=source.title,
            body=source.body,
            source_kind=source.source_kind,
            source_date=source.source_date,
            path=source.path,
            url=source.url,
            metadata={"adapter": "lark-cli", "command": [cli, *args], **metadata},
        )
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest Feishu/Lark content through an already configured lark-cli login.")
    parser.add_argument("--memory-home", help="Local memory store directory.")
    parser.add_argument("--cli", default="lark-cli", help="lark-cli executable name or path.")
    parser.add_argument("--auth-status", action="store_true", help="Only check lark-cli auth status.")
    parser.add_argument("--doc-token", help="Drive/doc token to export as Markdown through lark-cli drive +export.")
    parser.add_argument("--doc-type", default="docx", help="lark-cli document type, for example docx/wiki.")
    parser.add_argument("--minutes-token", help="Feishu minutes token to fetch through lark-cli vc +notes.")
    parser.add_argument("--agenda", action="store_true", help="Fetch agenda through lark-cli calendar +agenda.")
    parser.add_argument("--task-list", action="store_true", help="Fetch tasks through lark-cli task list.")
    parser.add_argument("--export-dir", default="", help="Relative or absolute export directory. Defaults to memory-home/sources/feishu-exports.")
    parser.add_argument("--title", default="", help="Stored title for stdout-style commands.")
    parser.add_argument("--date", default="", help="Source date.")
    args = parser.parse_args()

    try:
        if args.auth_status:
            print(run_cli(args.cli, ["auth", "status"]))
            return 0

        home = ensure_memory_home(args.memory_home)
        export_dir = Path(args.export_dir) if args.export_dir else home / "sources" / "feishu-exports"
        sources = []
        if args.doc_token:
            sources.extend(ingest_doc_export(args.cli, args.doc_token, args.doc_type, export_dir, args.date))
        if args.minutes_token:
            sources.extend(ingest_minutes(args.cli, args.minutes_token, export_dir / "minutes", args.date))
        if args.agenda:
            sources.extend(ingest_cli_stdout(args.cli, ["calendar", "+agenda"], "calendar", args.title or "Feishu agenda", args.date))
        if args.task_list:
            sources.extend(ingest_cli_stdout(args.cli, ["task", "list"], "task", args.title or "Feishu tasks", args.date))
        if not sources:
            raise RuntimeError("no Feishu source selected; use --doc-token, --minutes-token, --agenda, or --task-list")
        stats = append_sources(sources, home)
        print(json.dumps({"adapter": "lark-cli", **stats}, ensure_ascii=False))
        return 0
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
