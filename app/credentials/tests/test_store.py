"""DISC-02: Fernet-encrypted credential store at /data/.credentials."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from cryptography.fernet import Fernet


@pytest.fixture
def credential_env(tmp_path, monkeypatch):
    key = Fernet.generate_key()
    key_file = tmp_path / ".credential-key"
    key_file.write_bytes(key)
    creds_file = tmp_path / ".credentials"
    monkeypatch.setenv("POLICYCODEX_CREDENTIAL_KEY_FILE", str(key_file))
    monkeypatch.setenv("POLICYCODEX_CREDENTIAL_STORE_FILE", str(creds_file))
    yield key_file, creds_file


def test_get_missing_raises(credential_env):
    from app.credentials import store
    store._reset_cache()
    with pytest.raises(KeyError):
        store.get("llm.anthropic.api_key")


def test_set_then_get_roundtrip(credential_env):
    from app.credentials import store
    store._reset_cache()
    store.set("llm.anthropic.api_key", "sk-ant-test-12345")
    assert store.get("llm.anthropic.api_key") == "sk-ant-test-12345"


def test_set_persists_to_disk(credential_env):
    from app.credentials import store
    _, creds_file = credential_env
    store._reset_cache()
    store.set("github_app.app_id", "98765")
    assert creds_file.exists()
    # Encrypted, so the raw value must not appear in the file bytes.
    assert b"98765" not in creds_file.read_bytes()


def test_has_returns_bool(credential_env):
    from app.credentials import store
    store._reset_cache()
    assert store.has("missing.key") is False
    store.set("present.key", "v")
    assert store.has("present.key") is True


def test_first_boot_complete_signal(credential_env):
    from app.credentials import store
    store._reset_cache()
    assert store.first_boot_complete() is False
    store.set("llm.anthropic.api_key", "k")
    store.set("github_app.app_id", "1")
    store.set("github_app.installation_id", "2")
    store.set("github_app.private_key_pem", "-----BEGIN ...")
    assert store.first_boot_complete() is True


def test_write_is_atomic(tmp_path, credential_env):
    """Concurrent writers must not see a half-written file."""
    from app.credentials import store
    _, creds_file = credential_env
    store._reset_cache()
    store.set("a", "1")
    store.set("b", "2")
    # The intermediate temp file must not linger.
    siblings = list(creds_file.parent.glob(".credentials.*"))
    assert siblings == [], f"leftover temp files: {siblings}"


def test_missing_credential_key_file_raises_on_init(tmp_path, monkeypatch):
    from app.credentials import store
    monkeypatch.setenv("POLICYCODEX_CREDENTIAL_KEY_FILE", str(tmp_path / "absent"))
    monkeypatch.setenv("POLICYCODEX_CREDENTIAL_STORE_FILE", str(tmp_path / ".credentials"))
    store._reset_cache()
    with pytest.raises(RuntimeError) as exc:
        store.has("anything")
    assert "credential-key" in str(exc.value).lower()


def test_hydrate_provider_env_vars(credential_env, monkeypatch):
    from app.credentials import store, hydrate_environment
    store._reset_cache()
    store.set("llm.provider", "claude")
    store.set("llm.claude.api_key", "sk-ant-hydrate-test")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    hydrate_environment()
    assert os.environ["ANTHROPIC_API_KEY"] == "sk-ant-hydrate-test"


def test_hydrate_writes_github_app_key_to_path(credential_env, monkeypatch, tmp_path):
    from app.credentials import store, hydrate_environment
    monkeypatch.setenv("POLICYCODEX_GITHUB_APP_KEY_PATH", str(tmp_path / "app.pem"))
    store._reset_cache()
    store.set("github_app.app_id", "1")
    store.set("github_app.installation_id", "2")
    store.set("github_app.private_key_pem", "-----BEGIN PRIVATE KEY-----\nXXX\n-----END PRIVATE KEY-----")
    hydrate_environment()
    pem = tmp_path / "app.pem"
    assert pem.read_text().startswith("-----BEGIN")
    assert os.environ["POLICYCODEX_GH_PRIVATE_KEY_PATH"] == str(pem)


def _write_store_as_other_worker(key_file: Path, creds_file: Path, data: dict) -> None:
    """Emulate a second Gunicorn worker writing the on-disk store directly,
    without touching this process's module cache."""
    f = Fernet(key_file.read_bytes().strip())
    creds_file.write_bytes(f.encrypt(json.dumps(data, sort_keys=True).encode("utf-8")))


def test_get_sees_key_written_by_another_worker(credential_env):
    """Regression (GitHub App install-check failed): Gunicorn runs --workers 3,
    each with its own module cache. The manifest-create callback writes
    github_app.app_id on worker A; the install callback then lands on worker B,
    whose cache was warmed (e.g. by first_boot_complete) before the key existed.
    Pre-fix _ensure_loaded early-returned forever, so worker B raised
    KeyError('github_app.app_id'). The store must reload when the file changes."""
    from app.credentials import store
    key_file, creds_file = credential_env

    # Worker B warms an empty cache before any github_app.app_id is written.
    store._reset_cache()
    assert store.has("github_app.app_id") is False

    # Worker A (separate process) creates the App and persists the key.
    _write_store_as_other_worker(key_file, creds_file, {"github_app.app_id": "424242"})

    # Worker B serves the install check. Must reflect worker A's write.
    assert store.get("github_app.app_id") == "424242"


def test_get_sees_update_from_another_worker_existing_file(credential_env):
    """Cross-worker visibility also holds when the store file already existed
    (mtime changes on rewrite)."""
    from app.credentials import store
    key_file, creds_file = credential_env

    store._reset_cache()
    store.set("github_app.app_id", "1")
    assert store.get("github_app.app_id") == "1"

    # Another worker overwrites the value and we force a strictly-later mtime
    # so the change is detected regardless of filesystem timestamp resolution.
    _write_store_as_other_worker(key_file, creds_file, {"github_app.app_id": "2"})
    future = creds_file.stat().st_mtime + 10
    os.utime(creds_file, (future, future))

    assert store.get("github_app.app_id") == "2"


def test_hydrate_never_raises_when_pem_path_unwritable(credential_env, monkeypatch, tmp_path):
    # Regression: hydrate_environment is called at settings import and its
    # docstring promises it never raises. A read-only target dir (e.g. /data
    # not mounted writable outside Docker) made mkdir raise OSError, which
    # escaped the RuntimeError-only guard and crashed the app at boot.
    from app.credentials import store, hydrate_environment
    unwritable = tmp_path / "nope"
    unwritable.write_text("not a dir")  # parent path component is a file
    monkeypatch.setenv("POLICYCODEX_GITHUB_APP_KEY_PATH", str(unwritable / "app.pem"))
    store._reset_cache()
    store.set("github_app.app_id", "1")
    store.set("github_app.installation_id", "2")
    store.set("github_app.private_key_pem", "-----BEGIN PRIVATE KEY-----\nXXX\n-----END PRIVATE KEY-----")
    hydrate_environment()  # must not raise
