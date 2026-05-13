"""GitHub implementation of the GitProvider abstraction."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Optional

from github import Auth, Github

from app.git_provider.base import GitProvider
from app.git_provider.github_config import GitHubConfig, load_github_config


_REPO_RE = re.compile(r"^https://github\.com/([^/]+)/([^/.]+)(?:\.git)?/?$")


def _parse_owner_repo(origin_url: str) -> str:
    m = _REPO_RE.match(origin_url.strip())
    if not m:
        raise ValueError(f"Cannot parse owner/repo from origin URL: {origin_url}")
    return f"{m.group(1)}/{m.group(2)}"


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

    def commit(
        self,
        message: str,
        files: list[Path],
        author_name: str,
        author_email: str,
        working_dir: Path,
    ) -> str:
        for f in files:
            result = subprocess.run(
                ["git", "add", str(f)],
                cwd=working_dir,
                capture_output=True,
            )
            if result.returncode != 0:
                raise RuntimeError(
                    f"git add {f} failed (exit {result.returncode}): "
                    f"{result.stderr.decode(errors='replace')}"
                )
        commit_cmd = [
            "git",
            "-c", f"user.name={author_name}",
            "-c", f"user.email={author_email}",
            "commit",
            "-m", message,
        ]
        result = subprocess.run(commit_cmd, cwd=working_dir, capture_output=True)
        if result.returncode != 0:
            raise RuntimeError(
                f"git commit failed (exit {result.returncode}): "
                f"{result.stderr.decode(errors='replace')}"
            )
        rev = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=working_dir,
            capture_output=True,
        )
        if rev.returncode != 0:
            raise RuntimeError(
                f"git rev-parse HEAD failed (exit {rev.returncode}): "
                f"{rev.stderr.decode(errors='replace')}"
            )
        return rev.stdout.decode().strip()

    def push(self, branch: str, working_dir: Path) -> None:
        get_url = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=working_dir,
            capture_output=True,
        )
        if get_url.returncode != 0:
            raise RuntimeError(
                f"git remote get-url failed (exit {get_url.returncode}): "
                f"{get_url.stderr.decode(errors='replace')}"
            )
        origin_url = get_url.stdout.decode().strip()
        if not origin_url.startswith("https://github.com/"):
            raise ValueError(f"Origin is not an https://github.com/ URL: {origin_url}")
        token = self._installation_token()
        tokenized = origin_url.replace(
            "https://github.com/",
            f"https://x-access-token:{token}@github.com/",
            1,
        )
        result = subprocess.run(
            ["git", "push", tokenized, branch],
            cwd=working_dir,
            capture_output=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"git push failed (exit {result.returncode}): "
                f"{result.stderr.decode(errors='replace')}"
            )

    def open_pr(
        self,
        title: str,
        body: str,
        head_branch: str,
        base_branch: str,
        working_dir: Path,
    ) -> dict:
        get_url = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=working_dir,
            capture_output=True,
        )
        if get_url.returncode != 0:
            raise RuntimeError(
                f"git remote get-url failed (exit {get_url.returncode}): "
                f"{get_url.stderr.decode(errors='replace')}"
            )
        owner_repo = _parse_owner_repo(get_url.stdout.decode())
        repo = self._client.get_repo(owner_repo)
        pr = repo.create_pull(title=title, body=body, head=head_branch, base=base_branch)
        return {
            "pr_number": pr.number,
            "url": pr.html_url,
            "state": pr.state,
        }

    def read_pr_state(self, pr_number: int, working_dir: Path) -> str:
        get_url = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=working_dir,
            capture_output=True,
        )
        if get_url.returncode != 0:
            raise RuntimeError(
                f"git remote get-url failed (exit {get_url.returncode}): "
                f"{get_url.stderr.decode(errors='replace')}"
            )
        owner_repo = _parse_owner_repo(get_url.stdout.decode())
        repo = self._client.get_repo(owner_repo)
        pr = repo.get_pull(pr_number)
        if pr.merged:
            return "published"
        if pr.state == "closed":
            return "closed"
        approvals = sum(
            1 for r in pr.get_reviews() if getattr(r, "state", None) == "APPROVED"
        )
        return "reviewed" if approvals >= 1 else "drafted"
