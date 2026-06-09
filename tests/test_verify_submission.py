from __future__ import annotations

import sys
from pathlib import Path

import pytest


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import verify_submission


def test_verify_submission_runs_offline_path() -> None:
    summary = verify_submission.run_verification(["--cleanup", "--quiet"])

    assert summary["ok"] is True
    assert summary["backend"] == "token"
    assert "dailyContext" in summary["outputs"]


def test_verify_submission_requires_openvino_model_path() -> None:
    with pytest.raises(verify_submission.VerificationError, match="embedding-model"):
        verify_submission.run_verification(["--embedding-backend", "openvino", "--quiet", "--cleanup"])
