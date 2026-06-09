from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from rag_retriever import retrieve_context
from source_loader import dedupe_sources, load_request_sources
from memory_store import load_memory_sources, resolve_memory_home
from wiki_store import load_wiki_items


DAILY_RESULT_SCHEMA = {
    "requestId": "string",
    "summary": "string",
    "themes": ["string"],
    "ideas": ["string"],
    "tasks": ["string"],
    "taskReferences": [
        {
            "task": "string",
            "sourceTitle": "string",
            "sourceNoteId": "string",
            "sourceDate": "string",
            "note": "string",
        }
    ],
    "schedule": [
        {
            "time": "string",
            "title": "string",
            "description": "string",
            "location": "string",
            "link": "string",
            "sourceTitle": "string",
        }
    ],
    "defer": ["string"],
    "links": ["string"],
    "dailySynthesis": ["string"],
    "kindleCard": {"title": "string", "body": "string"},
}


def prepare_context(
    input_path: str | Path | None = None,
    top_k: int = 8,
    notes_dirs: list[str] | None = None,
    source_dirs: list[str] | None = None,
    memory_home: str | Path | None = None,
    date: str = "",
    objective: str = "Organize local work memory into a DailyResult.",
) -> str:
    request = {
        "requestId": f"work-memory-{date or 'latest'}",
        "date": date,
        "mode": "agent-owned-local-memory",
        "objective": objective,
    }
    sources = load_memory_sources(resolve_memory_home(memory_home))
    if input_path:
        request, request_sources = load_request_sources(input_path, notes_dirs=notes_dirs, source_dirs=source_dirs)
        sources.extend(request_sources)
    sources = dedupe_sources(sources)
    query = "\n".join(
        str(part)
        for part in [
            request.get("objective") or "",
            request.get("mode") or "",
            request.get("date") or "",
            *(source.title for source in sources[:20]),
        ]
        if part
    )
    retrieved = retrieve_context(query, sources, limit=top_k)
    wiki_items = load_wiki_items(memory_home)
    blocks = [
        "# Local Work Memory Context",
        "",
        "Use this context to generate one DailyResult JSON object. Do not invent facts.",
        "",
        "## Request",
        "",
        json.dumps(
            {
                "requestId": request.get("requestId") or request.get("id") or f"work-memory-{date or 'latest'}",
                "date": request.get("date") or date,
                "mode": request.get("mode") or "",
                "objective": request.get("objective") or "",
                "memoryHome": str(resolve_memory_home(memory_home)),
                "totalSourcesAfterDedupe": len(sources),
                "retrievedSources": len(retrieved),
                "acceptedWikiItems": len(wiki_items),
            },
            ensure_ascii=False,
            indent=2,
        ),
        "",
        "## Required DailyResult Shape",
        "",
        json.dumps(DAILY_RESULT_SCHEMA, ensure_ascii=False, indent=2),
        "",
        "## Rules",
        "",
        "- Ordinary article or document content is not a task unless it has explicit action intent.",
        "- Future-dated work such as tomorrow follow-up remains a task or follow-up, not defer.",
        "- Use defer only for intentionally paused, blocked, or low-priority items.",
        "- Keep links in the links field instead of scattering them through all sections.",
        "- Cite task sources through taskReferences.",
        "- Use LLM WIKI items as durable background context, but keep daily tasks grounded in retrieved sources.",
        "",
        "## Accepted LLM WIKI Knowledge",
    ]
    for item in wiki_items[:30]:
        blocks.extend(["", f"- [{item.kind}] {item.title}: {item.summary}"])
    blocks.extend([
        "",
        "## Retrieved Local Sources",
    ])
    for index, source in enumerate(retrieved, start=1):
        blocks.extend(["", f"<!-- source {index} -->", source.prompt_block()])
    return "\n".join(blocks).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare local RAG context for an agent-hosted LLM.")
    parser.add_argument("--input", help="Optional DailyRequest JSON path. If omitted, use the skill-owned memory store.")
    parser.add_argument("--output", required=True, help="Markdown context output path for the calling agent.")
    parser.add_argument("--memory-home", help="Local memory store directory. Defaults to .aipc-work-memory or AIPC_WORK_MEMORY_HOME.")
    parser.add_argument("--date", default="", help="Date label for memory-only requests, for example 2026-06-08.")
    parser.add_argument("--objective", default="Organize local work memory into a DailyResult.", help="User objective for the calling agent.")
    parser.add_argument("--top-k", type=int, default=8, help="Number of retrieved source items.")
    parser.add_argument("--notes-dir", action="append", default=[], help="Extra local notes directory.")
    parser.add_argument("--sources-dir", action="append", default=[], help="Extra local source-documents directory.")
    args = parser.parse_args()

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        prepare_context(
            args.input,
            top_k=args.top_k,
            notes_dirs=args.notes_dir,
            source_dirs=args.sources_dir,
            memory_home=args.memory_home,
            date=args.date,
            objective=args.objective,
        ),
        encoding="utf-8",
    )
    print(f"OK: wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
