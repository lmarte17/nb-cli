from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from nb_cli.exceptions import ConfigError
from nb_cli.config import load_config


def make_args(**overrides):
    base = {
        "config": None,
        "profile": None,
        "url": None,
        "token": None,
        "token_file": None,
        "timeout": None,
        "verify_ssl": None,
        "threading": None,
        "strict_filters": None,
    }
    base.update(overrides)
    return argparse.Namespace(**base)


def test_load_config_prefers_cli_env_and_profile(tmp_path, monkeypatch):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
default_profile = "lab"

[profiles.lab]
url = "https://netbox.example.com/"
token_env = "LAB_TOKEN"
verify_ssl = true
timeout = 15
threading = true
strict_filters = true
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("LAB_TOKEN", "profile-token")
    monkeypatch.setenv("NBCLI_TIMEOUT", "21")

    config = load_config(make_args(config=str(config_path), url="https://override.example.com"))

    assert config.profile == "lab"
    assert config.url == "https://override.example.com"
    assert config.token == "profile-token"
    assert config.timeout == 21.0
    assert config.verify_ssl is True
    assert config.threading is True
    assert config.strict_filters is True


def test_load_config_reads_token_file(tmp_path):
    token_path = tmp_path / "token.txt"
    token_path.write_text("abc123\n", encoding="utf-8")

    config = load_config(
        make_args(
            url="https://netbox.example.com",
            token_file=str(token_path),
        )
    )

    assert config.token == "abc123"
    assert config.url == "https://netbox.example.com"


def test_load_config_rejects_missing_explicit_file(tmp_path):
    with pytest.raises(ConfigError):
        load_config(make_args(config=str(tmp_path / "missing.toml")))
