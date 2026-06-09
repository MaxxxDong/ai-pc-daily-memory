from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent


class VerificationError(RuntimeError):
    pass


def run_command(label: str, command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=str(cwd), text=True, capture_output=True)
    if result.returncode != 0:
        details = "\n".join(
            part
            for part in [
                f"step failed: {label}",
                f"command: {' '.join(command)}",
                result.stdout.strip(),
                result.stderr.strip(),
            ]
            if part
        )
        raise VerificationError(details)
    return result


def require_file(path: Path, label: str) -> None:
    if not path.is_file() or path.stat().st_size == 0:
        raise VerificationError(f"missing or empty {label}: {path}")


def prepare_demo(work_dir: Path) -> Path:
    source = SKILL_ROOT / "examples" / "demo-workday"
    target = work_dir / "demo-workday"
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target, ignore=shutil.ignore_patterns(".aipc-work-memory", "out"))
    return target


def verify_rerank_output(path: Path) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("localOnly") is not True:
        raise VerificationError("local_rerank.json must declare localOnly=true")
    if not data.get("results"):
        raise VerificationError("local_rerank.json must contain at least one result")


def run_verification(argv: list[str] | None = None) -> dict[str, Any]:
    parser = argparse.ArgumentParser(description="Run one-command verification for the AI PC Daily Memory skill.")
    parser.add_argument("--work-dir", default="", help="Optional directory for verification outputs. Defaults to a temp directory.")
    parser.add_argument("--cleanup", action="store_true", help="Delete the generated temp verification directory before exit.")
    parser.add_argument("--quiet", action="store_true", help="Only print the final JSON summary.")
    parser.add_argument(
        "--embedding-backend",
        default="token",
        choices=["token", "localhost-embeddings", "openvino"],
        help="Rerank backend. token is deterministic; use openvino/localhost for AI PC evidence.",
    )
    parser.add_argument(
        "--embedding-endpoint",
        default="http://localhost:11434/v1/embeddings",
        help="Localhost embedding endpoint for localhost-embeddings backend.",
    )
    parser.add_argument(
        "--embedding-model",
        default="",
        help="Embedding model name for localhost endpoint, or local OpenVINO model directory.",
    )
    args = parser.parse_args(argv)

    if args.embedding_backend == "openvino" and not args.embedding_model:
        raise VerificationError("--embedding-model must point to a local OpenVINO model directory when backend=openvino")
    if args.embedding_backend == "localhost-embeddings" and not args.embedding_model:
        raise VerificationError("--embedding-model is required when backend=localhost-embeddings")

    temp_root: Path | None = None
    if args.work_dir:
        work_dir = Path(args.work_dir).expanduser().resolve()
        work_dir.mkdir(parents=True, exist_ok=True)
    else:
        temp_root = Path(tempfile.mkdtemp(prefix="aipc-skill-verify-"))
        work_dir = temp_root

    demo_dir = prepare_demo(work_dir)
    output_dir = demo_dir / "out"

    run_command("sync configured demo sources", [sys.executable, str(SCRIPT_DIR / "sync_work_memory.py"), "--config", "config.json"], demo_dir)

    rerank_command = [
        sys.executable,
        str(SCRIPT_DIR / "local_ai_rerank.py"),
        "--memory-home",
        ".aipc-work-memory",
        "--query",
        "AI PC Skill 提交 今日会议 今天看的文章",
        "--backend",
        args.embedding_backend,
        "--output",
        "out/local_rerank.json",
    ]
    if args.embedding_backend == "localhost-embeddings":
        rerank_command.extend(["--endpoint", args.embedding_endpoint, "--model", args.embedding_model])
    elif args.embedding_backend == "openvino":
        rerank_command.extend(["--model", args.embedding_model])
    run_command("local AI rerank", rerank_command, demo_dir)

    run_command(
        "mock local agent DailyResult",
        [
            sys.executable,
            str(SCRIPT_DIR / "organize_daily.py"),
            "--input",
            str(SKILL_ROOT / "examples" / "daily_request.sample.json"),
            "--output",
            "out/mock_daily_result.json",
            "--markdown-output",
            "out/mock_daily_summary.md",
            "--mock",
        ],
        demo_dir,
    )
    run_command("validate DailyResult schema", [sys.executable, str(SCRIPT_DIR / "validate_daily_result.py"), "out/mock_daily_result.json"], demo_dir)
    run_command(
        "save final daily memory",
        [
            sys.executable,
            str(SCRIPT_DIR / "save_daily_result.py"),
            "--input",
            "out/mock_daily_result.json",
            "--memory-home",
            ".aipc-work-memory",
            "--date",
            "2026-06-09",
            "--markdown-output",
            "out/final_daily_memory.md",
        ],
        demo_dir,
    )

    expected = {
        "dailyContext": output_dir / "daily_context.md",
        "wikiContext": output_dir / "wiki_context.md",
        "dailyDraft": output_dir / "daily_memory.md",
        "localRerank": output_dir / "local_rerank.json",
        "mockDailyResult": output_dir / "mock_daily_result.json",
        "finalDailyMemory": output_dir / "final_daily_memory.md",
        "importRecords": demo_dir / ".aipc-work-memory" / "import_records.jsonl",
    }
    for label, path in expected.items():
        require_file(path, label)
    verify_rerank_output(expected["localRerank"])

    summary: dict[str, Any] = {
        "ok": True,
        "backend": args.embedding_backend,
        "workDir": str(work_dir),
        "outputs": {label: str(path) for label, path in expected.items()},
    }

    if not args.quiet:
        print("AI PC Daily Memory verification")
        print(f"OK sync/rerank/schema/save-back using backend={args.embedding_backend}")
        print(f"Outputs: {output_dir}")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    if args.cleanup and temp_root is not None:
        shutil.rmtree(temp_root)
    return summary


def main() -> int:
    try:
        run_verification()
    except VerificationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
