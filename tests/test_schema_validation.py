from __future__ import annotations

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from validate_daily_result import validate_result


def test_validation_rejects_missing_required_fields() -> None:
    errors = validate_result({"requestId": "x"})

    assert any("missing required key: summary" in error for error in errors)
    assert any("tasks must be an array" in error for error in errors)

