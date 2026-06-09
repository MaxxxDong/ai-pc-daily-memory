from __future__ import annotations

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from organize_daily import organize
from local_llm_client import validate_local_base_url
from validate_daily_result import validate_result


def test_mock_organize_produces_valid_result() -> None:
    root = Path(__file__).resolve().parents[1]
    request_path = root / "examples" / "daily_request.sample.json"

    result = organize(request_path, mock=True)

    assert validate_result(result) == []
    assert result["requestId"] == "daily-2026-06-08-demo"
    assert any("明天跟进" in task for task in result["tasks"])
    assert not result["defer"]


def test_standalone_llm_endpoint_requires_localhost() -> None:
    validate_local_base_url("http://localhost:11434/v1")

    try:
        validate_local_base_url("https://api.example.com/v1")
    except ValueError as exc:
        assert "localhost" in str(exc)
    else:
        raise AssertionError("remote LLM endpoint should be rejected")
