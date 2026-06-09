from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from source_loader import SourceItem, content_hash, dedupe_sources


DEFAULT_MEMORY_HOME = ".aipc-work-memory"


def resolve_memory_home(value: str | Path | None = None) -> Path:
    configured = value or os.environ.get("AIPC_WORK_MEMORY_HOME") or DEFAULT_MEMORY_HOME
    return Path(configured).expanduser().resolve()


def ensure_memory_home(memory_home: str | Path | None = None) -> Path:
    home = resolve_memory_home(memory_home)
    (home / "results").mkdir(parents=True, exist_ok=True)
    (home / "sources").mkdir(parents=True, exist_ok=True)
    source_log(home).touch(exist_ok=True)
    import_record_log(home).touch(exist_ok=True)
    return home


def source_log(memory_home: str | Path | None = None) -> Path:
    return resolve_memory_home(memory_home) / "sources.jsonl"


def import_record_log(memory_home: str | Path | None = None) -> Path:
    return resolve_memory_home(memory_home) / "import_records.jsonl"


def result_path(date: str, memory_home: str | Path | None = None) -> Path:
    safe_date = date or datetime.now(timezone.utc).date().isoformat()
    return resolve_memory_home(memory_home) / "results" / f"{safe_date}.daily-result.json"


def load_memory_sources(memory_home: str | Path | None = None) -> list[SourceItem]:
    path = source_log(memory_home)
    if not path.exists():
        return []
    sources: list[SourceItem] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            value = json.loads(line)
            sources.append(
                SourceItem(
                    id=str(value.get("id") or ""),
                    title=str(value.get("title") or ""),
                    body=str(value.get("body") or ""),
                    source_kind=str(value.get("sourceKind") or "note"),
                    source_date=str(value.get("sourceDate") or ""),
                    path=str(value.get("path") or ""),
                    url=str(value.get("url") or ""),
                    metadata=value.get("metadata") if isinstance(value.get("metadata"), dict) else value,
                )
            )
    return dedupe_sources(sources)


def append_sources(sources: Iterable[SourceItem], memory_home: str | Path | None = None) -> dict[str, int]:
    home = ensure_memory_home(memory_home)
    existing_hashes = {source.content_hash for source in load_memory_sources(home)}
    added = 0
    skipped = 0
    with source_log(home).open("a", encoding="utf-8") as fh:
        for source in sources:
            if not source.text:
                skipped += 1
                continue
            digest = source.content_hash
            if digest in existing_hashes:
                skipped += 1
                continue
            existing_hashes.add(digest)
            fh.write(json.dumps(source_to_record(source, digest), ensure_ascii=False) + "\n")
            added += 1
    return {"added": added, "skipped": skipped}


def source_to_record(source: SourceItem, digest: str | None = None) -> dict[str, Any]:
    return {
        "id": source.id or f"mem:{uuid.uuid4()}",
        "title": source.title,
        "body": source.body,
        "sourceKind": source.source_kind,
        "sourceDate": source.source_date,
        "path": source.path,
        "url": source.url,
        "contentHash": digest or source.content_hash,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "metadata": source.metadata,
    }


def append_import_record(
    source_system: str,
    source_kind: str,
    title: str,
    status: str = "imported",
    memory_home: str | Path | None = None,
    path: str = "",
    url: str = "",
    error: str = "",
    metadata: dict[str, Any] | None = None,
) -> None:
    home = ensure_memory_home(memory_home)
    record = {
        "id": f"import:{uuid.uuid4()}",
        "sourceSystem": source_system,
        "sourceKind": source_kind,
        "title": title,
        "status": status,
        "path": path,
        "url": url,
        "error": error,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "importedAt": datetime.now(timezone.utc).isoformat() if status == "imported" else "",
        "convertedAt": datetime.now(timezone.utc).isoformat() if status == "imported" else "",
        "metadata": metadata or {},
    }
    with import_record_log(home).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def save_daily_result(result: dict[str, Any], date: str = "", memory_home: str | Path | None = None) -> Path:
    home = ensure_memory_home(memory_home)
    resolved_date = date or str(result.get("date") or result.get("requestId") or "latest")
    path = result_path(resolved_date, home)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def source_from_text(
    title: str,
    body: str,
    source_kind: str = "note",
    source_date: str = "",
    path: str = "",
    url: str = "",
) -> SourceItem:
    digest = content_hash(title, body, source_kind, source_date)
    return SourceItem(
        id=f"mem:{digest[:16]}",
        title=title or body.strip().splitlines()[0][:80] or "Untitled memory",
        body=body,
        source_kind=source_kind,
        source_date=source_date,
        path=path,
        url=url,
    )
