"""GitHub implementation of the GitProvider abstraction."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Optional

from github import Auth, Github, GithubIntegration

from app.git_provider.base import GitProvider
from app.git_provider.github_config import GitHubConfig, load_github_config


_REPO_RE = re.compile(r"^https://github\.com/([^/]+)/(.+?)(?:\.git)?/?$")

_VALID_MERGE_METHODS = ("merge", "squash", "rebase")

# Phrases GitHub returns (HTTP 401) when a JWT's time claims are out of range.
# These almost always mean the host clock is skewed, not that the credentials
# are wrong, so we steer the operator to NTP instead of echoing a raw 401.
_CLOCK_SKEW_SIGNALS = ("expiration time", "issued at", "too far in the future")


def friendly_github_auth_error(exc: Exception) -> str:
    """Map a GitHub App auth failure to an admin-actionable message. JWT
    time-claim rejections are reported as a clock problem; everything else is
    passed through unchanged (with GitHub's original text kept either way)."""
    msg = str(exc)
    low = msg.lower()
    if any(sig in low for sig in _CLOCK_SKEW_SIGNALS):
        return (
            "GitHub rejected the App credentials because the request time looks "
            "wrong. This usually means the server clock is off — sync it (enable "
            f"NTP) and retry. (GitHub said: {msg})"
        )
    return msg


def list_app_installations(app_id: str, private_key_pem: str) -> list[dict]:
    """List the App's installations via PyGithub (which generates the JWT per
    GitHub's spec). Returns dicts with 'id' and 'target_type'. Raises
    RuntimeError with an admin-actionable message on any auth failure."""
    try:
        app_auth = Auth.AppAuth(int(app_id), private_key_pem)
        integration = GithubIntegration(auth=app_auth)
        return [
            {"id": inst.id, "target_type": inst.target_type}
            for inst in integration.get_installations()
        ]
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(friendly_github_auth_error(exc)) from exc


def _parse_owner_repo(origin_url: str) -> str:
    m = _REPO_RE.match(origin_url.strip())
    if not m:
        raise ValueError(f"Cannot parse owner/repo from origin URL: {origin_url}")
    return f"{m.group(1)}/{m.group(2)}"


def _build_installation_token(config: GitHubConfig) -> str:
    """Fetch a fresh installation access token (no caching)."""
    private_key = config.private_key_path.read_text(encoding="utf-8")
    app_auth = Auth.AppAuth(config.app_id, private_key)
    integration = GithubIntegration(auth=app_auth)
    access = integration.get_access_token(config.installation_id)
    return access.token


def _pr_to_gate(pr) -> str:
    """Map a PyGithub PullRequest object to a PolicyCodex gate string.

    Identical mapping rules to `GitHubProvider.read_pr_state`:
    merged -> "published", closed-not-merged -> "closed",
    open + at least one approving review -> "reviewed",
    otherwise (open + no approval) -> "drafted".
    """
    if pr.merged:
        return "published"
    if pr.state == "closed":
        return "closed"
    approvals = sum(
        1 for r in pr.get_reviews() if getattr(r, "state", None) == "APPROVED"
    )
    return "reviewed" if approvals >= 1 else "drafted"


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
            integration = GithubIntegration(auth=app_auth)
            install_auth = integration.get_github_for_installation(
                self._config.installation_id
            )
            # get_github_for_installation returns a Github instance directly
            self._client = install_auth

    @classmethod
    def test_credentials(cls, app_id: str, installation_id: str, private_key_pem: str) -> bool:
        """DISC-05: dry-run authentication. Returns True if the App can mint an
        installation token; raises RuntimeError with the GitHub message otherwise."""
        try:
            app_auth = Auth.AppAuth(int(app_id), private_key_pem)
            integration = GithubIntegration(auth=app_auth)
            integration.get_access_token(int(installation_id))
        except Exception as exc:
            raise RuntimeError(friendly_github_auth_error(exc)) from exc
        return True

    @classmethod
    def create_repository(cls, *, org: str, repo_name: str, private: bool = True) -> dict:
        """DISC-07: Create a private repo under an org via the installation access token.

        Returns a dict with at least 'clone_url'. Raises RuntimeError on failure.
        Mirrors test_credentials's JWT + token-exchange auth pattern.
        """
        from app.git_provider.github_config import load_github_config
        config = load_github_config()
        try:
            private_key = config.private_key_path.read_text(encoding="utf-8")
            app_auth = Auth.AppAuth(config.app_id, private_key)
            integration = GithubIntegration(auth=app_auth)
            gh = integration.get_github_for_installation(config.installation_id)
            github_org = gh.get_organization(org)
            repo = github_org.create_repo(name=repo_name, private=private, auto_init=True)
        except Exception as exc:
            raise RuntimeError(str(exc)) from exc
        return {
            "clone_url": repo.clone_url,
            "html_url": repo.html_url,
            "full_name": repo.full_name,
        }

    def _installation_token(self) -> str:
        return _build_installation_token(self._config)

    def list_installation_repos(self) -> list[dict]:
        """GET /installation/repositories using the installation token. Returns
        [{"full_name": "owner/repo", "default_branch": "main"}, ...]."""
        import requests
        token = self._installation_token()
        response = requests.get(
            "https://api.github.com/installation/repositories",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
            },
            timeout=10,
        )
        response.raise_for_status()
        return [
            {"full_name": r.get("full_name", ""), "default_branch": r.get("default_branch", "main")}
            for r in response.json().get("repositories", [])
            if r.get("full_name")
        ]

    def _origin_url(self, working_dir: Path) -> str:
        """Return the working copy's `origin` remote URL, stripped.

        Raises RuntimeError if `git remote get-url origin` fails.
        """
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
        return get_url.stdout.decode().strip()

    def _resolve_repo(self, working_dir: Path):
        """Resolve the working copy's `origin` to a PyGithub Repository.

        Combines the origin-URL lookup, owner/repo parse, and
        `client.get_repo` call shared by every PR-related provider method.
        """
        owner_repo = _parse_owner_repo(self._origin_url(working_dir))
        return self._client.get_repo(owner_repo)

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
            # Strip any tokenized URL from stderr before raising
            stderr = result.stderr.decode(errors="replace").replace(token, "<redacted>")
            raise RuntimeError(
                f"git clone failed (exit {result.returncode}): {stderr}"
            )
        # Reset origin to clean URL so the token is not persisted on disk.
        # push() fetches a fresh token and rewrites the URL on each call.
        reset = subprocess.run(
            ["git", "remote", "set-url", "origin", repo_url],
            cwd=dest,
            capture_output=True,
        )
        if reset.returncode != 0:
            raise RuntimeError(
                f"git remote set-url origin failed (exit {reset.returncode}): "
                f"{reset.stderr.decode(errors='replace')}"
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
        origin_url = self._origin_url(working_dir)
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
            stderr = result.stderr.decode(errors="replace").replace(token, "<redacted>")
            raise RuntimeError(
                f"git push failed (exit {result.returncode}): {stderr}"
            )

    def pull(self, branch: str, working_dir: Path) -> None:
        origin_url = self._origin_url(working_dir)
        if not origin_url.startswith("https://github.com/"):
            raise ValueError(f"Origin is not an https://github.com/ URL: {origin_url}")
        token = self._installation_token()
        tokenized = origin_url.replace(
            "https://github.com/",
            f"https://x-access-token:{token}@github.com/",
            1,
        )
        result = subprocess.run(
            ["git", "pull", tokenized, branch],
            cwd=working_dir,
            capture_output=True,
        )
        if result.returncode != 0:
            stderr = result.stderr.decode(errors="replace").replace(token, "<redacted>")
            raise RuntimeError(
                f"git pull failed (exit {result.returncode}): {stderr}"
            )

    def open_pr(
        self,
        title: str,
        body: str,
        head_branch: str,
        base_branch: str,
        working_dir: Path,
    ) -> dict:
        repo = self._resolve_repo(working_dir)
        pr = repo.create_pull(title=title, body=body, head=head_branch, base=base_branch)
        return {
            "pr_number": pr.number,
            "url": pr.html_url,
            "state": pr.state,
        }

    def read_pr_state(self, pr_number: int, working_dir: Path) -> str:
        repo = self._resolve_repo(working_dir)
        pr = repo.get_pull(pr_number)
        return _pr_to_gate(pr)

    def list_open_prs(self, working_dir: Path) -> list[dict]:
        """Batched alternative to read_pr_state: one API call returns all open
        PRs along with their head branch + gate state, so the catalog view can
        build a {slug: gate} map without N round-trips."""
        repo = self._resolve_repo(working_dir)
        result: list[dict] = []
        for pr in repo.get_pulls(state="open"):
            result.append({
                "pr_number": pr.number,
                "head_branch": pr.head.ref,
                "gate": _pr_to_gate(pr),
                "url": pr.html_url,
            })
        return result

    def approve_pr(
        self,
        pr_number: int,
        working_dir: Path,
        body: str = "",
    ) -> dict:
        repo = self._resolve_repo(working_dir)
        pr = repo.get_pull(pr_number)
        review = pr.create_review(body=body, event="APPROVE")
        return {
            "review_id": review.id,
            "state": review.state,
            "pr_number": pr_number,
        }

    def merge_pr(
        self,
        pr_number: int,
        working_dir: Path,
        merge_method: str = "squash",
    ) -> dict:
        if merge_method not in _VALID_MERGE_METHODS:
            raise ValueError(
                f"merge_method must be one of {_VALID_MERGE_METHODS}, got {merge_method!r}"
            )
        repo = self._resolve_repo(working_dir)
        pr = repo.get_pull(pr_number)
        try:
            # PyGithub forwards keyword args to the PUT /merge endpoint.
            # commit_title and commit_message default to GitHub's auto-generated
            # values when omitted, which is fine for v0.1 (the PR title is
            # already structured by APP-07's edit flow).
            result = pr.merge(merge_method=merge_method)
        except Exception as exc:
            # PyGithub raises GithubException for HTTP errors (409 conflict,
            # 405 branch-protection-block, 422 unmergeable, 403 rate-limit).
            # Wrap in RuntimeError so callers in the view layer can render a
            # consistent flash message without depending on PyGithub.
            raise RuntimeError(
                f"merge_pr failed for PR #{pr_number}: {exc}"
            ) from exc
        if not getattr(result, "merged", False):
            raise RuntimeError(
                f"merge_pr returned not merged for PR #{pr_number}; "
                f"the PR may have been updated between read and merge"
            )
        return {
            "merged": True,
            "sha": result.sha,
            "merge_method": merge_method,
        }
