# APP-04 GitHub Provider Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Concrete `GitHubProvider(GitProvider)` implementing the 6 ABC methods from `app/git_provider/base.py` end-to-end against the PT test repo. Central Week-2 bottleneck — 8+ downstream tickets gated on this.

**Architecture:** GitHubProvider combines PyGithub (>=2.0, native App auth) for API ops (open_pr, read_pr_state) with `subprocess` for git CLI ops (clone, branch, commit, push). A separate `GitHubConfig` dataclass + loader reads App credentials from `~/.config/policycodex/config.env` (path overridable via `POLICYCODEX_CONFIG_PATH`). For clone/push, the App's installation access token gets injected into the HTTPS URL (`https://x-access-token:<tok>@github.com/...`); fresh token per call (no caching for v0.1). Commit author identity flows from the `commit(author_name, author_email, ...)` args via `git -c user.name=... -c user.email=...`. PR state mapping per the ABC docstring: drafted=open+no-approvals, reviewed=open+≥1-approval, published=merged, closed=closed-not-merged.

**Tech Stack:** Python 3.12, `PyGithub>=2.0`, stdlib (`subprocess`, `pathlib`, `dataclasses`), pytest.

**Ticket reference:** `PolicyWonk-v0.1-Tickets.md` APP-04. Depends on APP-03 (`app/git_provider/base.py`, landed at `cf4b6c2`) and REPO-03/04 (App installed on PT, credentials at `~/.config/policycodex/config.env`).

---

## File Structure

- Create: `app/git_provider/github_config.py` — `GitHubConfig` dataclass + `load_github_config()` loader.
- Create: `app/git_provider/github_provider.py` — `GitHubProvider(GitProvider)`.
- Create: `app/git_provider/tests/test_github_config.py` — config loader tests.
- Create: `app/git_provider/tests/test_github_provider.py` — provider unit tests (mocked PyGithub + mocked subprocess).
- Modify: `app/git_provider/__init__.py` — re-export `GitHubProvider`.
- Modify: `app/requirements.txt` — add `PyGithub>=2.0`.

**Existing context (read once at start):**
- `app/git_provider/base.py` — the ABC. The 6 method signatures land VERBATIM in `GitHubProvider`. Reference it for arg names/types/docstrings.
- `ai/claude_provider.py` (post-merge) — the canonical SDK-wrapper pattern for this repo. Mirror its style for constructor injection (`client=None` for testability), `getattr` defensive access on mock objects, error propagation policy.
- `ai/tests/test_claude_provider.py` — the canonical mocking pattern (`MagicMock`, `_mock_anthropic_response` builder). Mirror for `_mock_github_pr` etc.

**Config file shape (already standardized by REPO-03):** `~/.config/policycodex/config.env` contains shell-style `KEY=VALUE` lines. The keys this plan reads:
- `POLICYCODEX_GH_APP_ID` — numeric App ID.
- `POLICYCODEX_GH_INSTALLATION_ID` — per-org install ID.
- `POLICYCODEX_GH_PRIVATE_KEY_PATH` — absolute path to the `.pem` file.

Other keys (`POLICYCODEX_GH_CLIENT_ID`, `POLICYCODEX_GH_CLIENT_SECRET`, `POLICYCODEX_GH_APP_NAME`) exist in the file but are not consumed by APP-04.

---

## Task 1: Add PyGithub to requirements

**Files:** Modify `app/requirements.txt`.

- [ ] **Step 1: Append `PyGithub>=2.0`** to `app/requirements.txt`. Keep existing entries (`django>=5.0`, `pytest>=7.4`, `pytest-django>=4.8`).

- [ ] **Step 2: Install** in your venv:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r app/requirements.txt
```

Expected: PyGithub 2.x installed; no errors.

- [ ] **Step 3: Verify import:** `python -c "from github import Auth, Github; print(Github.__module__)"` — expect `github.MainClass` or similar (any non-error).

- [ ] **Step 4: Commit:**

```bash
git add app/requirements.txt
git commit -m "chore(APP-04): add PyGithub>=2.0 for GitHub App auth + API"
```

---

## Task 2: GitHubConfig dataclass + loader

**Files:** Create `app/git_provider/github_config.py`, `app/git_provider/tests/test_github_config.py`.

- [ ] **Step 1: Write the failing tests** in `app/git_provider/tests/test_github_config.py`:

```python
"""Tests for GitHub App config loader."""
import os
from pathlib import Path

