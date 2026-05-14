"""Tests for WorkingCopyManager."""
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.working_copy.config import WorkingCopyConfig
from app.working_copy.manager import WorkingCopyManager


def _cfg(root: Path) -> WorkingCopyConfig:
    return WorkingCopyConfig(
        repo_url="https://github.com/example/policy.git",
        branch="main",
        root=root,
    )


def test_sync_clones_when_working_dir_missing(tmp_path):
    cfg = _cfg(tmp_path)
    provider = MagicMock()
    manager = WorkingCopyManager(cfg, provider)

    result = manager.sync()

    provider.clone.assert_called_once_with(cfg.repo_url, cfg.working_dir)
    provider.pull.assert_not_called()
    assert result == cfg.working_dir


def test_sync_pulls_when_working_dir_exists(tmp_path):
    cfg = _cfg(tmp_path)
    cfg.working_dir.mkdir(parents=True)
    (cfg.working_dir / ".git").mkdir()
    provider = MagicMock()
    manager = WorkingCopyManager(cfg, provider)

    result = manager.sync()

    provider.clone.assert_not_called()
    provider.pull.assert_called_once_with(cfg.branch, cfg.working_dir)
    assert result == cfg.working_dir


def test_sync_refuses_to_clobber_non_git_directory(tmp_path):
    """Defensive: if the dir is there but is not a git repo, fail loud."""
    cfg = _cfg(tmp_path)
    cfg.working_dir.mkdir(parents=True)
    (cfg.working_dir / "stale.txt").write_text("x")
    provider = MagicMock()
    manager = WorkingCopyManager(cfg, provider)

    with pytest.raises(RuntimeError, match="not a git repository"):
        manager.sync()

    provider.clone.assert_not_called()
    provider.pull.assert_not_called()


def test_sync_creates_root_parents_before_clone(tmp_path):
    cfg = _cfg(tmp_path / "deeply" / "nested")
    provider = MagicMock()
    manager = WorkingCopyManager(cfg, provider)

    manager.sync()

    assert (tmp_path / "deeply" / "nested").is_dir()
    provider.clone.assert_called_once()


def test_sync_propagates_clone_error(tmp_path):
    cfg = _cfg(tmp_path)
    provider = MagicMock()
    provider.clone.side_effect = RuntimeError("git clone failed (exit 128): boom")
    manager = WorkingCopyManager(cfg, provider)

    with pytest.raises(RuntimeError, match="git clone failed"):
        manager.sync()


def test_sync_propagates_pull_error(tmp_path):
    cfg = _cfg(tmp_path)
    cfg.working_dir.mkdir(parents=True)
    (cfg.working_dir / ".git").mkdir()
    provider = MagicMock()
    provider.pull.side_effect = RuntimeError("git pull failed (exit 1): conflict")
    manager = WorkingCopyManager(cfg, provider)

    with pytest.raises(RuntimeError, match="git pull failed"):
        manager.sync()
