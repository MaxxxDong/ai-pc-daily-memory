# Demo Workday

This demo uses only local files and explicit links. It does not require DingTalk, Feishu, Codex, or network access.

Run:

```bash
cd examples/demo-workday
python ../../scripts/sync_work_memory.py --config config.json
python ../../scripts/local_ai_rerank.py \
  --memory-home .aipc-work-memory \
  --query "AI PC Skill 提交 今日会议 今天看的文章" \
  --backend token \
  --output out/local_rerank.json
```

Then ask the local AI PC agent to read `out/daily_context.md` with `../agent_prompt.daily_result.md` and write `out/daily_result.json`.

Validate and save:

```bash
python ../../scripts/validate_daily_result.py out/daily_result.json
python ../../scripts/save_daily_result.py \
  --input out/daily_result.json \
  --date 2026-06-09 \
  --markdown-output out/daily_memory.md
```
