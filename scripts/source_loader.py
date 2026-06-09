from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable


URL_RE = re.compile(r"https?://[^\s)>\]]+")


@dataclass(frozen=True)
class SourceItem:
    id: str
    title: str
    body: str
    source_kind: str = "note"
    source_date: str = ""
    path: str = ""
    url: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def text(self) -> str:
        parts = [self.title.strip(), self.body.strip()]
        return "\n".join(part for part in parts if part)

    @property
    def content_hash(self) -> str:
        return content_hash(self.title, self.body, self.source_kind, self.source_date)

    def prompt_block(self, max_chars: int = 1800) -> str:
        body = self.body.strip()
        if len(body) > max_chars:
            body = body[:max_chars].rstrip() + "\n...[truncated]"
        ref = self.path or self.url or self.id
        return (
            f"### {self.title}\n"
            f"- id: {self.id}\n"
            f"- kind: {self.source_kind}\n"
            f"- date: {self.source_date}\n"
            f"- ref: {ref}\n\n"
            f"{body}"
        )


def read_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as fh:
        value = json.load(fh)
    if not isinstance(value, dict):
        raise ValueError(f"request must be a JSON object: {path}")
    return value


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("\r\n", "\n").replace("\r", "\n").strip()


def content_hash(*parts: str) -> str:
    joined = "\n".join(normalize_text(part) for part in parts if normalize_text(part))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def extract_urls(text: str) -> list[str]:
    seen: set[str] = set()
    urls: list[str] = []
    for match in URL_RE.finditer(text):
        url = match.group(0).rstrip(".,;，。；")
        if url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def load_request_sources(
    request_path: str | Path,
    notes_dirs: Iterable[str | Path] | None = None,
    source_dirs: Iterable[str | Path] | None = None,
) -> tuple[dict[str, Any], list[SourceItem]]:
    request_file = Path(request_path)
    request = read_json(request_file)
    base_dir = request_file.parent
    sources = list(_sources_from_request(request))

    requested_note_dirs = _request_path_list(request, "notesDir", "notesDirs", "markdownFolders")
    requested_source_dirs = _request_path_list(request, "sourcesDir", "sourceDirs", "sourceFolders")

    for directory in [*(notes_dirs or []), *requested_note_dirs]:
        sources.extend(_sources_from_markdown_dir(resolve_path(directory, base_dir), "note"))

    for directory in [*(source_dirs or []), *requested_source_dirs]:
        sources.extend(_sources_from_markdown_dir(resolve_path(directory, base_dir), "source-document"))

    return request, dedupe_sources(sources)


def dedupe_sources(sources: Iterable[SourceItem]) -> list[SourceItem]:
    seen_hashes: set[str] = set()
    result: list[SourceItem] = []
    for source in sources:
        if not source.text:
            continue
        digest = source.content_hash
        if digest in seen_hashes:
            continue
        seen_hashes.add(digest)
        result.append(source)
    return result


def resolve_path(value: str | Path, base_dir: Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = base_dir / path
    return path


def _request_path_list(request: dict[str, Any], *keys: str) -> list[str]:
    paths: list[str] = []
    for key in keys:
        value = request.get(key)
        if isinstance(value, str):
            paths.append(value)
        elif isinstance(value, list):
            paths.extend(str(item) for item in value if item)
    return paths


def _sources_from_request(request: dict[str, Any]) -> Iterable[SourceItem]:
    yield from _items(request.get("notes"), "note")
    yield from _items(request.get("journals"), "journal")
    yield from _items(request.get("openTasks"), "task")
    yield from _items(request.get("tasks"), "task")
    yield from _items(request.get("schedule"), "schedule")
    yield from _items(request.get("schedules"), "schedule")
    yield from _items(request.get("sourceDocuments"), "source-document")
    yield from _items(request.get("source_documents"), "source-document")
    yield from _items(request.get("sources"), "source-document")
    yield from _items(request.get("documents"), "source-document")
    yield from _items(request.get("externalDocuments"), "source-document")


def _items(value: Any, source_kind: str) -> Iterable[SourceItem]:
    if not value:
        return
    if isinstance(value, dict):
        value = [value]
    if not isinstance(value, list):
        return
    for index, item in enumerate(value):
        if isinstance(item, str):
            body = normalize_text(item)
            title = body.splitlines()[0][:80] if body else f"{source_kind}-{index + 1}"
            yield SourceItem(
                id=f"{source_kind}:{index + 1}",
                title=title,
                body=body,
                source_kind=source_kind,
            )
            continue
        if not isinstance(item, dict):
            continue
        title = normalize_text(item.get("title") or item.get("name") or f"{source_kind}-{index + 1}")
        body = normalize_text(
            item.get("body")
            or item.get("content")
            or item.get("text")
            or item.get("summary")
            or item.get("description")
            or title
        )
        source_id = normalize_text(item.get("id") or item.get("sourceNoteId") or item.get("sourceDocumentId"))
        if not source_id:
            source_id = f"{source_kind}:{content_hash(title, body)[:12]}"
        source_date = normalize_text(item.get("date") or item.get("createdAt") or item.get("sourceDate"))
        path = normalize_text(item.get("path") or item.get("filePath") or item.get("sourcePath"))
        url = normalize_text(item.get("url") or item.get("sourceUrl") or item.get("link"))
        yield SourceItem(
            id=source_id,
            title=title,
            body=body,
            source_kind=source_kind,
            source_date=source_date,
            path=path,
            url=url,
            metadata=item,
        )


def _sources_from_markdown_dir(
    directory: Path,
    source_kind: str,
    exclude_dirs: set[str] | None = None,
) -> Iterable[SourceItem]:
    if not directory.exists():
        raise FileNotFoundError(f"local source directory not found: {directory}")
    if not directory.is_dir():
        raise NotADirectoryError(f"local source path is not a directory: {directory}")
    ignored = exclude_dirs or set()
    for path in sorted(directory.rglob("*")):
        if any(part in ignored for part in path.parts):
            continue
        if any(part.startswith(".") for part in path.relative_to(directory).parts[:-1]):
            continue
        if path.suffix.lower() not in {".md", ".markdown", ".txt"}:
            continue
        body = path.read_text(encoding="utf-8", errors="replace")
        title = _markdown_title(body) or path.stem
        yield SourceItem(
            id=f"file:{content_hash(title, body)[:12]}",
            title=title,
            body=body,
            source_kind=source_kind,
            path=str(path),
        )


def _markdown_title(body: str) -> str:
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return _clean_markdown_title(stripped.lstrip("#").strip())
        if stripped:
            return _clean_markdown_title(stripped[:80])
    return ""


def _clean_markdown_title(value: str) -> str:
    title = value.strip()
    while len(title) >= 2 and title[0] in {"*", "_", "`"} and title[-1] == title[0]:
        title = title[1:-1].strip()
    return title
