from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .exceptions import ConfigError, ValidationError
from .parsing import parse_bool

LOCAL_CONFIG_NAME = ".nb-cli.toml"
XDG_CONFIG_PATH = Path.home() / ".config" / "nb-cli" / "config.toml"


@dataclass(slots=True, frozen=True)
class AppConfig:
    profile: str
    url: str | None
    token: str | None
    verify_ssl: bool
    timeout: float
    threading: bool
    strict_filters: bool
    headers: dict[str, str] = field(default_factory=dict)
    config_files: tuple[str, ...] = field(default_factory=tuple)

    def requires_token_for(self, command: str, method: str | None = None) -> bool:
        if command in {"create", "update", "delete"}:
            return True
        if command == "request" and method and method.upper() not in {"GET", "HEAD", "OPTIONS"}:
            return True
        return False


def _load_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except FileNotFoundError:
        return {}
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"invalid TOML in config file: {path}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"config file must contain a TOML table: {path}")
    return data


def _merge_dicts(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_dicts(merged[key], value)
        else:
            merged[key] = value
    return merged


def _discover_config_files() -> list[Path]:
    files = []
    if XDG_CONFIG_PATH.exists():
        files.append(XDG_CONFIG_PATH)
    local_path = Path.cwd() / LOCAL_CONFIG_NAME
    if local_path.exists():
        files.append(local_path)
    return files


def _read_token_file(path: str | Path | None) -> str | None:
    if not path:
        return None
    token_path = Path(path)
    try:
        token = token_path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise ConfigError(f"unable to read token file: {token_path}") from exc
    if not token:
        raise ConfigError(f"token file is empty: {token_path}")
    return token


def _env_bool(name: str) -> bool | None:
    value = os.environ.get(name)
    if value is None:
        return None
    return parse_bool(value)


def _env_float(name: str) -> float | None:
    value = os.environ.get(name)
    if value is None:
        return None
    try:
        return float(value)
    except ValueError as exc:
        raise ValidationError(f"environment variable {name} must be numeric") from exc


def load_config(args: Any) -> AppConfig:
    if getattr(args, "config", None):
        explicit_path = Path(args.config)
        if not explicit_path.exists():
            raise ConfigError(f"config file does not exist: {explicit_path}")
        config_files = [explicit_path]
    else:
        config_files = _discover_config_files()

    merged: dict[str, Any] = {}
    for path in config_files:
        merged = _merge_dicts(merged, _load_toml(path))

    env_profile = os.environ.get("NBCLI_PROFILE")
    default_profile = merged.get("default_profile", "default")
    profile_name = args.profile or env_profile or default_profile

    profiles = merged.get("profiles", {})
    if profiles and not isinstance(profiles, dict):
        raise ConfigError("profiles must be a TOML table")
    if profiles and profile_name not in profiles:
        raise ConfigError(f"profile {profile_name!r} was not found in the loaded config")
    profile = profiles.get(profile_name, {})
    if profile and not isinstance(profile, dict):
        raise ConfigError(f"profile {profile_name} must be a TOML table")

    profile_token = profile.get("token")
    profile_token_file = profile.get("token_file")
    profile_token_env = profile.get("token_env")
    token_from_profile_env = os.environ.get(profile_token_env) if profile_token_env else None

    token = (
        args.token
        or _read_token_file(getattr(args, "token_file", None))
        or os.environ.get("NBCLI_TOKEN")
        or os.environ.get("NETBOX_TOKEN")
        or token_from_profile_env
        or _read_token_file(profile_token_file)
        or profile_token
    )

    url = (
        args.url
        or os.environ.get("NBCLI_URL")
        or os.environ.get("NETBOX_URL")
        or profile.get("url")
    )
    if url:
        url = str(url).rstrip("/")

    verify_ssl = (
        args.verify_ssl
        if args.verify_ssl is not None
        else _env_bool("NBCLI_VERIFY_SSL")
    )
    if verify_ssl is None:
        verify_ssl = bool(profile.get("verify_ssl", True))

    timeout = args.timeout if args.timeout is not None else _env_float("NBCLI_TIMEOUT")
    if timeout is None:
        timeout = float(profile.get("timeout", 30.0))

    threading = (
        args.threading
        if args.threading is not None
        else _env_bool("NBCLI_THREADING")
    )
    if threading is None:
        threading = bool(profile.get("threading", True))

    strict_filters = (
        args.strict_filters
        if args.strict_filters is not None
        else _env_bool("NBCLI_STRICT_FILTERS")
    )
    if strict_filters is None:
        strict_filters = bool(profile.get("strict_filters", True))

    headers = profile.get("headers", {})
    if headers and not isinstance(headers, dict):
        raise ConfigError("profile headers must be a TOML table")

    return AppConfig(
        profile=profile_name,
        url=url,
        token=token,
        verify_ssl=verify_ssl,
        timeout=timeout,
        threading=threading,
        strict_filters=strict_filters,
        headers={str(key): str(value) for key, value in headers.items()},
        config_files=tuple(str(path) for path in config_files),
    )