import pytest

from app.git_provider.github_config import GitHubConfig, load_github_config


def _write_config(tmp_path: Path, lines: list[str]) -> Path:
    config_file = tmp_path / "config.env"
    config_file.write_text("\n".join(lines) + "\n")
    return config_file


def test_load_config_reads_required_keys(tmp_path, monkeypatch):
    config_file = _write_config(tmp_path, [
        "POLICYCODEX_GH_APP_ID=12345",
        "POLICYCODEX_GH_INSTALLATION_ID=67890",
        f"POLICYCODEX_GH_PRIVATE_KEY_PATH={tmp_path}/key.pem",
    ])
    monkeypatch.setenv("POLICYCODEX_CONFIG_PATH", str(config_file))
    cfg = load_github_config()
    assert cfg.app_id == 12345
    assert cfg.installation_id == 67890
    assert cfg.private_key_path == tmp_path / "key.pem"


def test_load_config_defaults_to_home_config_path(tmp_path, monkeypatch):
    # POLICYCODEX_CONFIG_PATH unset → default ~/.config/policycodex/config.env
    monkeypatch.delenv("POLICYCODEX_CONFIG_PATH", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    config_dir = tmp_path / ".config" / "policycodex"
    config_dir.mkdir(parents=True)
    _write_config(config_dir, [
        "POLICYCODEX_GH_APP_ID=1",
        "POLICYCODEX_GH_INSTALLATION_ID=2",
        f"POLICYCODEX_GH_PRIVATE_KEY_PATH={tmp_path}/k.pem",
    ]).rename(config_dir / "config.env")
    cfg = load_github_config()
    assert cfg.app_id == 1


def test_load_config_ignores_comments_and_blank_lines(tmp_path, monkeypatch):
    config_file = _write_config(tmp_path, [
        "# leading comment",
        "",
        "POLICYCODEX_GH_APP_ID=42",
        "  # indented comment",
        "POLICYCODEX_GH_INSTALLATION_ID=43",
        f"POLICYCODEX_GH_PRIVATE_KEY_PATH={tmp_path}/k.pem",
    ])
    monkeypatch.setenv("POLICYCODEX_CONFIG_PATH", str(config_file))
    cfg = load_github_config()
    assert cfg.app_id == 42


def test_load_config_strips_surrounding_quotes(tmp_path, monkeypatch):
    config_file = _write_config(tmp_path, [
        'POLICYCODEX_GH_APP_ID="42"',
        "POLICYCODEX_GH_INSTALLATION_ID='43'",
        f'POLICYCODEX_GH_PRIVATE_KEY_PATH="{tmp_path}/k.pem"',
    ])
    monkeypatch.setenv("POLICYCODEX_CONFIG_PATH", str(config_file))
    cfg = load_github_config()
    assert cfg.app_id == 42
    assert cfg.installation_id == 43


def test_load_config_raises_on_missing_file(tmp_path, monkeypatch):
    monkeypatch.setenv("POLICYCODEX_CONFIG_PATH", str(tmp_path / "missing.env"))
    with pytest.raises(FileNotFoundError):
        load_github_config()


def test_load_config_raises_on_missing_required_key(tmp_path, monkeypatch):
    config_file = _write_config(tmp_path, [
        "POLICYCODEX_GH_APP_ID=1",
        # POLICYCODEX_GH_INSTALLATION_ID missing
        f"POLICYCODEX_GH_PRIVATE_KEY_PATH={tmp_path}/k.pem",
    ])
    monkeypatch.setenv("POLICYCODEX_CONFIG_PATH", str(config_file))
    with pytest.raises(ValueError, match="POLICYCODEX_GH_INSTALLATION_ID"):
        load_github_config()
```

- [ ] **Step 2: Run tests to verify failure:**

```bash
python -m pytest app/git_provider/tests/test_github_config.py -v
```

Expected: ImportError, all 6 fail.

- [ ] **Step 3: Implement** in `app/git_provider/github_config.py`:

```python
"""GitHub App configuration loader (read-only, no caching)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class GitHubConfig:
    app_id: int
    installation_id: int
    private_key_path: Path


def _parse_value(raw: str) -> str:
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in ('"', "'"):
        return raw[1:-1]
    return raw


def _parse_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        raise FileNotFoundError(f"PolicyCodex config not found at {path}")
    result: dict[str, str] = {}
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, raw_value = line.partition("=")
            result[key.strip()] = _parse_value(raw_value)
    return result


def _default_config_path() -> Path:
    return Path(os.path.expanduser("~/.config/policycodex/config.env"))


def load_github_config(path: Path | None = None) -> GitHubConfig:
    if path is None:
        env_override = os.getenv("POLICYCODEX_CONFIG_PATH")
        path = Path(env_override) if env_override else _default_config_path()
    values = _parse_env_file(path)
    required = ("POLICYCODEX_GH_APP_ID", "POLICYCODEX_GH_INSTALLATION_ID", "POLICYCODEX_GH_PRIVATE_KEY_PATH")
    missing = [k for k in required if k not in values or not values[k]]
    if missing:
        raise ValueError(f"Missing required keys in {path}: {missing}")
    return GitHubConfig(
        app_id=int(values["POLICYCODEX_GH_APP_ID"]),
        installation_id=int(values["POLICYCODEX_GH_INSTALLATION_ID"]),
        private_key_path=Path(values["POLICYCODEX_GH_PRIVATE_KEY_PATH"]),
    )
```

- [ ] **Step 4: Run tests to verify pass.**

- [ ] **Step 5: Commit:**

```bash
git add app/git_provider/github_config.py app/git_provider/tests/test_github_config.py
git commit -m "feat(APP-04): GitHubConfig dataclass + config.env loader"
```

---

## Task 3: GitHubProvider scaffold + auth helper

**Files:** Create `app/git_provider/github_provider.py`, `app/git_provider/tests/test_github_provider.py`.

- [ ] **Step 1: Write the failing tests:**

```python
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


def test_constructor_loads_config_by_default(tmp_path, monkeypatch):
    """If config not passed, load_github_config is called."""
    fake_cfg = _fake_config(tmp_path)
    (tmp_path / "key.pem").write_text("FAKE PEM")
    with patch("app.git_provider.github_provider.load_github_config", return_value=fake_cfg) as loader:
        p = GitHubProvider(github_client=MagicMock())
    loader.assert_called_once()
    assert p._config is fake_cfg


def test_installation_token_fetched_via_app_auth(tmp_path):
    cfg = _fake_config(tmp_path)
    (tmp_path / "key.pem").write_text("FAKE PEM")
    mock_client = MagicMock()
    mock_app = MagicMock()
    mock_install = MagicMock()
    mock_install.token = "ghs_fake_token_xyz"
    mock_app.get_access_token.return_value = mock_install
    mock_client.get_app.return_value.get_installation.return_value = mock_install
    # Patch the PyGithub auth path to return a known token
    with patch("app.git_provider.github_provider._build_installation_token", return_value="ghs_fake_token_xyz") as builder:
        p = GitHubProvider(config=cfg, github_client=mock_client)
        token = p._installation_token()
    assert token == "ghs_fake_token_xyz"
    builder.assert_called_once_with(cfg)
```

- [ ] **Step 2: Run tests to verify failure** (ImportError).

- [ ] **Step 3: Implement** in `app/git_provider/github_provider.py`:

```python
"""GitHub implementation of the GitProvider abstraction."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from github import Auth, Github

from app.git_provider.base import GitProvider
from app.git_provider.github_config import GitHubConfig, load_github_config


def _build_installation_token(config: GitHubConfig) -> str:
    """Fetch a fresh installation access token for the configured GitHub App.

    Reads the .pem off disk every call (no caching). Tokens have ~1h
    TTL; downstream callers regenerate per operation.
    """
    private_key = config.private_key_path.read_text(encoding="utf-8")
    app_auth = Auth.AppAuth(config.app_id, private_key)
    install_auth = app_auth.get_installation_auth(config.installation_id)
    return install_auth.token


class GitHubProvider(GitProvider):
    """GitProvider backed by PyGithub (API ops) + subprocess git (CLI ops).

    Auth: GitHub App credentials are loaded from
    ~/.config/policycodex/config.env (overridable via POLICYCODEX_CONFIG_PATH).
    Each push/clone fetches a fresh installation access token; PyGithub
    requests reuse the constructor-built `github_client`.
    """

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

    # ABC methods land in Tasks 4-9 below.
    def clone(self, repo_url, dest):
        raise NotImplementedError  # Task 4

    def branch(self, name, working_dir):
        raise NotImplementedError  # Task 5

    def commit(self, message, files, author_name, author_email, working_dir):
        raise NotImplementedError  # Task 6

    def push(self, branch, working_dir):
        raise NotImplementedError  # Task 7

    def open_pr(self, title, body, head_branch, base_branch, working_dir):
        raise NotImplementedError  # Task 8

    def read_pr_state(self, pr_number, working_dir):
        raise NotImplementedError  # Task 9
```

- [ ] **Step 4: Run tests to verify the 3 scaffold tests pass.**

- [ ] **Step 5: Commit:**

```bash
git add app/git_provider/github_provider.py app/git_provider/tests/test_github_provider.py
git commit -m "feat(APP-04): GitHubProvider scaffold + installation-token helper"
```

---

## Task 4: clone() with token-in-URL

**Files:** Modify `app/git_provider/github_provider.py`, `app/git_provider/tests/test_github_provider.py`.

- [ ] **Step 1: Append failing tests:**

```python
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
```

- [ ] **Step 2: Verify fail.**

- [ ] **Step 3: Implement.** Add to the top of `github_provider.py`:

```python
import subprocess
```

Replace `clone` stub:

```python
def clone(self, repo_url: str, dest: Path) -> None:
    if not repo_url.startswith("https://github.com/"):
        raise ValueError(f"GitHubProvider only supports https://github.com/ URLs, got {repo_url}")
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
        raise RuntimeError(f"git clone failed (exit {result.returncode}): {result.stderr.decode(errors='replace')}")
```

- [ ] **Step 4: Verify pass.**

- [ ] **Step 5: Commit:**

```bash
git add app/git_provider/github_provider.py app/git_provider/tests/test_github_provider.py
git commit -m "feat(APP-04): GitHubProvider.clone via tokenized HTTPS URL + subprocess"
```

---

## Task 5: branch()

**Files:** Modify provider + tests.

- [ ] **Step 1: Append failing test:**

```python
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
```

- [ ] **Step 2: Verify fail.**

- [ ] **Step 3: Implement:**

```python
def branch(self, name: str, working_dir: Path) -> None:
    result = subprocess.run(
        ["git", "checkout", "-b", name],
        cwd=working_dir,
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git checkout -b failed (exit {result.returncode}): {result.stderr.decode(errors='replace')}")
```

- [ ] **Step 4: Verify pass.**

- [ ] **Step 5: Commit:**

```bash
git add app/git_provider/github_provider.py app/git_provider/tests/test_github_provider.py
git commit -m "feat(APP-04): GitHubProvider.branch via git checkout -b"
```

---

## Task 6: commit() with per-call author identity

**Files:** Modify provider + tests.

- [ ] **Step 1: Append failing tests:**

```python
def test_commit_stages_files_then_commits_with_identity(tmp_path):
    cfg = _fake_config(tmp_path)
    (tmp_path / "key.pem").write_text("FAKE PEM")
    wd = tmp_path / "wd"
    files = [Path("policies/hr/onboarding.md"), Path("policies/finance/budget.md")]
    with patch("app.git_provider.github_provider.subprocess.run") as run:
        # Two add calls (one per file), then commit, then rev-parse for SHA.
        run.side_effect = [
            MagicMock(returncode=0),  # git add file 1
            MagicMock(returncode=0),  # git add file 2
            MagicMock(returncode=0),  # git commit
            MagicMock(returncode=0, stdout=b"abc1234567890\n"),  # git rev-parse HEAD
        ]
        p = GitHubProvider(config=cfg, github_client=MagicMock())
        sha = p.commit(
            message="Update HR onboarding",
            files=files,
            author_name="Pat Editor",
            author_email="pat@diocese-pt.example",
            working_dir=wd,
        )
    assert sha == "abc1234567890"
    add1 = run.call_args_list[0]
    assert add1[0][0] == ["git", "add", "policies/hr/onboarding.md"]
    assert add1[1]["cwd"] == wd
    commit_call = run.call_args_list[2]
    cmd = commit_call[0][0]
    assert cmd[:5] == ["git", "-c", "user.name=Pat Editor", "-c", "user.email=pat@diocese-pt.example"]
    assert "commit" in cmd
    assert "-m" in cmd
    assert "Update HR onboarding" in cmd


def test_commit_raises_on_nonzero_exit(tmp_path):
    cfg = _fake_config(tmp_path)
    (tmp_path / "key.pem").write_text("FAKE PEM")
    with patch("app.git_provider.github_provider.subprocess.run") as run:
        run.side_effect = [MagicMock(returncode=0), MagicMock(returncode=1, stderr=b"nothing to commit")]
        p = GitHubProvider(config=cfg, github_client=MagicMock())
        with pytest.raises(RuntimeError, match="git commit"):
            p.commit("msg", [Path("a.md")], "n", "e", tmp_path / "wd")
```

- [ ] **Step 2: Verify fail.**

- [ ] **Step 3: Implement:**

```python
def commit(
    self,
    message: str,
    files: list[Path],
    author_name: str,
    author_email: str,
    working_dir: Path,
) -> str:
    for f in files:
        result = subprocess.run(["git", "add", str(f)], cwd=working_dir, capture_output=True)
        if result.returncode != 0:
            raise RuntimeError(f"git add {f} failed (exit {result.returncode}): {result.stderr.decode(errors='replace')}")
    commit_cmd = [
        "git",
        "-c", f"user.name={author_name}",
        "-c", f"user.email={author_email}",
        "commit",
        "-m", message,
    ]
    result = subprocess.run(commit_cmd, cwd=working_dir, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(f"git commit failed (exit {result.returncode}): {result.stderr.decode(errors='replace')}")
    rev = subprocess.run(["git", "rev-parse", "HEAD"], cwd=working_dir, capture_output=True)
    if rev.returncode != 0:
        raise RuntimeError(f"git rev-parse HEAD failed (exit {rev.returncode}): {rev.stderr.decode(errors='replace')}")
    return rev.stdout.decode().strip()
```

- [ ] **Step 4: Verify pass.**

- [ ] **Step 5: Commit:**

```bash
git add app/git_provider/github_provider.py app/git_provider/tests/test_github_provider.py
git commit -m "feat(APP-04): GitHubProvider.commit with per-call user.name/email"
```

---

## Task 7: push() with token-in-URL

**Files:** Modify provider + tests.

- [ ] **Step 1: Append failing test:**

```python
def test_push_rewrites_remote_url_with_token(tmp_path):
    cfg = _fake_config(tmp_path)
    (tmp_path / "key.pem").write_text("FAKE PEM")
    wd = tmp_path / "wd"
    with patch("app.git_provider.github_provider._build_installation_token", return_value="ghs_PUSH"):
        with patch("app.git_provider.github_provider.subprocess.run") as run:
            run.side_effect = [
                MagicMock(returncode=0, stdout=b"https://github.com/foo/bar.git\n"),  # git remote get-url origin
                MagicMock(returncode=0),  # git push with tokenized URL
            ]
            p = GitHubProvider(config=cfg, github_client=MagicMock())
            p.push("policycodex/draft-foo", wd)
    push_call = run.call_args_list[1]
    cmd = push_call[0][0]
    assert cmd[0] == "git"
    assert cmd[1] == "push"
    assert any("x-access-token:ghs_PUSH@github.com/foo/bar.git" in c for c in cmd)
    assert "policycodex/draft-foo" in cmd


def test_push_raises_on_nonzero_exit(tmp_path):
    cfg = _fake_config(tmp_path)
    (tmp_path / "key.pem").write_text("FAKE PEM")
    with patch("app.git_provider.github_provider._build_installation_token", return_value="t"):
        with patch("app.git_provider.github_provider.subprocess.run") as run:
            run.side_effect = [
                MagicMock(returncode=0, stdout=b"https://github.com/foo/bar.git\n"),
                MagicMock(returncode=1, stderr=b"rejected"),
            ]
            p = GitHubProvider(config=cfg, github_client=MagicMock())
            with pytest.raises(RuntimeError, match="git push"):
                p.push("br", tmp_path / "wd")
```

- [ ] **Step 2: Verify fail.**

- [ ] **Step 3: Implement:**

```python
def push(self, branch: str, working_dir: Path) -> None:
    get_url = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=working_dir,
        capture_output=True,
    )
    if get_url.returncode != 0:
        raise RuntimeError(f"git remote get-url failed (exit {get_url.returncode}): {get_url.stderr.decode(errors='replace')}")
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
        raise RuntimeError(f"git push failed (exit {result.returncode}): {result.stderr.decode(errors='replace')}")
```

- [ ] **Step 4: Verify pass.**

- [ ] **Step 5: Commit:**

```bash
git add app/git_provider/github_provider.py app/git_provider/tests/test_github_provider.py
git commit -m "feat(APP-04): GitHubProvider.push via tokenized origin URL"
```

---

## Task 8: open_pr()

**Files:** Modify provider + tests.

- [ ] **Step 1: Append failing test:**

```python
def test_open_pr_uses_repo_from_origin_and_returns_metadata(tmp_path):
    cfg = _fake_config(tmp_path)
    (tmp_path / "key.pem").write_text("FAKE PEM")
    wd = tmp_path / "wd"
    fake_pr = MagicMock(number=42, html_url="https://github.com/foo/bar/pull/42", state="open")
    fake_repo = MagicMock()
    fake_repo.create_pull.return_value = fake_pr
    fake_client = MagicMock()
    fake_client.get_repo.return_value = fake_repo
    with patch("app.git_provider.github_provider.subprocess.run") as run:
        run.return_value = MagicMock(returncode=0, stdout=b"https://github.com/foo/bar.git\n")
        p = GitHubProvider(config=cfg, github_client=fake_client)
        result = p.open_pr(
            title="Draft: policies/hr/onboarding.md",
            body="Opened by PolicyCodex on behalf of Pat Editor",
            head_branch="policycodex/draft-foo",
            base_branch="main",
            working_dir=wd,
        )
    fake_client.get_repo.assert_called_once_with("foo/bar")
    fake_repo.create_pull.assert_called_once_with(
        title="Draft: policies/hr/onboarding.md",
        body="Opened by PolicyCodex on behalf of Pat Editor",
        head="policycodex/draft-foo",
        base="main",
    )
    assert result == {
        "pr_number": 42,
        "url": "https://github.com/foo/bar/pull/42",
        "state": "open",
    }
```

- [ ] **Step 2: Verify fail.**

- [ ] **Step 3: Implement.** Add a helper for the origin → `owner/repo` extraction near the top of the file:

```python
import re

_REPO_RE = re.compile(r"^https://github\.com/([^/]+)/([^/.]+)(?:\.git)?/?$")


def _parse_owner_repo(origin_url: str) -> str:
    m = _REPO_RE.match(origin_url.strip())
    if not m:
        raise ValueError(f"Cannot parse owner/repo from origin URL: {origin_url}")
    return f"{m.group(1)}/{m.group(2)}"
```

Replace `open_pr` stub:

```python
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
        raise RuntimeError(f"git remote get-url failed (exit {get_url.returncode}): {get_url.stderr.decode(errors='replace')}")
    owner_repo = _parse_owner_repo(get_url.stdout.decode())
    repo = self._client.get_repo(owner_repo)
    pr = repo.create_pull(title=title, body=body, head=head_branch, base=base_branch)
    return {
        "pr_number": pr.number,
        "url": pr.html_url,
        "state": pr.state,
    }
```

- [ ] **Step 4: Verify pass.**

- [ ] **Step 5: Commit:**

```bash
git add app/git_provider/github_provider.py app/git_provider/tests/test_github_provider.py
git commit -m "feat(APP-04): GitHubProvider.open_pr via PyGithub create_pull"
```

---

## Task 9: read_pr_state() with full state mapping

**Files:** Modify provider + tests.

This is the interesting one. The ABC docstring requires:
- "drafted" = open PR, no approving reviews
- "reviewed" = open PR, ≥1 approving review
- "published" = merged
- "closed" = closed without merge

Approval detection: count PyGithub PR reviews where `state == "APPROVED"`. Use the current count (not deduplicated by reviewer; multiple approvals from the same person still count as ≥1). This is a v0.1 simplification — dismissed/stale approvals are not separately tracked.

- [ ] **Step 1: Append failing tests:**

```python
@pytest.mark.parametrize("pr_state,merged,approvals,expected", [
    ("open", False, 0, "drafted"),
    ("open", False, 1, "reviewed"),
    ("open", False, 3, "reviewed"),
    ("closed", True, 0, "published"),
    ("closed", True, 2, "published"),
    ("closed", False, 0, "closed"),
    ("closed", False, 1, "closed"),
])
def test_read_pr_state_mapping(tmp_path, pr_state, merged, approvals, expected):
    cfg = _fake_config(tmp_path)
    (tmp_path / "key.pem").write_text("FAKE PEM")
    wd = tmp_path / "wd"
    review_mocks = []
    for _ in range(approvals):
        rv = MagicMock(); rv.state = "APPROVED"; review_mocks.append(rv)
    # Add some non-approving noise to ensure filtering works
    noise = MagicMock(); noise.state = "COMMENTED"
    review_mocks.append(noise)
    fake_pr = MagicMock(state=pr_state, merged=merged)
    fake_pr.get_reviews.return_value = review_mocks
    fake_repo = MagicMock()
    fake_repo.get_pull.return_value = fake_pr
    fake_client = MagicMock()
    fake_client.get_repo.return_value = fake_repo
    with patch("app.git_provider.github_provider.subprocess.run") as run:
        run.return_value = MagicMock(returncode=0, stdout=b"https://github.com/foo/bar.git\n")
        p = GitHubProvider(config=cfg, github_client=fake_client)
        assert p.read_pr_state(123, wd) == expected
    fake_repo.get_pull.assert_called_once_with(123)
```

- [ ] **Step 2: Verify fail.**

- [ ] **Step 3: Implement:**

```python
def read_pr_state(self, pr_number: int, working_dir: Path) -> str:
    get_url = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=working_dir,
        capture_output=True,
    )
    if get_url.returncode != 0:
        raise RuntimeError(f"git remote get-url failed (exit {get_url.returncode}): {get_url.stderr.decode(errors='replace')}")
    owner_repo = _parse_owner_repo(get_url.stdout.decode())
    repo = self._client.get_repo(owner_repo)
    pr = repo.get_pull(pr_number)
    if pr.merged:
        return "published"
    if pr.state == "closed":
        return "closed"
    approvals = sum(1 for r in pr.get_reviews() if getattr(r, "state", None) == "APPROVED")
    return "reviewed" if approvals >= 1 else "drafted"
```

- [ ] **Step 4: Verify pass (all 7 parametrized cases).**

- [ ] **Step 5: Commit:**

```bash
git add app/git_provider/github_provider.py app/git_provider/tests/test_github_provider.py
git commit -m "feat(APP-04): GitHubProvider.read_pr_state with drafted/reviewed/published/closed mapping"
```

---

## Task 10: Re-export from app/git_provider/__init__.py

**Files:** Modify `app/git_provider/__init__.py`.

- [ ] **Step 1: Update** `app/git_provider/__init__.py` to:

```python
"""Git provider abstraction layer."""
from app.git_provider.base import GitProvider
from app.git_provider.github_provider import GitHubProvider

__all__ = ["GitProvider", "GitHubProvider"]
```

- [ ] **Step 2: Verify import:**

```bash
python -c "from app.git_provider import GitHubProvider, GitProvider; print(GitHubProvider.__mro__)"
```

Expected: `(<class 'app.git_provider.github_provider.GitHubProvider'>, <class 'app.git_provider.base.GitProvider'>, <class 'abc.ABC'>, <class 'object'>)`.

- [ ] **Step 3: Run full app suite:**

```bash
python -m pytest app/git_provider/ -v
```

Expected: ≥21 tests pass (7 from APP-03 base + ≥14 new).

- [ ] **Step 4: Commit:**

```bash
git add app/git_provider/__init__.py
git commit -m "feat(APP-04): re-export GitHubProvider from app/git_provider/"
```

---

## Smoke test (informational — runs after all tasks; not a commit)

If `~/.config/policycodex/config.env` is present and valid, run an end-to-end smoke against `pt-policy`:

```bash
python - <<'PY'
from pathlib import Path
import tempfile, datetime
from app.git_provider import GitHubProvider

p = GitHubProvider()  # loads config from default path
with tempfile.TemporaryDirectory() as td:
    wd = Path(td) / "pt-policy"
    p.clone("https://github.com/Diocese-of-Pensacola-Tallahassee/pt-policy.git", wd)
    stamp = datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    branch_name = f"policycodex/smoke-{stamp}"
    p.branch(branch_name, wd)
    smoke_file = wd / "policies" / "SMOKE.md"
    smoke_file.parent.mkdir(parents=True, exist_ok=True)
    smoke_file.write_text(f"PolicyCodex APP-04 smoke test {stamp}\n")
    sha = p.commit("APP-04 smoke", [smoke_file.relative_to(wd)], "PolicyCodex Smoke", "smoke@policycodex.local", wd)
    print("commit", sha)
    p.push(branch_name, wd)
    pr = p.open_pr(f"Smoke {stamp}", "APP-04 end-to-end smoke", branch_name, "main", wd)
    print("PR", pr)
    print("state", p.read_pr_state(pr["pr_number"], wd))
PY
```

Capture the output in your final report. **The smoke does NOT gate merge.** If credentials are missing or the PT repo is unreachable, report "smoke deferred" and explain why; Chuck will run it manually post-merge.

The smoke PR can be closed afterward — it's intentionally a stub and should not be merged.

---

## Definition of Done (paste output in report)

1. `python -m pytest app/git_provider/ -v` — all pass (≥21 tests).
2. `python -c "from app.git_provider import GitHubProvider, GitProvider; print(GitHubProvider.__mro__)"` — MRO printed.
3. `grep -c "PyGithub" app/requirements.txt` — returns 1.
4. No changes outside `app/git_provider/` and `app/requirements.txt`.
5. Smoke output if credentials present; "smoke deferred (<reason>)" otherwise.

## Report format

```
STATUS: DONE | DONE_WITH_CONCERNS | NEEDS_CONTEXT | BLOCKED

Worktree: <path>
Branch: <name>

Commits (oldest to newest):
- <sha> <subject>
- ...

Verification:
$ python -m pytest app/git_provider/ -v
<paste>

$ python -c "from app.git_provider import GitHubProvider, GitProvider; print(GitHubProvider.__mro__)"
<paste>

$ python -c "import app.git_provider.github_config as c; print(c.load_github_config()  if you can; else 'skipped: no config' )"
<paste or 'skipped'>

Smoke output (or 'deferred: <reason>'):
<paste>

Files changed:
- <path>
- ...

Concerns / open questions:
- ...
```

If you hit BLOCKED or NEEDS_CONTEXT before completing, stop and report immediately. Do not modify files outside the File Structure list.
