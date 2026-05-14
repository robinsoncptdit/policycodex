# APP-05 Local Working Copy Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A `WorkingCopyManager` + a Django management command `pull_working_copy` that clone the diocese's policy repo on first run and pull it on subsequent runs, giving the app a consistent local read-side that unblocks APP-06 (catalog view), APP-21 (startup self-check), and INGEST-07 (bundle reader).

**Architecture:** Single new package `app/working_copy/` with two modules: `config.py` (dataclass loaded from Django settings) and `manager.py` (`WorkingCopyManager` class that orchestrates `GitHubProvider.clone` + a new `GitHubProvider.pull`). The cadence trigger is a Django management command driven by cron — simplest option, no extra deps, the cron interval is operations rather than code, the command is also the first-run installer (idempotent) and a callable surface for APP-21's startup self-check. Rejected: in-process background thread (breaks under autoreload and multi-worker WSGI), `apscheduler` (overbuilt for v0.1). No file-locking module in v0.1: pulls are short, reads tolerate a clear error from INGEST-07 if they catch a mid-pull state, and the next request succeeds. Locks can be added in v0.2 if a real diocese sees thrash.

**Tech Stack:** Python 3.12, Django 5+, `subprocess` (reuses GitHubProvider's tokenized-URL clone/push pattern for the new `pull` method), pytest with `pytest-django`. No new pip deps.

**Ticket reference:** `PolicyWonk-v0.1-Tickets.md` APP-05. Depends on APP-04 (`GitHubProvider`, done). Unblocks APP-06, APP-21, INGEST-07.

**BASE:** `main` at SHA `d9da925`.

---

## File Structure

- Create: `app/working_copy/__init__.py` — empty.
- Create: `app/working_copy/config.py` — `WorkingCopyConfig` dataclass + `load_working_copy_config()` factory.
- Create: `app/working_copy/manager.py` — `WorkingCopyManager` class.
- Create: `app/working_copy/tests/__init__.py` — empty.
- Create: `app/working_copy/tests/test_config.py` — settings-loading tests.
- Create: `app/working_copy/tests/test_manager.py` — clone-on-first-run + pull-on-existing tests, subprocess mocked.
- Create: `core/management/__init__.py` — empty (if not present).
- Create: `core/management/commands/__init__.py` — empty.
- Create: `core/management/commands/pull_working_copy.py` — Django management command.
- Create: `core/tests/test_pull_working_copy_command.py` — `call_command` test.
- Modify: `app/git_provider/base.py` — add abstract `pull(branch, working_dir)`.
- Modify: `app/git_provider/github_provider.py` — implement `pull(branch, working_dir)` using the same tokenized-URL subprocess pattern as `push`.
- Modify: `app/git_provider/tests/test_base.py` — extend the ABC-instantiation test/parametrize to include `pull` in any stub.
- Modify: `app/git_provider/tests/test_github_provider.py` — add `pull` happy-path + error tests (mock `subprocess.run`).
- Modify: `policycodex_site/settings.py` — three new env-driven settings: `POLICYCODEX_POLICY_REPO_URL`, `POLICYCODEX_POLICY_BRANCH` (default `main`), `POLICYCODEX_WORKING_COPY_ROOT` (default `~/.policycodex/working-copies`).
- Modify (conditional): `.gitignore` — add `.policycodex/` if the implementer chose to test against the default root.

No other files touched.

---

## Why `pull` lands in the same task as the ABC extension

Adding an `@abstractmethod` to `GitProvider` makes `GitHubProvider` instantiation fail until `pull` is also implemented on the concrete class. Splitting these across two commits leaves the test suite red between them. The plan deliberately collapses both edits + their tests into Task 2 to avoid an intentionally-broken commit on `main` (cleaner bisect, no review confusion).

---

## Task 1: Worktree setup + pre-flight

**Files:**
- None modified.

- [ ] **Step 1: Confirm BASE**

```bash
git rev-parse HEAD
```

Expected: `d9da925` or descendant.

- [ ] **Step 2: Confirm test suite green from BASE**

```bash
cd /Users/chuck/PolicyWonk && python -m pytest -v
```

Expected: 116 passing. Capture exact count.

- [ ] **Step 3: Confirm `git --version` works in the worktree subprocess context**

```bash
git --version
```

Expected: something like `git version 2.x` printed. APP-05's subprocess shells will need this.

- [ ] **Step 4: No commit yet.**

---

## Task 2: Extend `GitProvider` ABC with `pull` and implement on `GitHubProvider` (TDD)

**Files:**
- Modify: `app/git_provider/base.py`
- Modify: `app/git_provider/github_provider.py`
- Modify: `app/git_provider/tests/test_base.py`
- Modify: `app/git_provider/tests/test_github_provider.py`

- [ ] **Step 1: Read the existing GitHubProvider patterns**

Read `app/git_provider/github_provider.py` for the patterns used by `clone()` (token-rewrite + subprocess + token-redaction on error) and `push()` (read `origin` URL, tokenize for the operation only). `pull` should use the SAME pattern as `push`: fetch a fresh token, tokenize the origin URL just for the operation, redact on error.

- [ ] **Step 2: Read the test parametrization for the ABC**

Read `app/git_provider/tests/test_base.py`. If there is a parametrized test that asserts every abstract method is in the ABC's `__abstractmethods__`, add `pull` to its list. Run it to confirm it FAILS before edits.

```bash
python -m pytest app/git_provider/tests/test_base.py -v
```

Expected: at minimum, no false positives. Capture the test layout for Step 5.

- [ ] **Step 3: Write the failing tests on `GitHubProvider.pull`**

Add to `app/git_provider/tests/test_github_provider.py`:

```python
def test_pull_runs_git_pull_with_tokenized_origin(github_provider, mock_subprocess_run):
    """pull() does: git remote get-url origin -> tokenize -> git pull <tokenized> <branch>."""
    mock_subprocess_run.side_effect = [
        _subprocess_result(stdout=b"https://github.com/Diocese-of-Pensacola-Tallahassee/pt-policy.git\n"),
        _subprocess_result(),
    ]
    github_provider.pull("main", Path("/tmp/wc"))

    assert mock_subprocess_run.call_count == 2
    first_call = mock_subprocess_run.call_args_list[0]
    assert first_call.args[0] == ["git", "remote", "get-url", "origin"]
    second_call = mock_subprocess_run.call_args_list[1]
    cmd = second_call.args[0]
    assert cmd[0:2] == ["git", "pull"]
    # Tokenized URL must appear, original must not be plain
    assert any("x-access-token:" in part for part in cmd)
    assert cmd[-1] == "main"


def test_pull_raises_on_non_github_origin(github_provider, mock_subprocess_run):
    mock_subprocess_run.return_value = _subprocess_result(stdout=b"git@github.com:org/repo.git\n")
    with pytest.raises(ValueError, match="https://github.com/"):
        github_provider.pull("main", Path("/tmp/wc"))


def test_pull_redacts_token_in_error(github_provider, mock_subprocess_run, monkeypatch):
    mock_subprocess_run.side_effect = [
        _subprocess_result(stdout=b"https://github.com/x/y.git\n"),
        _subprocess_result(returncode=1, stderr=b"fatal: could not read from remote (token=AAAA)"),
    ]
    # Force installation_token to be a known string for substring assertion
    monkeypatch.setattr(github_provider, "_installation_token", lambda: "AAAA")
    with pytest.raises(RuntimeError) as excinfo:
        github_provider.pull("main", Path("/tmp/wc"))
    assert "AAAA" not in str(excinfo.value)
    assert "<redacted>" in str(excinfo.value)
```

If `github_provider`, `mock_subprocess_run`, and `_subprocess_result` are not existing fixtures, copy the pattern from neighboring `push` tests verbatim.

- [ ] **Step 4: Run to confirm failures**

```bash
python -m pytest app/git_provider/tests/test_github_provider.py -v -k pull
```

Expected: all three new tests FAIL with `AttributeError` (no `pull` method).

- [ ] **Step 5: Implement `pull` on the ABC and concrete class**

In `app/git_provider/base.py`, add to `GitProvider`:

```python
    @abstractmethod
    def pull(self, branch: str, working_dir: Path) -> None:
        """Pull the latest commits for the given branch into the working directory.

        Args:
            branch: Name of the branch to pull (typically the default branch).
            working_dir: Path to the cloned repository working directory.
        """
        pass
```

In `app/git_provider/github_provider.py`, add the method (place it after `push`):

```python
    def pull(self, branch: str, working_dir: Path) -> None:
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
            ["git", "pull", tokenized, branch],
            cwd=working_dir,
            capture_output=True,
        )
        if result.returncode != 0:
            stderr = result.stderr.decode(errors="replace").replace(token, "<redacted>")
            raise RuntimeError(
                f"git pull failed (exit {result.returncode}): {stderr}"
            )
```

In `app/git_provider/tests/test_base.py`, extend whichever parametrize / assertion enumerates the abstract methods so `pull` is included. (Concrete change depends on the existing test shape; consult it. If the test asserts that `GitProvider.__abstractmethods__` matches a set, add `"pull"` to the expected set.)

- [ ] **Step 6: Run all tests**

```bash
cd /Users/chuck/PolicyWonk && python -m pytest -v
```

Expected: full suite green; 3 new tests pass; no regressions. Capture green count.

- [ ] **Step 7: Commit**

```bash
git add app/git_provider/base.py app/git_provider/github_provider.py app/git_provider/tests/test_base.py app/git_provider/tests/test_github_provider.py
git commit -m "feat(APP-05): add pull() to GitProvider ABC + GitHubProvider"
```

---

## Task 3: `WorkingCopyConfig` + Django settings wiring (TDD)

**Files:**
- Create: `app/working_copy/__init__.py`
- Create: `app/working_copy/config.py`
- Create: `app/working_copy/tests/__init__.py`
- Create: `app/working_copy/tests/test_config.py`
- Modify: `policycodex_site/settings.py`

- [ ] **Step 1: Write the failing test**

Create `app/working_copy/tests/test_config.py`:

```python
"""Tests for WorkingCopyConfig."""
from pathlib import Path

import pytest
from django.test import override_settings

from app.working_copy.config import WorkingCopyConfig, load_working_copy_config


def test_load_from_django_settings_uses_three_settings(tmp_path):
    with override_settings(
        POLICYCODEX_POLICY_REPO_URL="https://github.com/example/policy.git",
        POLICYCODEX_POLICY_BRANCH="main",
        POLICYCODEX_WORKING_COPY_ROOT=str(tmp_path / "wc-root"),
    ):
        cfg = load_working_copy_config()

    assert isinstance(cfg, WorkingCopyConfig)
    assert cfg.repo_url == "https://github.com/example/policy.git"
    assert cfg.branch == "main"
    assert cfg.root == tmp_path / "wc-root"


def test_load_raises_when_repo_url_unset():
    with override_settings(
        POLICYCODEX_POLICY_REPO_URL="",
        POLICYCODEX_POLICY_BRANCH="main",
        POLICYCODEX_WORKING_COPY_ROOT="/tmp/wc",
    ):
        with pytest.raises(RuntimeError, match="POLICYCODEX_POLICY_REPO_URL"):
            load_working_copy_config()


def test_working_dir_property_is_root_plus_slug(tmp_path):
    cfg = WorkingCopyConfig(
        repo_url="https://github.com/example/policy.git",
        branch="main",
        root=tmp_path,
    )
    assert cfg.working_dir == tmp_path / "policy"


def test_working_dir_handles_dot_git_suffix(tmp_path):
    cfg = WorkingCopyConfig(
        repo_url="https://github.com/example/policy.git",
        branch="main",
        root=tmp_path,
    )
    assert cfg.working_dir.name == "policy"


def test_working_dir_without_dot_git_suffix(tmp_path):
    cfg = WorkingCopyConfig(
        repo_url="https://github.com/example/policy",
        branch="main",
        root=tmp_path,
    )
    assert cfg.working_dir == tmp_path / "policy"
```

- [ ] **Step 2: Run to confirm failure**

```bash
python -m pytest app/working_copy/tests/test_config.py -v
```

Expected: ImportError.

- [ ] **Step 3: Create the module**

Create `app/working_copy/__init__.py` (empty) and `app/working_copy/tests/__init__.py` (empty).

Create `app/working_copy/config.py`:

```python
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
        # Derive a stable directory name from the repo URL (strip trailing slashes and .git)
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
```

- [ ] **Step 4: Wire the settings**

In `policycodex_site/settings.py`, add (place near other env-driven settings):

```python
POLICYCODEX_POLICY_REPO_URL = os.environ.get("POLICYCODEX_POLICY_REPO_URL", "")
POLICYCODEX_POLICY_BRANCH = os.environ.get("POLICYCODEX_POLICY_BRANCH", "main")
POLICYCODEX_WORKING_COPY_ROOT = os.environ.get(
    "POLICYCODEX_WORKING_COPY_ROOT", ""
)
```

If `import os` is not already at the top of the settings file, add it.

- [ ] **Step 5: Run to confirm pass**

```bash
python -m pytest app/working_copy/tests/test_config.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add app/working_copy/__init__.py app/working_copy/config.py app/working_copy/tests/__init__.py app/working_copy/tests/test_config.py policycodex_site/settings.py
git commit -m "feat(APP-05): WorkingCopyConfig dataclass + settings wiring"
```

---

## Task 4: `WorkingCopyManager` clone-on-first-run, pull-on-existing (TDD)

**Files:**
- Create: `app/working_copy/manager.py`
- Create: `app/working_copy/tests/test_manager.py`

- [ ] **Step 1: Write the failing tests**

Create `app/working_copy/tests/test_manager.py`:

```python
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
    (cfg.working_dir / ".git").mkdir()  # marker
    provider = MagicMock()
    manager = WorkingCopyManager(cfg, provider)

    result = manager.sync()

    provider.clone.assert_not_called()
    provider.pull.assert_called_once_with(cfg.branch, cfg.working_dir)
    assert result == cfg.working_dir


def test_sync_pulls_when_working_dir_exists_but_no_dot_git_raises(tmp_path):
    """Defensive: if the dir is there but is not a git repo, fail loud (don't clobber)."""
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
```

- [ ] **Step 2: Run to confirm failures**

```bash
python -m pytest app/working_copy/tests/test_manager.py -v
```

Expected: ImportError.

- [ ] **Step 3: Create the manager**

Create `app/working_copy/manager.py`:

```python
"""Orchestrate clone-on-first-run + pull-on-existing for the policy working copy."""
from __future__ import annotations

from pathlib import Path

from app.git_provider.base import GitProvider
from app.working_copy.config import WorkingCopyConfig


class WorkingCopyManager:
    """Maintains a local clone of the diocese's policy repo.

    Idempotent: calling `sync()` clones on first invocation and pulls on
    subsequent invocations. Safe to invoke from a cron-driven management
    command or from the app's startup self-check.
    """

    def __init__(self, config: WorkingCopyConfig, provider: GitProvider) -> None:
        self._config = config
        self._provider = provider

    def sync(self) -> Path:
        wd = self._config.working_dir
        if wd.exists():
            # Defensive: refuse to clobber a non-git directory at the target path.
            if not (wd / ".git").exists():
                raise RuntimeError(
                    f"working copy path exists but is not a git repository: {wd}. "
                    f"Refusing to clone over existing content. Move or delete the directory "
                    f"and re-run."
                )
            self._provider.pull(self._config.branch, wd)
            return wd

        # First-run clone path. Ensure the root exists (provider.clone wants the parent).
        wd.parent.mkdir(parents=True, exist_ok=True)
        self._provider.clone(self._config.repo_url, wd)
        return wd
```

- [ ] **Step 4: Run to confirm pass**

```bash
python -m pytest app/working_copy/tests/test_manager.py -v
```

Expected: all 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add app/working_copy/manager.py app/working_copy/tests/test_manager.py
git commit -m "feat(APP-05): WorkingCopyManager orchestrates clone-on-first-run + pull"
```

---

## Task 5: Django management command `pull_working_copy` (TDD)

**Files:**
- Create: `core/management/__init__.py` (empty, if not present)
- Create: `core/management/commands/__init__.py` (empty)
- Create: `core/management/commands/pull_working_copy.py`
- Create: `core/tests/test_pull_working_copy_command.py`

- [ ] **Step 1: Write the failing test**

Create `core/tests/test_pull_working_copy_command.py`:

```python
"""Tests for the pull_working_copy management command."""
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.test import override_settings


@pytest.fixture
def settings_for_command(tmp_path):
    with override_settings(
        POLICYCODEX_POLICY_REPO_URL="https://github.com/example/policy.git",
        POLICYCODEX_POLICY_BRANCH="main",
        POLICYCODEX_WORKING_COPY_ROOT=str(tmp_path),
    ):
        yield tmp_path


def test_command_invokes_manager_sync(settings_for_command):
    out = StringIO()
    with patch("core.management.commands.pull_working_copy.WorkingCopyManager") as MgrCls:
        instance = MgrCls.return_value
        instance.sync.return_value = settings_for_command / "policy"

        call_command("pull_working_copy", stdout=out)

    MgrCls.assert_called_once()
    instance.sync.assert_called_once_with()
    assert "policy" in out.getvalue()


def test_command_raises_with_clear_message_when_repo_url_missing():
    out = StringIO()
    with override_settings(
        POLICYCODEX_POLICY_REPO_URL="",
        POLICYCODEX_POLICY_BRANCH="main",
        POLICYCODEX_WORKING_COPY_ROOT="/tmp/wc",
    ):
        with pytest.raises(RuntimeError, match="POLICYCODEX_POLICY_REPO_URL"):
            call_command("pull_working_copy", stdout=out)


def test_command_propagates_sync_error(settings_for_command):
    out = StringIO()
    err = StringIO()
    with patch("core.management.commands.pull_working_copy.WorkingCopyManager") as MgrCls:
        MgrCls.return_value.sync.side_effect = RuntimeError("git pull failed (exit 1): nope")
        with pytest.raises(RuntimeError, match="git pull failed"):
            call_command("pull_working_copy", stdout=out, stderr=err)
```

- [ ] **Step 2: Run to confirm failure**

```bash
python -m pytest core/tests/test_pull_working_copy_command.py -v
```

Expected: `CommandError: Unknown command: 'pull_working_copy'`.

- [ ] **Step 3: Create the management command**

Create `core/management/__init__.py` (empty) if it doesn't already exist. Create `core/management/commands/__init__.py` (empty).

Create `core/management/commands/pull_working_copy.py`:

```python
"""Sync the local working copy of the diocese's policy repo.

Run on cadence via cron (~5 minute interval) to keep the app's read-side
consistent with the diocese's GitHub repo. Idempotent: clones on first
run, pulls on subsequent runs. Safe to invoke from APP-21's startup self-
check.
"""
from django.core.management.base import BaseCommand

from app.git_provider.github_provider import GitHubProvider
from app.working_copy.config import load_working_copy_config
from app.working_copy.manager import WorkingCopyManager


class Command(BaseCommand):
    help = "Clone (first run) or pull (subsequent runs) the diocese's policy repo."

    def handle(self, *args, **options):
        config = load_working_copy_config()
        provider = GitHubProvider()
        manager = WorkingCopyManager(config, provider)
        working_dir = manager.sync()
        self.stdout.write(self.style.SUCCESS(f"working copy synced at {working_dir}"))
```

- [ ] **Step 4: Run to confirm pass**

```bash
python -m pytest core/tests/test_pull_working_copy_command.py -v
```

Expected: all 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add core/management/__init__.py core/management/commands/__init__.py core/management/commands/pull_working_copy.py core/tests/test_pull_working_copy_command.py
git commit -m "feat(APP-05): pull_working_copy management command"
```

---

## Task 6: Full-suite verification + cadence docs note + handoff

**Files:**
- Modify (optional): `.gitignore` — add `.policycodex/` if the implementer used that path during local manual smoke.

- [ ] **Step 1: Full suite green**

```bash
cd /Users/chuck/PolicyWonk && python -m pytest -v
```

Expected: 116 baseline + 14 new tests = 130 passing (5 config + 6 manager + 3 command). If the count differs, surface in the self-report.

- [ ] **Step 2: Smoke check (optional, requires GitHub App creds)**

If `~/.config/policycodex/config.env` is populated AND the implementer has explicit Chuck-authorization to run live GitHub calls, do a one-time manual smoke:

```bash
export POLICYCODEX_POLICY_REPO_URL=https://github.com/Diocese-of-Pensacola-Tallahassee/pt-policy.git
export POLICYCODEX_POLICY_BRANCH=main
export POLICYCODEX_WORKING_COPY_ROOT=/tmp/app05-smoke
python manage.py pull_working_copy
ls /tmp/app05-smoke/pt-policy/policies/document-retention/
rm -rf /tmp/app05-smoke  # cleanup (this is /tmp; safe)
```

Expected (first run): clone succeeds; `policies/document-retention/{policy.md, data.yaml, source.pdf}` are present.

If the implementer does NOT have authorization or creds aren't local, skip this step and note it in the self-report. Unit tests are authoritative.

- [ ] **Step 3: Cadence trigger note in self-report**

The plan deliberately scoped out the actual cron entry — operating concern, not code. Note in the self-report:

> The cron entry to drive this command is operations-side. Suggested form for the diocese's deployment:
> ```
> */5 * * * * cd /opt/policycodex && /opt/policycodex/.venv/bin/python manage.py pull_working_copy >> /var/log/policycodex/working-copy.log 2>&1
> ```
> Final form moves to the deployment ticket (REPO-05 dual-Compose).

- [ ] **Step 4: Compose self-report**

Cover:
- Goal in one sentence.
- Cadence-trigger approach (Django mgmt command + cron) and the rejected alternatives (in-process thread, apscheduler).
- Files created/modified.
- Commit list (`git log --oneline main..HEAD`).
- Test count before / after.
- Anything that surprised the implementer (e.g., the test_base.py parametrize pattern).
- Open follow-ups (e.g., concurrent-access safety to v0.2; production cron config to REPO-05).

- [ ] **Step 5: Handoff to code review**

Do not merge. Hand the branch + self-report back to the dispatching session for `superpowers:requesting-code-review`.

---

## Definition of Done

- `app/git_provider/base.py` declares `pull` as an `@abstractmethod`.
- `app/git_provider/github_provider.py` implements `pull` using the same tokenized-URL subprocess pattern as `push` (no plain-text tokens persisted to disk; tokens redacted from error messages).
- `app/working_copy/` package exists with `config.py` (`WorkingCopyConfig` + `load_working_copy_config`) and `manager.py` (`WorkingCopyManager.sync()`).
- `core/management/commands/pull_working_copy.py` exists and is invokable via `python manage.py pull_working_copy`.
- `policycodex_site/settings.py` reads three new env vars: `POLICYCODEX_POLICY_REPO_URL`, `POLICYCODEX_POLICY_BRANCH`, `POLICYCODEX_WORKING_COPY_ROOT`. None have a PT-specific default; the diocese's wizard (APP-08..16) will populate them per-install.
- Full repo test suite passes; ~14 new tests added on top of the 116 baseline.
- No edits outside the files listed in **File Structure**.
- No em dashes anywhere in new content.
- No PT-specific tokens (`pt-policy`, `Pensacola-Tallahassee`, hardcoded org name) in `app/working_copy/` or `core/management/commands/` code. PT appears only in test/smoke env exports and docstrings about install zero.
- Five commits since BASE `d9da925` (1 per task that produces a commit; tasks 1 + 6 produce none).
- Self-report calls out test count before/after and the cadence-trigger decision with the rejected alternatives.
