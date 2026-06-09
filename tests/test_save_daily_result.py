from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import save_daily_result


def daily_result() -> dict:
    return {
        "requestId": "work-memory-2026-06-08",
        "summary": "今天完成了固定来源同步。",
        "themes": ["AI PC Skill"],
        "ideas": ["让本地 agent 读取明确配置的资料。"],
        "tasks": ["补齐 README"],
        "taskReferences": [
            {
                "task": "补齐 README",
                "sourceTitle": "今天资料",
                "sourceNoteId": "note:1",
                "sourceDate": "2026-06-08",
                "note": "来源中包含明确行动。",
            }
        ],
        "schedule": [
            {
                "time": "2026-06-08T10:00:00+08:00",
                "title": "产品例会",
                "description": "讨论参赛提交。",
                "location": "",
                "link": "",
                "sourceTitle": "产品例会",
            }
        ],
        "defer": [],
        "links": ["https://example.com/article"],
        "dailySynthesis": ["今天围绕 AI PC Skill 做了完整闭环。"],
        "kindleCard": {"title": "今日工作记忆", "body": "固定来源同步完成。"},
    }


def test_save_daily_result_can_write_stable_markdown(tmp_path: Path, monkeypatch) -> None:
    input_path = tmp_path / "daily_result.json"
    output_path = tmp_path / "out" / "daily_memory.md"
    input_path.write_text(json.dumps(daily_result(), ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "save_daily_result.py",
            "--input",
            str(input_path),
            "--memory-home",
            str(tmp_path / ".memory"),
            "--date",
            "2026-06-08",
            "--markdown-output",
            str(output_path),
        ],
    )

    assert save_daily_result.main() == 0

    text = output_path.read_text(encoding="utf-8")
    assert "# 今日工作记忆" in text
    assert "## 日程" in text
    assert "产品例会" in text
    assert "## 待办" in text
    assert "补齐 README" in text
