# OpenVINO Rerank Demo

This optional demo shows the contest-facing local AI tool path. The default offline verification uses the deterministic `token` backend; this demo switches the same tool to a local OpenVINO embedding model directory.

## Requirements

- Python 3.10+
- A local OpenVINO embedding model directory already available on disk
- Optional dependencies installed from `requirements-openvino.txt`

Install optional dependencies and export a local embedding model:

```bash
python -m pip install -r requirements-openvino.txt
python scripts/prepare_openvino_embedding.py \
  --model-id BAAI/bge-small-zh-v1.5 \
  --output models/openvino/bge-small-zh-v1.5
```

The model directory must be local. Do not use a remote model endpoint for the contest path. A valid directory should contain tokenizer files and OpenVINO model files that `transformers.AutoTokenizer.from_pretrained(..., local_files_only=True)` and `OVModelForFeatureExtraction.from_pretrained(..., local_files_only=True)` can load.

## Run

First create local memory with the built-in demo:

```bash
python scripts/verify_submission.py
```

The command prints a `workDir`. Re-run rerank against that generated memory:

```bash
python scripts/local_ai_rerank.py \
  --memory-home <WORK_DIR>/demo-workday/.aipc-work-memory \
  --query "AI PC Skill 提交 今日会议 今天看的文章" \
  --backend openvino \
  --model models/openvino/bge-small-zh-v1.5 \
  --output <WORK_DIR>/demo-workday/out/openvino_rerank.json
```

Or run one-command verification with OpenVINO:

```bash
python scripts/verify_submission.py \
  --embedding-backend openvino \
  --embedding-model models/openvino/bge-small-zh-v1.5
```

## Evidence To Capture

- Terminal output from `verify_submission.py` showing `ok: true` and `backend: openvino`
- `out/openvino_rerank.json` or `out/local_rerank.json`
- `out/daily_context.md`
- `out/final_daily_memory.md`

The important scoring point is that the Agent uses a `<=35B` local model as its brain, then calls a local AI tool (`local_ai_rerank.py`) backed by OpenVINO embeddings over private local memory.
