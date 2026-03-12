from __future__ import annotations

import dataclasses
import datetime as dt
import json
import pprint
from pathlib import Path
from typing import Any

from .exceptions import ErrorPayload


def to_data(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dt.datetime):
        return value.isoformat()
    if isinstance(value, dt.date):
        return value.isoformat()
    if dataclasses.is_dataclass(value):
        return to_data(dataclasses.asdict(value))
    if hasattr(value, "serialize") and callable(value.serialize):
        return to_data(value.serialize())
    if isinstance(value, dict):
        return {str(key): to_data(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_data(item) for item in value]
    if isinstance(value, bytes):
        return value.decode("utf-8")
    if hasattr(value, "__iter__") and not isinstance(value, (str, bytes)):
        return [to_data(item) for item in value]
    return str(value)


def success_envelope(command: str, data: Any) -> dict[str, Any]:
    return {
        "ok": True,
        "command": command,
        "data": to_data(data),
    }


def error_envelope(payload: ErrorPayload) -> dict[str, Any]:
    data = {
        "type": payload.error_type,
        "message": payload.message,
    }
    if payload.details is not None:
        data["details"] = to_data(payload.details)
    return {
        "ok": False,
        "error": data,
    }


def render_output(data: Any, fmt: str) -> str:
    normalized = to_data(data)
    if fmt == "jsonl":
        return _render_jsonl(normalized)
    if fmt == "table":
        return _render_table(normalized)
    if fmt == "text":
        if _is_success_envelope(normalized):
            return _render_text(normalized["data"])
        if _is_error_envelope(normalized):
            error = normalized["error"]
            return f"{error['type']}: {error['message']}"
        if isinstance(normalized, str):
            return normalized
        return pprint.pformat(normalized, sort_dicts=False)
    return json.dumps(normalized, indent=2, sort_keys=False)


def _render_jsonl(normalized: Any) -> str:
    if _is_success_envelope(normalized) and isinstance(normalized.get("data"), list):
        return "\n".join(json.dumps(item, sort_keys=False) for item in normalized["data"])
    if isinstance(normalized, list):
        return "\n".join(json.dumps(item, sort_keys=False) for item in normalized)
    return json.dumps(normalized, sort_keys=False)


def _render_text(data: Any) -> str:
    if isinstance(data, dict) and "body" in data and "topic" in data:
        suffix = ""
        topics = data.get("available_topics")
        if isinstance(topics, list) and topics:
            suffix = "\nAvailable topics: " + ", ".join(topics)
        return f"{data['body'].rstrip()}{suffix}"
    if isinstance(data, str):
        return data
    return pprint.pformat(data, sort_dicts=False)


def _render_table(normalized: Any) -> str:
    if _is_success_envelope(normalized):
        normalized = normalized["data"]
    elif _is_error_envelope(normalized):
        error = normalized["error"]
        return f"{error['type']}: {error['message']}"

    if isinstance(normalized, dict):
        rows = [(key, _cell(value)) for key, value in normalized.items()]
        return _format_rows(["field", "value"], rows)
    if isinstance(normalized, list):
        if not normalized:
            return "(no rows)"
        if all(isinstance(item, dict) for item in normalized):
            columns = _collect_columns(normalized)
            rows = [[_cell(item.get(column)) for column in columns] for item in normalized]
            return _format_rows(columns, rows)
        rows = [[index, _cell(item)] for index, item in enumerate(normalized, start=1)]
        return _format_rows(["row", "value"], rows)
    return str(normalized)


def _collect_columns(rows: list[dict[str, Any]]) -> list[str]:
    columns: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row.keys():
            if key not in seen:
                seen.add(key)
                columns.append(str(key))
    return columns


def _format_rows(headers: list[str], rows: list[list[Any]] | list[tuple[Any, ...]]) -> str:
    widths = [len(str(header)) for header in headers]
    matrix = [[str(cell) for cell in row] for row in rows]
    for row in matrix:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))

    header_line = " | ".join(str(header).ljust(widths[index]) for index, header in enumerate(headers))
    separator = "-+-".join("-" * width for width in widths)
    body = [" | ".join(cell.ljust(widths[index]) for index, cell in enumerate(row)) for row in matrix]
    return "\n".join([header_line, separator, *body])


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=False)
    return str(value)


def _is_success_envelope(value: Any) -> bool:
    return isinstance(value, dict) and value.get("ok") is True and "data" in value


def _is_error_envelope(value: Any) -> bool:
    return isinstance(value, dict) and value.get("ok") is False and "error" in value
