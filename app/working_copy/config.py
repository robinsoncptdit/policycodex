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


def _from_credential_store() -> tuple[str, str] | None:
    """DISC followup: the Settings Policy Repository panel writes the repo URL + branch
    to the in-app credential store. Read from there before falling back to Django
    settings, which only see env vars set at container boot."""
    try:
        from app.credentials import store
        if store.has("policy_repo.url") and store.has("policy_repo.branch"):
            return store.get("policy_repo.url"), store.get("policy_repo.branch")
    except Exception:
        pass
    return None


def load_working_copy_config() -> WorkingCopyConfig:
    repo_url = getattr(settings, "POLICYCODEX_POLICY_REPO_URL", "")
    branch = getattr(settings, "POLICYCODEX_POLICY_BRANCH", "main")
    if not repo_url:
        from_store = _from_credential_store()
        if from_store is not None:
            repo_url, branch = from_store
    if not repo_url:
        raise RuntimeError(
            "POLICYCODEX_POLICY_REPO_URL is not set. Configure the diocese's policy repo URL "
            "(e.g., https://github.com/<org>/<repo>.git) via Django settings, env var, or the Settings page."
        )
    root_raw = getattr(settings, "POLICYCODEX_WORKING_COPY_ROOT", "")
    if not root_raw:
        # In Docker the entrypoint volume is /data. Outside Docker fall back to $HOME.
        root = Path("/data/working-copy") if Path("/data").exists() else Path.home() / ".policycodex" / "working-copies"
    else:
        root = Path(os.path.expanduser(root_raw))
    return WorkingCopyConfig(repo_url=repo_url, branch=branch, root=root)
