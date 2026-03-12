from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

from .exceptions import UsageError, ValidationError

KEY_VALUE_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+=.+$")
RESOURCE_PATTERN = re.compile(r"^[A-Za-z0-9_]+(?:\.[A-Za-z0-9_-]+)+$")


def parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValidationError(f"invalid boolean value: {value}")


def parse_resource(resource: str) -> list[str]:
    if not RESOURCE_PATTERN.match(resource):
        raise UsageError(
            "resource must be a dotted endpoint path like dcim.devices or ipam.ip_addresses"
        )
    return resource.split(".")


def parse_scalar(value: str) -> Any:
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def parse_key_value_pairs(items: list[str] | None, option_name: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for item in items or []:
        if not KEY_VALUE_PATTERN.match(item):
            raise UsageError(f"{option_name} entries must look like key=value")
        key, raw_value = item.split("=", 1)
        value = parse_scalar(raw_value)
        if key in result:
            existing = result[key]
            if isinstance(existing, list):
                existing.append(value)
            else:
                result[key] = [existing, value]
        else:
            result[key] = value
    return result


def load_json_data(raw: str | None) -> Any:
    if raw is None:
        return None
    if raw == "-":
        content = sys.stdin.read()
    elif raw.startswith("@"):
        path = Path(raw[1:])
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ValidationError(f"unable to read payload file: {path}") from exc
    else:
        content = raw
    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"payload is not valid JSON: {exc.msg}") from exc


def require_confirmation(*, yes: bool, dry_run: bool, action: str) -> None:
    if dry_run:
        return
    if not yes:
        raise ValidationError(f"{action} requires --yes unless --dry-run is used")
