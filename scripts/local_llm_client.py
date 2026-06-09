from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


SYSTEM_PROMPT = """You organize private local work memory.
Return one JSON object only. Do not wrap it in Markdown.
Do not invent facts. If a source is inaccessible or thin, say so explicitly in summary or dailySynthesis.
Do not convert ordinary article content into tasks unless the source clearly asks the user to act.
Future-dated work is still a task or follow-up, not a discarded defer item.
"""


def build_daily_prompt(request: dict[str, Any], context_blocks: list[str]) -> str:
    request_id = request.get("id") or request.get("requestId") or "daily-request"
    date = request.get("date") or ""
    objective = request.get("objective") or request.get("mode") or "daily organize"
    context = "\n\n".join(context_blocks)
    return f"""
Request:
- requestId: {request_id}
- date: {date}
- objective: {objective}

DailyResult schema:
{{
  "requestId": "string",
  "summary": "string",
  "themes": ["string"],
  "ideas": ["string"],
  "tasks": ["string"],
  "taskReferences": [
    {{"task": "string", "sourceTitle": "string", "sourceNoteId": "string", "sourceDate": "string", "note": "string"}}
  ],
  "schedule": [
    {{"time": "string", "title": "string", "description": "string", "location": "string", "link": "string", "sourceTitle": "string"}}
  ],
  "defer": ["string"],
  "links": ["string"],
  "dailySynthesis": ["string"],
  "kindleCard": {{"title": "string", "body": "string"}}
}}

Local retrieved context:
{context}
""".strip()


def call_local_llm(prompt: str, timeout: int = 120) -> dict[str, Any]:
    base_url = os.environ.get("AIPC_LLM_BASE_URL", "http://localhost:11434/v1").rstrip("/")
    validate_local_base_url(base_url)
    model = os.environ.get("AIPC_LLM_MODEL", "qwen3.6-35b-a3b")
    api_key = os.environ.get("AIPC_LLM_API_KEY", "local")
    url = f"{base_url}/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.URLError as exc:
        raise RuntimeError(f"local LLM endpoint unavailable: {url}; {exc}") from exc

    data = json.loads(raw)
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("local LLM response did not contain choices[0].message.content") from exc
    return parse_json_object(content)


def validate_local_base_url(base_url: str) -> None:
    parsed = urllib.parse.urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in LOCAL_HOSTS:
        raise ValueError("AIPC_LLM_BASE_URL must use localhost, 127.0.0.1, or ::1")


def parse_json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("model output does not contain a JSON object")
    value = json.loads(cleaned[start : end + 1])
    if not isinstance(value, dict):
        raise ValueError("model output JSON must be an object")
    return value
