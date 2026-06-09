from __future__ import annotations

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from prepare_daily_context import prepare_context


def test_prepare_context_contains_request_schema_and_sources() -> None:
    root = Path(__file__).resolve().parents[1]
    context = prepare_context(root / "examples" / "daily_request.sample.json")

    assert "# Local Work Memory Context" in context
    assert "Required DailyResult Shape" in context
    assert "AI PC Skill 参赛思路" in context
    assert "Future-dated work" in context

