"""Tests for WorkingCopyConfig."""
from pathlib import Path

import pytest
from django.test import override_settings

from app.working_copy.config import WorkingCopyConfig, load_working_copy_config


def test_load_from_django_settings_uses_three_settings(tmp_path):
    with override_settings(
        POLICYCODEX_POLICY_REPO_URL="https://github.com/example/policy.git",
        POLICYCODEX_POLICY_BRANCH="main",
        POLICYCODEX_WORKING_COPY_ROOT=str(tmp_path / "wc-root"),
    ):
        cfg = load_working_copy_config()

    assert isinstance(cfg, WorkingCopyConfig)
    assert cfg.repo_url == "https://github.com/example/policy.git"
    assert cfg.branch == "main"
    assert cfg.root == tmp_path / "wc-root"


def test_load_raises_when_repo_url_unset():
    with override_settings(
        POLICYCODEX_POLICY_REPO_URL="",
        POLICYCODEX_POLICY_BRANCH="main",
        POLICYCODEX_WORKING_COPY_ROOT="/tmp/wc",
    ):
        # Defensive: also clear any policy_repo.* the credential store may carry.
        from app.credentials import store
        try:
            store._reset_cache()
        except Exception:
            pass
        with pytest.raises(RuntimeError, match="POLICYCODEX_POLICY_REPO_URL"):
            load_working_copy_config()


def test_load_falls_back_to_credential_store_when_settings_empty(tmp_path, monkeypatch):
    """DISC followup: the wizard's screen 4 writes policy_repo.url + branch
    to the credential store. load_working_copy_config() must read those
    when Django settings are empty (the common production state — env vars
    set only at container boot, before the wizard ran)."""
    from cryptography.fernet import Fernet
    from app.credentials import store
    key_file = tmp_path / ".credential-key"
    key_file.write_bytes(Fernet.generate_key())
    monkeypatch.setenv("POLICYCODEX_CREDENTIAL_KEY_FILE", str(key_file))
    monkeypatch.setenv("POLICYCODEX_CREDENTIAL_STORE_FILE", str(tmp_path / ".credentials"))
    store._reset_cache()
    try:
        store.set("policy_repo.url", "https://github.com/diocese/from-store.git")
        store.set("policy_repo.branch", "main")
        with override_settings(
            POLICYCODEX_POLICY_REPO_URL="",
            POLICYCODEX_POLICY_BRANCH="main",
            POLICYCODEX_WORKING_COPY_ROOT=str(tmp_path / "wc-root"),
        ):
            cfg = load_working_copy_config()
        assert cfg.repo_url == "https://github.com/diocese/from-store.git"
        assert cfg.branch == "main"
    finally:
        # Clear the in-memory cache so subsequent tests don't see this data
        # (monkeypatch restores the env vars but the module-level _cache global
        # would survive into the next test if we didn't reset it).
        store._reset_cache()


def test_working_dir_property_strips_dot_git(tmp_path):
    cfg = WorkingCopyConfig(
        repo_url="https://github.com/example/policy.git",
        branch="main",
        root=tmp_path,
    )
    assert cfg.working_dir == tmp_path / "policy"


def test_working_dir_without_dot_git_suffix(tmp_path):
    cfg = WorkingCopyConfig(
        repo_url="https://github.com/example/policy",
        branch="main",
        root=tmp_path,
    )
    assert cfg.working_dir == tmp_path / "policy"


def test_load_expands_user_in_root_path(monkeypatch):
    monkeypatch.setenv("HOME", "/tmp/fakehome")
    with override_settings(
        POLICYCODEX_POLICY_REPO_URL="https://github.com/example/policy.git",
        POLICYCODEX_POLICY_BRANCH="main",
        POLICYCODEX_WORKING_COPY_ROOT="~/custom-wc",
    ):
        cfg = load_working_copy_config()
    assert cfg.root == Path("/tmp/fakehome/custom-wc")
