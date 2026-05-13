"""Tests for GitHubProvider."""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.git_provider.base import GitProvider
from app.git_provider.github_provider import GitHubProvider


def _fake_config(tmp_path: Path) -> MagicMock:
    cfg = MagicMock()
    cfg.app_id = 1
    cfg.installation_id = 2
    cfg.private_key_path = tmp_path / "key.pem"
    return cfg


def test_github_provider_is_git_provider(tmp_path):
    cfg = _fake_config(tmp_path)
    (tmp_path / "key.pem").write_text("FAKE PEM")
    assert issubclass(GitHubProvider, GitProvider)
    p = GitHubProvider(config=cfg, github_client=MagicMock())
    assert isinstance(p, GitProvider)


def test_constructor_loads_config_by_default(tmp_path):
    fake_cfg = _fake_config(tmp_path)
    (tmp_path / "key.pem").write_text("FAKE PEM")
    with patch("app.git_provider.github_provider.load_github_config", return_value=fake_cfg) as loader:
        p = GitHubProvider(github_client=MagicMock())
    loader.assert_called_once()
    assert p._config is fake_cfg


def test_installation_token_fetched_via_app_auth(tmp_path):
    cfg = _fake_config(tmp_path)
    (tmp_path / "key.pem").write_text("FAKE PEM")
    with patch("app.git_provider.github_provider._build_installation_token", return_value="ghs_fake_token_xyz") as builder:
        p = GitHubProvider(config=cfg, github_client=MagicMock())
        token = p._installation_token()
    assert token == "ghs_fake_token_xyz"
    builder.assert_called_once_with(cfg)


def test_clone_invokes_git_with_tokenized_url(tmp_path):
    cfg = _fake_config(tmp_path)
    (tmp_path / "key.pem").write_text("FAKE PEM")
    with patch("app.git_provider.github_provider._build_installation_token", return_value="ghs_TOK"):
        with patch("app.git_provider.github_provider.subprocess.run") as run:
            run.return_value = MagicMock(returncode=0)
            p = GitHubProvider(config=cfg, github_client=MagicMock())
            p.clone("https://github.com/foo/bar.git", tmp_path / "dest")
    args, kwargs = run.call_args
    cmd = args[0]
    assert cmd[0] == "git"
    assert cmd[1] == "clone"
    assert any("x-access-token:ghs_TOK@github.com/foo/bar.git" in part for part in cmd)
    assert str(tmp_path / "dest") in cmd


def test_clone_raises_on_nonzero_exit(tmp_path):
    cfg = _fake_config(tmp_path)
    (tmp_path / "key.pem").write_text("FAKE PEM")
    with patch("app.git_provider.github_provider._build_installation_token", return_value="t"):
        with patch("app.git_provider.github_provider.subprocess.run") as run:
            run.return_value = MagicMock(returncode=128, stderr=b"fatal: repo not found")
            p = GitHubProvider(config=cfg, github_client=MagicMock())
            with pytest.raises(RuntimeError, match="git clone"):
                p.clone("https://github.com/foo/bar.git", tmp_path / "dest")


def test_branch_creates_new_branch_in_working_dir(tmp_path):
    cfg = _fake_config(tmp_path)
    (tmp_path / "key.pem").write_text("FAKE PEM")
    with patch("app.git_provider.github_provider.subprocess.run") as run:
        run.return_value = MagicMock(returncode=0)
        p = GitHubProvider(config=cfg, github_client=MagicMock())
        p.branch("policycodex/draft-foo", tmp_path / "wd")
    args, kwargs = run.call_args
    assert args[0] == ["git", "checkout", "-b", "policycodex/draft-foo"]
    assert kwargs["cwd"] == tmp_path / "wd"


def test_branch_raises_on_nonzero_exit(tmp_path):
    cfg = _fake_config(tmp_path)
    (tmp_path / "key.pem").write_text("FAKE PEM")
    with patch("app.git_provider.github_provider.subprocess.run") as run:
        run.return_value = MagicMock(returncode=128, stderr=b"branch exists")
        p = GitHubProvider(config=cfg, github_client=MagicMock())
        with pytest.raises(RuntimeError, match="git checkout"):
            p.branch("dupe", tmp_path / "wd")
