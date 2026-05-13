"""Tests for GitHub App config loader."""
import os
from pathlib import Path

import pytest

from app.git_provider.github_config import GitHubConfig, load_github_config


def _write_config(tmp_path: Path, lines: list[str]) -> Path:
    config_file = tmp_path / "config.env"
    config_file.write_text("\n".join(lines) + "\n")
    return config_file


def test_load_config_reads_required_keys(tmp_path, monkeypatch):
    config_file = _write_config(tmp_path, [
        "POLICYCODEX_GH_APP_ID=12345",
        "POLICYCODEX_GH_INSTALLATION_ID=67890",
        f"POLICYCODEX_GH_PRIVATE_KEY_PATH={tmp_path}/key.pem",
    ])
    monkeypatch.setenv("POLICYCODEX_CONFIG_PATH", str(config_file))
    cfg = load_github_config()
    assert cfg.app_id == 12345
    assert cfg.installation_id == 67890
    assert cfg.private_key_path == tmp_path / "key.pem"


def test_load_config_defaults_to_home_config_path(tmp_path, monkeypatch):
    monkeypatch.delenv("POLICYCODEX_CONFIG_PATH", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    config_dir = tmp_path / ".config" / "policycodex"
    config_dir.mkdir(parents=True)
    _write_config(config_dir, [
        "POLICYCODEX_GH_APP_ID=1",
        "POLICYCODEX_GH_INSTALLATION_ID=2",
        f"POLICYCODEX_GH_PRIVATE_KEY_PATH={tmp_path}/k.pem",
    ]).rename(config_dir / "config.env")
    cfg = load_github_config()
    assert cfg.app_id == 1


def test_load_config_ignores_comments_and_blank_lines(tmp_path, monkeypatch):
    config_file = _write_config(tmp_path, [
        "# leading comment",
        "",
        "POLICYCODEX_GH_APP_ID=42",
        "  # indented comment",
        "POLICYCODEX_GH_INSTALLATION_ID=43",
        f"POLICYCODEX_GH_PRIVATE_KEY_PATH={tmp_path}/k.pem",
    ])
    monkeypatch.setenv("POLICYCODEX_CONFIG_PATH", str(config_file))
    cfg = load_github_config()
    assert cfg.app_id == 42


def test_load_config_strips_surrounding_quotes(tmp_path, monkeypatch):
    config_file = _write_config(tmp_path, [
        'POLICYCODEX_GH_APP_ID="42"',
        "POLICYCODEX_GH_INSTALLATION_ID='43'",
        f'POLICYCODEX_GH_PRIVATE_KEY_PATH="{tmp_path}/k.pem"',
    ])
    monkeypatch.setenv("POLICYCODEX_CONFIG_PATH", str(config_file))
    cfg = load_github_config()
    assert cfg.app_id == 42
    assert cfg.installation_id == 43


def test_load_config_raises_on_missing_file(tmp_path, monkeypatch):
    monkeypatch.setenv("POLICYCODEX_CONFIG_PATH", str(tmp_path / "missing.env"))
    with pytest.raises(FileNotFoundError):
        load_github_config()


def test_load_config_raises_on_missing_required_key(tmp_path, monkeypatch):
    config_file = _write_config(tmp_path, [
        "POLICYCODEX_GH_APP_ID=1",
        f"POLICYCODEX_GH_PRIVATE_KEY_PATH={tmp_path}/k.pem",
    ])
    monkeypatch.setenv("POLICYCODEX_CONFIG_PATH", str(config_file))
    with pytest.raises(ValueError, match="POLICYCODEX_GH_INSTALLATION_ID"):
        load_github_config()
