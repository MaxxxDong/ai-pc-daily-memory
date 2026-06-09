---
name: ai-pc-daily-memory
description: Use when an AI PC agent needs to turn explicitly configured local, DingTalk, Feishu, Obsidian, schedule, note, or link sources into a private daily memory.
---

# AI PC Daily Memory

Use this as the dispatcher skill for local-first work memory. Route the user's request to source ingestion, LLM WIKI knowledge extraction, daily organization, or result validation instead of treating every task as one monolithic workflow.

This skill is model-agnostic. It does not depend on Codex, a cloud model, a specific notebook app, or a hard-coded model name. In the normal ModelScope / AI PC flow, the agent already has a local `<=35B` model as its brain; that agent calls this skill's scripts to prepare local RAG context, then the agent itself generates the final `DailyResult`.

For a single-file runbook covering offline/online, DingTalk, Feishu, local folders, Obsidian, local rerank, and final save-back states, read `AGENT_RUNBOOK.md` first.

`AIPC_LLM_BASE_URL` and `AIPC_LLM_MODEL` are optional standalone CLI variables only. Use them when running this package outside an agent host and you want `organize_daily.py` to call a local OpenAI-compatible endpoint by itself.

## Dispatch

If the host supports multiple skills, dispatch to these sibling skills:

- `ai-pc-source-ingest`: local text/files/folders, Obsidian, Feishu/Lark CLI, DingTalk CLI.
- `ai-pc-llm-wiki-memory`: durable LLM WIKI extraction and accepted knowledge storage.
- `ai-pc-daily-organizer`: daily context preparation, result validation, and result save-back.

If the user wants "pull my configured work materials and organize today", start from the explicit config flow. The config must name the exact local folders, Obsidian vaults, DingTalk documents/calendar/todos, and Feishu resources to read. Broad scans are not supported.

For contest judging or pre-submit verification, run `python scripts/verify_submission.py` from this skill directory. It exercises offline source sync, local rerank, DailyResult validation, and save-back without requiring DingTalk, Feishu, Codex, or network access.

```powershell
python scripts\sync_work_memory.py --config examples\work_memory_config.sample.json
```

This writes configured sources into the chosen `memoryHome`, records lightweight import status in `import_records.jsonl`, then prepares `wikiContext`, `dailyContext`, and optional `dailyMarkdown` outputs. The calling AI PC agent reads `dailyContext`, generates `DailyResult`, validates it, and saves it.

If the host only loads this dispatcher skill, call the same scripts directly:

1. Source request -> `ingest_memory.py`, `ingest_feishu_cli.py`, or `ingest_dingtalk_cli.py`.
2. Knowledge request -> `prepare_wiki_context.py`, then `save_wiki_items.py`.
3. Daily organization request -> `prepare_daily_context.py`, then validate and save the generated result.
4. Local AI tool request -> `local_ai_rerank.py` with `token`, `localhost-embeddings`, or `openvino` backend.

Do not duplicate business logic across subskills. All paths share `.aipc-work-memory/`, content-hash dedupe, and the same `DailyResult` shape.

Primary agent-hosted flow, without any notebook app:

```powershell
python scripts\ingest_memory.py --text "待办：完成 AIPC Skill 演示。明天跟进：补技术文章。" --title "今天的想法" --date 2026-06-08
python scripts\prepare_daily_context.py --date 2026-06-08 --output out\daily_context.md
# The calling AI PC agent reads out\daily_context.md and generates out\daily_result.json.
python scripts\validate_daily_result.py out\daily_result.json
python scripts\save_daily_result.py --input out\daily_result.json --date 2026-06-08 --markdown-output out\daily_memory.md
```

Supported source adapters:

