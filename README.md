# AI PC Daily Memory

AI PC Daily Memory is a local-first Agent Skill for turning explicitly configured notes, Markdown folders, Obsidian vaults, schedules, links, DingTalk, and Feishu sources into a private daily memory.

It is built for the ModelScope AI PC Agent Skills activity: a local `<=35B` agent acts as the brain, calls this skill's scripts as local tools, prepares RAG context, optionally reranks memory sources with localhost/OpenVINO embeddings, and saves a validated `DailyResult`.

## Quick Verification

Run the offline judge path from the repository root:

```bash
python3 scripts/verify_submission.py
```

This does not require DingTalk, Feishu, Codex, network access, or a cloud model. It verifies:

- configured source sync
- local rerank
- `DailyResult` schema validation
- final daily memory save-back
- import record generation

Run the test suite:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip pytest
python -m pytest tests -q
```

## Local Model Setup

The contest path uses a local `<=35B` model as the Agent brain. If the judge or user runs the package outside an existing Agent host, pull and verify the Ollama model with:

```bash
python scripts/download_ollama_model.py --model qwen3.6-35b-a3b
```

If the contest model is published under a different Ollama registry name, pass that exact name with `--model`. The standalone local LLM client reads `AIPC_LLM_BASE_URL` and `AIPC_LLM_MODEL`; keep the base URL on localhost, for example `http://localhost:11434/v1`.

## Optional OpenVINO Rerank

Default verification uses the deterministic `token` backend. To capture OpenVINO evidence, install optional dependencies and create a local OpenVINO embedding model directory:

```bash
python -m pip install -r requirements-openvino.txt
python scripts/prepare_openvino_embedding.py \
  --model-id BAAI/bge-small-zh-v1.5 \
  --output models/openvino/bge-small-zh-v1.5

python scripts/verify_submission.py \
  --embedding-backend openvino \
  --embedding-model models/openvino/bge-small-zh-v1.5
```

The OpenVINO model path must be local. The code uses `local_files_only=True` and does not download remote models in the contest path.

## Repository Layout

| Path | Purpose |
| --- | --- |
| `SKILL.md` | Main Agent Skill instructions |
| `AGENT_RUNBOOK.md` | Single-file runbook for local agents and judges |
| `model.json` | ModelScope Skill metadata |
| `scripts/` | Local source sync, model setup, rerank, validation, and save-back tools |
| `examples/` | Offline demo, prompt, sample config, and OpenVINO notes |
| `tests/` | Deterministic pytest coverage |
| `docs/submission-checklist.md` | ModelScope submission checklist |
| `docs/submission-article-draft.md` | Draft technical article |

## Safety Boundaries

- No full-disk, home-folder, or all-cloud-doc scans.
- Only configured folders, vaults, links, tokens, node IDs, and calendar ranges are read.
- Private DingTalk/Feishu reads fail explicitly when unavailable.
- Remote embedding/model APIs are not used in the contest path.

## ModelScope Submission

Create a clean zip from tracked files only:

```bash
git archive --format=zip -o ai-pc-daily-memory-submission.zip HEAD
```

Upload the zip or the repository root to ModelScope Skills Center and add the `AIPC` tag.
