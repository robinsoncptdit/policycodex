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
        with pytest.raises(RuntimeError, match="POLICYCODEX_POLICY_REPO_URL"):
            load_working_copy_config()


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
