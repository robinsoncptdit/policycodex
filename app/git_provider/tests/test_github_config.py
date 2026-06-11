"""Tests for GitHub App config loader."""
import os
from pathlib import Path

import pytest

from app.git_provider.github_config import GitHubConfig, load_github_config


def _write_config(tmp_path: Path, lines: list[str]) -> Path:
    config_file = tmp_path / "config.env"
    config_file.write_text("\n".join(lines) + "\n")
    return config_file


@pytest.fixture(autouse=True)
def _isolate_gh_env_vars(monkeypatch):
    """DISC-02's hydrate_environment() writes POLICYCODEX_GH_* via os.environ[...]=
    in other tests; monkeypatch doesn't undo that. These tests assert file-path
    behavior, so unset the env vars unless a test sets them explicitly."""
    monkeypatch.delenv("POLICYCODEX_GH_APP_ID", raising=False)
    monkeypatch.delenv("POLICYCODEX_GH_INSTALLATION_ID", raising=False)
    monkeypatch.delenv("POLICYCODEX_GH_PRIVATE_KEY_PATH", raising=False)


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


def test_load_config_prefers_env_vars_over_file(tmp_path, monkeypatch):
    """DISC-02 followup: credential-store hydration writes POLICYCODEX_GH_*
    env vars at Django startup. load_github_config() must honor them before
    falling back to the legacy ~/.config/policycodex/config.env file path,
    which no longer exists after the DISC architecture pivot."""
    monkeypatch.setenv("POLICYCODEX_GH_APP_ID", "777")
    monkeypatch.setenv("POLICYCODEX_GH_INSTALLATION_ID", "888")
    monkeypatch.setenv("POLICYCODEX_GH_PRIVATE_KEY_PATH", str(tmp_path / "from-env.pem"))
    monkeypatch.setenv("POLICYCODEX_CONFIG_PATH", str(tmp_path / "should-be-ignored.env"))
    # Note: config.env does NOT exist — env vars win before file is read.
    cfg = load_github_config()
    assert cfg.app_id == 777
    assert cfg.installation_id == 888
    assert cfg.private_key_path == tmp_path / "from-env.pem"


def test_load_config_hydrates_from_credential_store(tmp_path, monkeypatch):
    """DISC-02 hydrate_environment runs at Django startup, BEFORE the wizard
    writes creds. load_github_config() must call hydrate on every call so
    the wizard's writes flow into env vars before the env-var path checks."""
    from cryptography.fernet import Fernet
    from app.credentials import store
    key_file = tmp_path / ".credential-key"
    key_file.write_bytes(Fernet.generate_key())
    monkeypatch.setenv("POLICYCODEX_CREDENTIAL_KEY_FILE", str(key_file))
    monkeypatch.setenv("POLICYCODEX_CREDENTIAL_STORE_FILE", str(tmp_path / ".credentials"))
    monkeypatch.setenv("POLICYCODEX_GITHUB_APP_KEY_PATH", str(tmp_path / "gh.pem"))
    store._reset_cache()
    store.set("github_app.app_id", "555")
    store.set("github_app.installation_id", "666")
    store.set("github_app.private_key_pem", "-----BEGIN-----\nABC\n-----END-----")
    # Env vars are NOT pre-set — load_github_config must hydrate them itself.
    cfg = load_github_config()
    assert cfg.app_id == 555
    assert cfg.installation_id == 666
    assert cfg.private_key_path == tmp_path / "gh.pem"
    assert cfg.private_key_path.read_text().startswith("-----BEGIN-----")


def test_load_config_falls_back_to_file_when_env_vars_partial(tmp_path, monkeypatch):
    """If only some POLICYCODEX_GH_* env vars are set (e.g., a partial leak),
    skip the env path and use the file. Prevents a half-configured env from
    silently overriding a complete config.env."""
    config_file = _write_config(tmp_path, [
        "POLICYCODEX_GH_APP_ID=1",
        "POLICYCODEX_GH_INSTALLATION_ID=2",
        f"POLICYCODEX_GH_PRIVATE_KEY_PATH={tmp_path}/k.pem",
    ])
    monkeypatch.setenv("POLICYCODEX_CONFIG_PATH", str(config_file))
    monkeypatch.setenv("POLICYCODEX_GH_APP_ID", "999")  # only one of three
    monkeypatch.delenv("POLICYCODEX_GH_INSTALLATION_ID", raising=False)
    monkeypatch.delenv("POLICYCODEX_GH_PRIVATE_KEY_PATH", raising=False)
    cfg = load_github_config()
    assert cfg.app_id == 1  # came from file, not the partial env
