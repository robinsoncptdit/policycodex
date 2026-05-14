"""Orchestrate clone-on-first-run + pull-on-existing for the policy working copy."""
from __future__ import annotations

from pathlib import Path

from app.git_provider.base import GitProvider
from app.working_copy.config import WorkingCopyConfig


class WorkingCopyManager:
    """Maintains a local clone of the diocese's policy repo.

    Idempotent: calling sync() clones on first invocation and pulls on
    subsequent invocations. Safe to invoke from a cron-driven management
    command or from the app's startup self-check.
    """

    def __init__(self, config: WorkingCopyConfig, provider: GitProvider) -> None:
        self._config = config
        self._provider = provider

    def sync(self) -> Path:
        wd = self._config.working_dir
        if wd.exists():
            if not (wd / ".git").exists():
                raise RuntimeError(
                    f"working copy path exists but is not a git repository: {wd}. "
                    f"Refusing to clone over existing content. Move or delete the directory "
                    f"and re-run."
                )
            self._provider.pull(self._config.branch, wd)
            return wd

        wd.parent.mkdir(parents=True, exist_ok=True)
        self._provider.clone(self._config.repo_url, wd)
        return wd
