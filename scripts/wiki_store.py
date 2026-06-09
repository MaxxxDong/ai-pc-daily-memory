from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from source_loader import content_hash, normalize_text
from memory_store import ensure_memory_home, resolve_memory_home


@dataclass(frozen=True)
class WikiItem:
    id: str
    kind: str
    title: str
    summary: str
    source_id: str = ""
    source_title: str = ""
    source_date: str = ""
    tags: list[str] = field(default_factory=list)
    related: list[str] = field(default_factory=list)
    status: str = "accepted"

    @property
    def text(self) -> str:
        return "\n".join(part for part in [self.title.strip(), self.summary.strip()] if part)

    @property
    def content_hash(self) -> str:
        return wiki_hash(self.kind, self.title, self.summary, self.source_id, self.source_title)


def wiki_log(memory_home: str | Path | None = None) -> Path:
    return resolve_memory_home(memory_home) / "wiki.jsonl"


def ensure_wiki_store(memory_home: str | Path | None = None) -> Path:
    home = ensure_memory_home(memory_home)
    wiki_log(home).touch(exist_ok=True)
    return home


def wiki_hash(kind: str, title: str, summary: str, source_id: str = "", source_title: str = "") -> str:
    return content_hash(kind, title, summary, source_id, source_title)


def load_wiki_items(memory_home: str | Path | None = None, status: str = "accepted") -> list[WikiItem]:
    path = wiki_log(memory_home)
    if not path.exists():
        return []
    items: list[WikiItem] = []
    seen: set[str] = set()
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            value = json.loads(line)
            item = wiki_item_from_record(value)
            if status and item.status != status:
                continue
            digest = item.content_hash
            if digest in seen or not item.text:
                continue
            seen.add(digest)
            items.append(item)
    return items


def append_wiki_items(items: Iterable[WikiItem], memory_home: str | Path | None = None) -> dict[str, int]:
    home = ensure_wiki_store(memory_home)
    existing_hashes = {item.content_hash for item in load_wiki_items(home, status="")}
    added = 0
    skipped = 0
    with wiki_log(home).open("a", encoding="utf-8") as fh:
        for item in items:
            if not item.text:
                skipped += 1
                continue
            digest = item.content_hash
            if digest in existing_hashes:
                skipped += 1
                continue
            existing_hashes.add(digest)
            fh.write(json.dumps(wiki_item_to_record(item, digest), ensure_ascii=False) + "\n")
            added += 1
    return {"added": added, "skipped": skipped}


def wiki_item_from_record(value: dict[str, Any]) -> WikiItem:
    return WikiItem(
        id=normalize_text(value.get("id")) or f"wiki:{wiki_hash(normalize_text(value.get('kind')), normalize_text(value.get('title')), normalize_text(value.get('summary')))[:16]}",
        kind=normalize_text(value.get("kind")) or "claim",
        title=normalize_text(value.get("title")),
        summary=normalize_text(value.get("summary")),
        source_id=normalize_text(value.get("sourceId") or value.get("source_id")),
        source_title=normalize_text(value.get("sourceTitle") or value.get("source_title")),
        source_date=normalize_text(value.get("sourceDate") or value.get("source_date")),
        tags=[normalize_text(item) for item in value.get("tags", []) if normalize_text(item)] if isinstance(value.get("tags"), list) else [],
        related=[normalize_text(item) for item in value.get("related", []) if normalize_text(item)] if isinstance(value.get("related"), list) else [],
        status=normalize_text(value.get("status")) or "accepted",
    )


def wiki_item_to_record(item: WikiItem, digest: str | None = None) -> dict[str, Any]:
    return {
        "id": item.id or f"wiki:{(digest or item.content_hash)[:16]}",
        "kind": item.kind,
        "title": item.title,
        "summary": item.summary,
        "sourceId": item.source_id,
        "sourceTitle": item.source_title,
        "sourceDate": item.source_date,
        "tags": item.tags,
        "related": item.related,
        "status": item.status,
        "contentHash": digest or item.content_hash,
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }
