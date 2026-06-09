from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from local_llm_client import build_daily_prompt, call_local_llm
from memory_store import load_memory_sources, resolve_memory_home
from rag_retriever import retrieve_context
from source_loader import SourceItem, dedupe_sources, extract_urls, load_request_sources
from validate_daily_result import assert_valid_result


ACTION_RE = re.compile(
    r"^\s*[-*]?\s*(TODO|todo|待办|行动项|要做)[:：]"
)
FUTURE_ACTION_RE = re.compile(
    r"^\s*(明天|后天|下周|下个月|\d{4}-\d{1,2}-\d{1,2}).{0,12}(跟进|完成|处理|确认|提交|整理|复盘|预约)"
)
DEFER_RE = re.compile(r"(暂缓|搁置|以后再说|先不做|低优先级|blocked|waiting)", re.IGNORECASE)
CHECKBOX_RE = re.compile(r"^\s*[-*]\s*\[[ xX]?\]\s*")


def organize(
    input_path: str | Path,
    mock: bool = False,
    top_k: int = 8,
    notes_dirs: list[str] | None = None,
    source_dirs: list[str] | None = None,
    memory_home: str | None = None,
) -> dict[str, Any]:
    request, sources = load_request_sources(input_path, notes_dirs=notes_dirs, source_dirs=source_dirs)
    sources.extend(load_memory_sources(resolve_memory_home(memory_home)))
    sources = dedupe_sources(sources)
    query = build_query(request, sources)
    retrieved = retrieve_context(query, sources, limit=top_k)
    if mock:
        result = build_mock_result(request, retrieved, len(sources))
    else:
        prompt = build_daily_prompt(request, [source.prompt_block() for source in retrieved])
        result = call_local_llm(prompt)
    assert_valid_result(result)
    return result


def build_query(request: dict[str, Any], sources: list[SourceItem]) -> str:
    parts = [
        str(request.get("objective") or ""),
        str(request.get("mode") or ""),
        str(request.get("date") or ""),
    ]
    parts.extend(source.title for source in sources[:20])
    return "\n".join(part for part in parts if part)


def build_mock_result(request: dict[str, Any], sources: list[SourceItem], source_count: int) -> dict[str, Any]:
    request_id = str(request.get("id") or request.get("requestId") or "daily-request")
    tasks, refs, future = extract_tasks(sources)
    defer = extract_defer(sources)
    ideas = extract_ideas(sources)
    schedule = extract_schedule(sources)
    links = extract_all_links(sources)
    themes = extract_themes(sources)
    synthesis = [
        f"已从 {source_count} 条本地来源中召回 {len(sources)} 条相关材料，并按内容 hash 去重。",
        "本结果由 mock 模式生成，用于稳定演示 Skill 的读取、召回、整理和校验闭环。",
    ]
    if future:
        synthesis.append("包含未来日期或后续跟进事项；这些事项仍作为待办/后续事项处理，不归入暂缓。")
    if not tasks:
        synthesis.append("未发现明确行动语义；普通文章或资料内容不会被伪装成待办。")
    if links:
        synthesis.append("检测到链接来源，已集中放入 links 字段，避免在摘要中重复展开。")

    summary = f"已整理本地工作记忆：{len(themes)} 个主题、{len(tasks)} 个待办、{len(schedule)} 条日程。"
    return {
        "requestId": request_id,
        "summary": summary,
        "themes": themes,
        "ideas": ideas,
        "tasks": tasks,
        "taskReferences": refs,
        "schedule": schedule,
        "defer": defer,
        "links": links,
        "dailySynthesis": synthesis,
        "kindleCard": {
            "title": "今日工作记忆",
            "body": "\n".join([summary, *tasks[:3]]) if tasks else summary,
        },
    }


def extract_tasks(sources: list[SourceItem]) -> tuple[list[str], list[dict[str, str]], list[str]]:
    tasks: list[str] = []
    refs: list[dict[str, str]] = []
    future: list[str] = []
    seen: set[str] = set()
    for source in sources:
        if source.source_kind == "schedule":
            continue
        lines = source.body.splitlines()
        if source.source_kind == "task" and not lines:
            lines = [source.title]
        for line in lines:
            if line.strip().startswith("#"):
                continue
            candidate = normalize_task_line(line)
            if not candidate:
                continue
            explicit_task_source = source.source_kind == "task"
            explicit_action_line = bool(ACTION_RE.search(line) or CHECKBOX_RE.search(line) or FUTURE_ACTION_RE.search(line))
            if not (explicit_task_source or explicit_action_line):
                continue
            if source.source_kind == "source-document" and not (ACTION_RE.search(line) or CHECKBOX_RE.search(line)):
                continue
            if not explicit_action_line and len(candidate) > 80:
                continue
            normalized = normalize_for_dedupe(candidate)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            tasks.append(candidate)
            if re.search(r"(明天|后天|下周|下个月|\d{4}-\d{1,2}-\d{1,2})", candidate):
                future.append(candidate)
            refs.append(
                {
                    "task": candidate,
                    "sourceTitle": source.title,
                    "sourceNoteId": source.id,
                    "sourceDate": source.source_date,
                    "note": "来源中包含明确行动或排期语义。",
                }
            )
    return tasks[:12], refs[:12], future


def extract_defer(sources: list[SourceItem]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for source in sources:
        for line in source.body.splitlines():
            stripped = line.strip()
            if not stripped or not DEFER_RE.search(stripped):
                continue
            normalized = normalize_for_dedupe(stripped)
            if normalized in seen:
                continue
            seen.add(normalized)
            result.append(stripped[:120])
    return result[:8]


def extract_ideas(sources: list[SourceItem]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for source in sources:
        for line in source.body.splitlines():
            if line.strip().startswith("#"):
                continue
            stripped = line.strip(" -\t")
            if not stripped or len(stripped) > 140:
                continue
            if not re.search(r"(想法|灵感|可以|建议|机会|方案)", stripped):
                continue
            normalized = normalize_for_dedupe(stripped)
            if normalized in seen:
                continue
            seen.add(normalized)
            result.append(stripped)
    return result[:8]


def extract_schedule(sources: list[SourceItem]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for source in sources:
        if source.source_kind != "schedule":
            continue
        metadata = source.metadata or {}
        result.append(
            {
                "time": str(metadata.get("time") or metadata.get("start") or metadata.get("startTime") or source.source_date),
                "title": source.title,
                "description": source.body,
                "location": str(metadata.get("location") or ""),
                "link": str(metadata.get("link") or metadata.get("url") or source.url),
                "sourceTitle": source.title,
            }
        )
    return result[:12]


def extract_all_links(sources: list[SourceItem]) -> list[str]:
    seen: set[str] = set()
    links: list[str] = []
    for source in sources:
        for url in [source.url, *extract_urls(source.text)]:
            if url and url not in seen:
                seen.add(url)
                links.append(url)
    return links[:20]


def extract_themes(sources: list[SourceItem]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for source in sources:
        title = source.title.strip()
        if not title:
            continue
        title = title[:40]
        normalized = normalize_for_dedupe(title)
        if normalized in seen:
            continue
        seen.add(normalized)
        result.append(title)
    return result[:5] or ["本地工作记忆"]


def normalize_task_line(line: str) -> str:
    stripped = CHECKBOX_RE.sub("", line).strip(" -\t")
    stripped = re.sub(r"^(TODO|todo|待办|行动项|要做)[:：]\s*", "", stripped).strip()
    return stripped[:160]


def normalize_for_dedupe(text: str) -> str:
    return re.sub(r"\s+", "", text).lower()


def render_markdown(result: dict[str, Any]) -> str:
    lines = [
        f"# {result['kindleCard']['title']}",
        "",
        result["summary"],
        "",
        "## 待办",
    ]
    lines.extend(f"- [ ] {task}" for task in result["tasks"])
    lines.extend(["", "## 日程"])
    lines.extend(f"- {item['time']} {item['title']}".strip() for item in result["schedule"])
    lines.extend(["", "## 信息归纳"])
    lines.extend(f"- {item}" for item in result["dailySynthesis"])
    lines.extend(["", "## 来源链接"])
    lines.extend(f"- {url}" for url in result["links"])
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Organize local work memory into DailyResult JSON.")
    parser.add_argument("--input", required=True, help="DailyRequest JSON path.")
    parser.add_argument("--output", required=True, help="Output DailyResult JSON path.")
    parser.add_argument("--markdown-output", help="Optional clean Markdown summary output path.")
    parser.add_argument("--mock", action="store_true", help="Run deterministic local demo without an LLM.")
    parser.add_argument("--top-k", type=int, default=8, help="Number of retrieved source items.")
    parser.add_argument("--notes-dir", action="append", default=[], help="Extra local notes directory.")
    parser.add_argument("--sources-dir", action="append", default=[], help="Extra local source-documents directory.")
    parser.add_argument("--memory-home", help="Optional skill-owned memory store directory to include.")
    args = parser.parse_args()

    result = organize(
        args.input,
        mock=args.mock,
        top_k=args.top_k,
        notes_dirs=args.notes_dir,
        source_dirs=args.sources_dir,
        memory_home=args.memory_home,
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.markdown_output:
        markdown_path = Path(args.markdown_output)
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(render_markdown(result), encoding="utf-8")

    print(f"OK: wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
