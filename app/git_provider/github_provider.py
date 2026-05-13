"""GitHub implementation of the GitProvider abstraction."""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional

from github import Auth, Github

from app.git_provider.base import GitProvider
from app.git_provider.github_config import GitHubConfig, load_github_config


def _build_installation_token(config: GitHubConfig) -> str:
    """Fetch a fresh installation access token (no caching)."""
    private_key = config.private_key_path.read_text(encoding="utf-8")
    app_auth = Auth.AppAuth(config.app_id, private_key)
    install_auth = app_auth.get_installation_auth(config.installation_id)
    return install_auth.token


class GitHubProvider(GitProvider):
    def __init__(
        self,
        config: Optional[GitHubConfig] = None,
        github_client: Optional[Github] = None,
    ) -> None:
        self._config = config if config is not None else load_github_config()
        if github_client is not None:
            self._client = github_client
        else:
            private_key = self._config.private_key_path.read_text(encoding="utf-8")
            app_auth = Auth.AppAuth(self._config.app_id, private_key)
            install_auth = app_auth.get_installation_auth(self._config.installation_id)
            self._client = Github(auth=install_auth)

    def _installation_token(self) -> str:
        return _build_installation_token(self._config)

    def clone(self, repo_url: str, dest: Path) -> None:
        if not repo_url.startswith("https://github.com/"):
            raise ValueError(
                f"GitHubProvider only supports https://github.com/ URLs, got {repo_url}"
            )
        token = self._installation_token()
        tokenized = repo_url.replace(
            "https://github.com/",
            f"https://x-access-token:{token}@github.com/",
            1,
        )
        result = subprocess.run(
            ["git", "clone", tokenized, str(dest)],
            capture_output=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"git clone failed (exit {result.returncode}): "
                f"{result.stderr.decode(errors='replace')}"
            )

    def branch(self, name: str, working_dir: Path) -> None:
        result = subprocess.run(
            ["git", "checkout", "-b", name],
            cwd=working_dir,
            capture_output=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"git checkout -b failed (exit {result.returncode}): "
                f"{result.stderr.decode(errors='replace')}"
            )

    def commit(self, message, files, author_name, author_email, working_dir):
        raise NotImplementedError

    def push(self, branch, working_dir):
        raise NotImplementedError

    def open_pr(self, title, body, head_branch, base_branch, working_dir):
        raise NotImplementedError

    def read_pr_state(self, pr_number, working_dir):
        raise NotImplementedError
