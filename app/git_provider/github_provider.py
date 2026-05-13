"""GitHub implementation of the GitProvider abstraction."""
from __future__ import annotations

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

    def clone(self, repo_url, dest):
        raise NotImplementedError

    def branch(self, name, working_dir):
        raise NotImplementedError

    def commit(self, message, files, author_name, author_email, working_dir):
        raise NotImplementedError

    def push(self, branch, working_dir):
        raise NotImplementedError

    def open_pr(self, title, body, head_branch, base_branch, working_dir):
        raise NotImplementedError

    def read_pr_state(self, pr_number, working_dir):
        raise NotImplementedError
