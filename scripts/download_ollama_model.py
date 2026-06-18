#!/usr/bin/env python3
"""Download and verify the local Ollama model used as the Agent brain."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path


DEFAULT_MODEL = os.environ.get("AIPC_LLM_MODEL", "qwen3.6-35b-a3b")


def run(cmd: list[str], dry_run: bool) -> dict[str, object]:
    if dry_run:
        return {"cmd": cmd, "returncode": 0, "dryRun": True}
    completed = subprocess.run(cmd, check=False, text=True, capture_output=True)
    return {
        "cmd": cmd,
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Ollama model name to pull. Defaults to AIPC_LLM_MODEL or qwen3.6-35b-a3b.")
    parser.add_argument("--ollama-bin", default=os.environ.get("OLLAMA_BIN", "ollama"), help="Ollama executable path or name.")
    parser.add_argument("--output", default="", help="Optional JSON summary output path.")
    parser.add_argument("--dry-run", action="store_true", help="Print commands without downloading.")
    parser.add_argument("--skip-pull", action="store_true", help="Only verify the model with `ollama show`.")
    args = parser.parse_args()

    ollama_path = shutil.which(args.ollama_bin) or args.ollama_bin
    commands: list[dict[str, object]] = []

    if not args.dry_run and not shutil.which(args.ollama_bin) and not Path(args.ollama_bin).exists():
        raise SystemExit(f"Ollama executable not found: {args.ollama_bin}")

    commands.append(run([ollama_path, "--version"], args.dry_run))
    if not args.skip_pull:
        commands.append(run([ollama_path, "pull", args.model], args.dry_run))
    commands.append(run([ollama_path, "show", args.model], args.dry_run))

    failed = [item for item in commands if item.get("returncode") != 0]
    summary = {
        "ok": not failed,
        "model": args.model,
        "ollama": ollama_path,
        "commands": commands,
        "notes": [
            "Keep AIPC_LLM_BASE_URL on localhost, for example http://localhost:11434/v1.",
            "If the contest model is published under a different Ollama registry name, rerun with --model <name>.",
        ],
    }
    text = json.dumps(summary, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
