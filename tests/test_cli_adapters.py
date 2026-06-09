from __future__ import annotations

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import ingest_dingtalk_cli
import ingest_feishu_cli


def test_dingtalk_dws_uses_json_format_flag(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run_cli(cli: str, args: list[str], timeout: int = 120) -> str:
        calls.append(args)
        return '{"content":"# 钉钉文档\\n\\n正文"}'

    monkeypatch.setattr(ingest_dingtalk_cli, "run_cli", fake_run_cli)

    title, body, metadata = ingest_dingtalk_cli.read_dingtalk("dws", "dws", doc_url="https://alidocs.dingtalk.com/i/nodes/demo")

    assert title == "钉钉文档"
    assert body == "# 钉钉文档\n\n正文"
    assert metadata["url"].startswith("https://")
    assert calls == [["-f", "json", "doc", "read", "--node", "https://alidocs.dingtalk.com/i/nodes/demo"]]


def test_dingtalk_legacy_cli_uses_json_prefix(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run_cli(cli: str, args: list[str], timeout: int = 120) -> str:
        calls.append(args)
        return '{"markdown":"表格"}'

    monkeypatch.setattr(ingest_dingtalk_cli, "run_cli", fake_run_cli)

    _, body, _ = ingest_dingtalk_cli.read_dingtalk("dingtalk-cli", "dingtalk-cli", workbook_node_id="node-1", workbook_range="A1:B2")

    assert body == "表格"
    assert calls == [["--json", "workbook", "read", "--node-id", "node-1", "--range", "A1:B2"]]


def test_dingtalk_dws_sheet_uses_range_read(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run_cli(cli: str, args: list[str], timeout: int = 120) -> str:
        calls.append(args)
        return '{"markdown":"表格"}'

    monkeypatch.setattr(ingest_dingtalk_cli, "run_cli", fake_run_cli)

    _, body, _ = ingest_dingtalk_cli.read_dingtalk("dws", "dws", workbook_node_id="node-1", workbook_range="A1:B2")

    assert body == "表格"
    assert calls == [["-f", "json", "sheet", "range", "read", "--node", "node-1", "--range", "A1:B2"]]


def test_dingtalk_calendar_and_todo_sources() -> None:
    calendar_raw = '{"success":true,"result":[{"summary":"产品例会","start":{"dateTime":"2026-06-08T10:00:00+08:00"},"end":{"dateTime":"2026-06-08T11:00:00+08:00"}}]}'
    todo_raw = '{"result":{"todoCards":[{"taskName":"补充 AIPC 提交文档"}]}}'

    calendar_sources = ingest_dingtalk_cli.sources_from_calendar(calendar_raw, "2026-06-08")
    todo_sources = ingest_dingtalk_cli.sources_from_todos(todo_raw, "2026-06-08")

    assert calendar_sources[0].source_kind == "schedule"
    assert calendar_sources[0].title == "产品例会"
    assert calendar_sources[0].metadata["start"] == "2026-06-08T10:00:00+08:00"
    assert todo_sources[0].source_kind == "task"
    assert todo_sources[0].title == "补充 AIPC 提交文档"


def test_feishu_extract_body_prefers_markdown() -> None:
    body, metadata = ingest_feishu_cli.extract_body('{"data":{"markdown":"会议摘要"}}')

    assert body == "会议摘要"
    assert metadata["data"]["markdown"] == "会议摘要"


def test_feishu_doc_export_uses_relative_output(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[list[str], Path | None]] = []

    def fake_run_cli(cli: str, args: list[str], cwd: Path | None = None, timeout: int = 180) -> str:
        calls.append((args, cwd))
        assert cwd is not None
        (cwd / "token.md").write_text("# 飞书文档\n\n正文", encoding="utf-8")
        return ""

    monkeypatch.setattr(ingest_feishu_cli, "run_cli", fake_run_cli)

    sources = ingest_feishu_cli.ingest_doc_export("lark-cli", "token", "docx", tmp_path, "2026-06-08")

    assert sources[0].title == "飞书文档"
    assert sources[0].source_kind == "feishu-document"
    assert calls[0][0][-3:] == ["--output", "token.md", "--overwrite"]
    assert str(tmp_path) not in calls[0][0]


def test_feishu_main_reports_cli_error_without_traceback(monkeypatch, capsys) -> None:
    def fake_run_cli(cli: str, args: list[str], cwd: Path | None = None, timeout: int = 180) -> str:
        raise RuntimeError("lark-cli not found")

    monkeypatch.setattr(ingest_feishu_cli, "run_cli", fake_run_cli)
    monkeypatch.setattr(sys, "argv", ["ingest_feishu_cli.py", "--auth-status"])

    assert ingest_feishu_cli.main() == 1
    captured = capsys.readouterr()
    assert "ERROR: lark-cli not found" in captured.err
    assert "Traceback" not in captured.err
