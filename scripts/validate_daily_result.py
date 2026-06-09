from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REQUIRED_KEYS = [
    "requestId",
    "summary",
    "themes",
    "ideas",
    "tasks",
    "taskReferences",
    "schedule",
    "defer",
    "links",
    "dailySynthesis",
    "kindleCard",
]


def validate_result(result: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for key in REQUIRED_KEYS:
        if key not in result:
            errors.append(f"missing required key: {key}")

    _expect(result, "requestId", str, errors)
    _expect(result, "summary", str, errors)
    _expect_list_of_strings(result, "themes", errors)
    _expect_list_of_strings(result, "ideas", errors)
    _expect_list_of_strings(result, "tasks", errors)
    _expect_list_of_strings(result, "defer", errors)
    _expect_list_of_strings(result, "links", errors)
    _expect_list_of_strings(result, "dailySynthesis", errors)
    _expect_task_references(result.get("taskReferences"), errors)
    _expect_schedule(result.get("schedule"), errors)
    _expect_kindle_card(result.get("kindleCard"), errors)

    extra = sorted(set(result.keys()).difference(REQUIRED_KEYS))
    for key in extra:
        errors.append(f"unexpected key: {key}")
    return errors


def load_result(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as fh:
        value = json.load(fh)
    if not isinstance(value, dict):
        raise ValueError("daily result must be a JSON object")
    return value


def assert_valid_result(result: dict[str, Any]) -> None:
    errors = validate_result(result)
    if errors:
        raise ValueError("; ".join(errors))


def _expect(result: dict[str, Any], key: str, expected_type: type, errors: list[str]) -> None:
    if key in result and not isinstance(result[key], expected_type):
        errors.append(f"{key} must be {expected_type.__name__}")


def _expect_list_of_strings(result: dict[str, Any], key: str, errors: list[str]) -> None:
    value = result.get(key)
    if not isinstance(value, list):
        errors.append(f"{key} must be an array")
        return
    for index, item in enumerate(value):
        if not isinstance(item, str):
            errors.append(f"{key}[{index}] must be string")


def _expect_task_references(value: Any, errors: list[str]) -> None:
    required = {"task", "sourceTitle", "sourceNoteId", "sourceDate", "note"}
    if not isinstance(value, list):
        errors.append("taskReferences must be an array")
        return
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            errors.append(f"taskReferences[{index}] must be object")
            continue
        for key in required:
            if not isinstance(item.get(key), str):
                errors.append(f"taskReferences[{index}].{key} must be string")
        extra = set(item.keys()).difference(required)
        if extra:
            errors.append(f"taskReferences[{index}] has unexpected keys: {sorted(extra)}")


def _expect_schedule(value: Any, errors: list[str]) -> None:
    required = {"time", "title", "description", "location", "link", "sourceTitle"}
    if not isinstance(value, list):
        errors.append("schedule must be an array")
        return
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            errors.append(f"schedule[{index}] must be object")
            continue
        for key in required:
            if not isinstance(item.get(key), str):
                errors.append(f"schedule[{index}].{key} must be string")
        extra = set(item.keys()).difference(required)
        if extra:
            errors.append(f"schedule[{index}] has unexpected keys: {sorted(extra)}")


def _expect_kindle_card(value: Any, errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append("kindleCard must be object")
        return
    for key in ("title", "body"):
        if not isinstance(value.get(key), str):
            errors.append(f"kindleCard.{key} must be string")
    extra = set(value.keys()).difference({"title", "body"})
    if extra:
        errors.append(f"kindleCard has unexpected keys: {sorted(extra)}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate DailyResult JSON.")
    parser.add_argument("path", help="Path to a DailyResult JSON file.")
    args = parser.parse_args()

    result = load_result(args.path)
    errors = validate_result(result)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"OK: {args.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

