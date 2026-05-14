"""Configuration for the local working copy of the diocese's policy repo."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings


@dataclass(frozen=True)
class WorkingCopyConfig:
    repo_url: str
    branch: str
    root: Path

    @property
    def working_dir(self) -> Path:
        """Local path to the cloned repo under the working-copy root."""
        name = self.repo_url.rstrip("/").rsplit("/", 1)[-1]
        if name.endswith(".git"):
            name = name[:-4]
        return self.root / name


def load_working_copy_config() -> WorkingCopyConfig:
    repo_url = getattr(settings, "POLICYCODEX_POLICY_REPO_URL", "")
    if not repo_url:
        raise RuntimeError(
            "POLICYCODEX_POLICY_REPO_URL is not set. Configure the diocese's policy repo URL "
            "(e.g., https://github.com/<org>/<repo>.git) via Django settings or env var."
        )
    branch = getattr(settings, "POLICYCODEX_POLICY_BRANCH", "main")
    root_raw = getattr(settings, "POLICYCODEX_WORKING_COPY_ROOT", "")
    if not root_raw:
        root = Path.home() / ".policycodex" / "working-copies"
    else:
        root = Path(os.path.expanduser(root_raw))
    return WorkingCopyConfig(repo_url=repo_url, branch=branch, root=root)
