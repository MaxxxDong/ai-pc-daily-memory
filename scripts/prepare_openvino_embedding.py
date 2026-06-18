#!/usr/bin/env python3
"""Download or convert an embedding model into a local OpenVINO directory."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path


DEFAULT_MODEL_ID = os.environ.get("AIPC_OPENVINO_EMBED_MODEL_ID", "BAAI/bge-small-zh-v1.5")
DEFAULT_OUTPUT = os.environ.get("AIPC_OPENVINO_EMBED_MODEL_DIR", "models/openvino/bge-small-zh-v1.5")


def build_command(args: argparse.Namespace) -> list[str]:
    cmd = [
        args.optimum_cli,
        "export",
        "openvino",
        "--task",
        args.task,
        "--model",
        args.model_id,
    ]
    if args.trust_remote_code:
        cmd.append("--trust-remote-code")
    cmd.append(args.output)
    return cmd


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-id", default=DEFAULT_MODEL_ID, help="Hub model id or local model directory to export.")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Local OpenVINO output directory.")
    parser.add_argument("--task", default="feature-extraction", help="Optimum export task for embedding models.")
    parser.add_argument("--optimum-cli", default=os.environ.get("OPTIMUM_CLI", "optimum-cli"), help="optimum-cli executable path or name.")
    parser.add_argument("--trust-remote-code", action="store_true", help="Forward --trust-remote-code to optimum-cli when required by a chosen model.")
    parser.add_argument("--dry-run", action="store_true", help="Print the export command without downloading or converting.")
    args = parser.parse_args()

    optimum_path = shutil.which(args.optimum_cli) or args.optimum_cli
    cmd = build_command(argparse.Namespace(**{**vars(args), "optimum_cli": optimum_path}))
    output_path = Path(args.output)

    if not args.dry_run and not shutil.which(args.optimum_cli) and not Path(args.optimum_cli).exists():
        raise SystemExit("optimum-cli not found. Install optional deps with: python -m pip install -r requirements-openvino.txt")

    if args.dry_run:
        result = {"returncode": 0, "stdout": "", "stderr": "", "dryRun": True}
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        completed = subprocess.run(cmd, check=False, text=True, capture_output=True)
        result = {
            "returncode": completed.returncode,
            "stdout": completed.stdout.strip(),
            "stderr": completed.stderr.strip(),
            "dryRun": False,
        }

    expected_files = ["openvino_model.xml", "openvino_model.bin", "config.json"]
    existing = [name for name in expected_files if (output_path / name).exists()]
    summary = {
        "ok": bool(args.dry_run or (result["returncode"] == 0 and "openvino_model.xml" in existing)),
        "modelId": args.model_id,
        "output": str(output_path),
        "command": cmd,
        "result": result,
        "existingExpectedFiles": existing,
        "nextCommand": f"python scripts/local_ai_rerank.py --backend openvino --model {output_path} --memory-home .aipc-work-memory --query \"今天会议 今天要做什么\" --output out/local_rerank.json",
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