```powershell
# Local Markdown/text folder
python scripts\ingest_memory.py --local-markdown-dir D:\Notes --date 2026-06-08

# Obsidian vault, skipping .obsidian and hidden folders
python scripts\ingest_memory.py --obsidian-vault D:\ObsidianVault --date 2026-06-08

# Feishu/Lark through an already logged-in lark-cli
python scripts\ingest_feishu_cli.py --auth-status
python scripts\ingest_feishu_cli.py --doc-token <TOKEN> --date 2026-06-08
python scripts\ingest_feishu_cli.py --minutes-token <TOKEN> --date 2026-06-08
python scripts\ingest_feishu_cli.py --agenda --date 2026-06-08

# DingTalk through the official dws CLI, already logged in with dws auth login
python scripts\ingest_dingtalk_cli.py --cli tools\dws\dws --auth-status
python scripts\ingest_dingtalk_cli.py --cli tools\dws\dws --doc-url "https://alidocs.dingtalk.com/i/nodes/xxx" --date 2026-06-08
python scripts\ingest_dingtalk_cli.py --cli tools\dws\dws --node-id "<NODE_ID_OR_URL>" --date 2026-06-08
python scripts\ingest_dingtalk_cli.py --cli tools\dws\dws --workbook-node-id "<SHEET_NODE_ID_OR_URL>" --range "A1:Z80" --date 2026-06-08
python scripts\ingest_dingtalk_cli.py --cli tools\dws\dws --calendar-events --start "2026-06-08T00:00:00+08:00" --end "2026-06-09T00:00:00+08:00" --date 2026-06-08
python scripts\ingest_dingtalk_cli.py --cli tools\dws\dws --todo-open --date 2026-06-08

# Feishu/Lark exported Markdown or copied content as a fallback only
python scripts\ingest_memory.py --feishu-file D:\Exports\meeting.md --feishu-kind meeting --date 2026-06-08
python scripts\ingest_memory.py --feishu-text "飞书日程或文档内容..." --feishu-kind document --title "飞书文档" --date 2026-06-08
```

External-source rule: prefer login-state CLI or MCP first, then exported local files, and use pasted text only as the last fallback. The skill never pretends a private document was read when the CLI/MCP cannot access it.

Local AI rerank tool:

```powershell
python scripts\local_ai_rerank.py --memory-home .aipc-work-memory --query "今天会议 今天要做什么 今天看的文章" --backend token --output out\local_rerank.json
```

Use `token` for deterministic tests. For an AI PC demo, use `localhost-embeddings` against a local embedding endpoint or `openvino` against a local OpenVINO embedding model directory. Never call a remote embedding API in the contest path.

Configured sync supports these source controls:

- `mode: "all"` imports all Markdown/text files under that configured folder.
- `mode: "modifiedToday"` imports only files whose modified date equals `date`, using `timezone` when provided.
- `mode: "explicitFiles"` imports only files listed in `files`.
- `links` imports only explicitly configured URL/title/summary items; it does not silently crawl the web.

LLM WIKI flow:

```powershell
python scripts\prepare_wiki_context.py --date 2026-06-08 --output out\wiki_context.md
# The calling agent reads out\wiki_context.md and writes out\wiki_items.json.
python scripts\save_wiki_items.py --input out\wiki_items.json
python scripts\prepare_daily_context.py --date 2026-06-08 --output out\daily_context.md
```

Sample request flow for deterministic repository tests:

```powershell
python scripts\prepare_daily_context.py --input examples\daily_request.sample.json --output out\daily_context.md
```

Run the deterministic demo without a model:

```powershell
python scripts\organize_daily.py --input examples\daily_request.sample.json --output out\daily_result.json --markdown-output out\daily_summary.md --mock
python scripts\validate_daily_result.py out\daily_result.json
```

Standalone local-endpoint mode is optional. Run with a local OpenAI-compatible endpoint by omitting `--mock` and setting `AIPC_LLM_BASE_URL` / `AIPC_LLM_MODEL`.

## Output Rules

- Do not invent facts or pretend inaccessible sources were read.
- Never scan all local files, all home folders, or all cloud documents. Only read paths, vaults, tokens, node ids, calendars, and tasks that are explicitly configured or requested.
- Do not require Codex, Codex CLI, or a desktop sticky-note app in the ModelScope path.
- Keep model/tool calls local. `localhost-embeddings` must use localhost and `openvino` must use a local model directory.
- Do not classify ordinary article/document content as tasks unless it contains explicit action intent.
- If a note says "tomorrow", "next week", or a specific future date, keep it as a future task or follow-up, not as a discarded defer item.
- Use `defer` only for intentionally paused, blocked, or low-priority items.
- Keep source references concise and traceable.
- Return JSON that matches the bundled `DailyResult` shape before generating Markdown.
