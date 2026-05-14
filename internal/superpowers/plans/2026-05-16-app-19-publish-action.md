# APP-19 Publish Action Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A "Publish" button on every Reviewed-state policy in the catalog that POSTs to `/policies/<slug>/publish/`, gates on the PR being in `reviewed` state, and merges the PR via a new `GitHubProvider.merge_pr(...)` method that wraps PyGithub's `PullRequest.merge(merge_method="squash")`.

**Architecture:** Add one new abstract method `merge_pr` to `GitProvider` and implement it in `GitHubProvider`, mirroring `open_pr` / `read_pr_state` (origin URL → owner/repo → `repo.get_pull(pr_number).merge(...)`). A new function-based view `core.views.publish_policy` looks up the policy's PR number from the per-policy `.policymeta.yaml` sidecar (written by APP-07's edit flow), pre-checks `read_pr_state` and refuses anything other than `"reviewed"`, then calls `merge_pr`. The catalog template grows a per-row publish button rendered only when the row's gate state is `"reviewed"` (gate state comes from APP-17's context-builder; this plan stubs the per-row state shape so APP-19 is independently testable). All non-happy paths surface as Django messages framework flash messages and redirect back to `/catalog/`.

**Tech Stack:** Django 5+ function-based views, Django messages framework, PyGithub 2.x, pytest-django, `unittest.mock`.

**Ticket reference:** `PolicyWonk-v0.1-Tickets.md` APP-19 (line 101): "Publish action in UI merges PR (requires merge permission)." Gate model from `CLAUDE.md`: "Published = merged."

**BASE:** `main` at SHA `5017488` (post-Wave-2 close, post-APP-06 + APP-21 merges; on-disk baseline is 180 passing tests).

**Discipline reminders:**
- TDD: every test in this plan must be observed-failing first, then passing. Don't skip RED.
- No em dashes anywhere in new content (code, docstrings, comments, commit messages).
- Ship-generic: no `pt`, `PT`, `pensacola`, `tallahassee` tokens anywhere in `app/git_provider/`, `core/views.py`, `core/templates/catalog.html`, or the test files. Tests use synthetic slugs and `https://github.com/foo/bar.git` style origins.
- Tests use `pytest-django`'s `client` fixture and the `force_login` pattern from `core/tests/test_auth.py`.
- The GitHub App's `Contents: Read and write` + `Pull requests: Read and write` permissions (verified in `internal/REPO-03-GitHub-App-Checklist.md` lines 33-34) are sufficient for merge. No new App permissions are required.

**Parallel-dispatch concern with APP-18:** APP-18 (Approve action) is dispatched in the same wave and adds a different abstract method (`approve_pr`) to `GitProvider`. Whichever of APP-18 and APP-19 merges to `main` second will hit a deterministic conflict in `app/git_provider/tests/test_base.py` (each plan adds a `test_subclass_missing_<method>_fails` test class AND adds a stub of its own method to every OTHER missing-method test class). The conflict is mechanical: the second branch resolves by (a) keeping both new test classes and (b) adding the first-merged method to its own new test class's incomplete-provider AND adding its own method to the first-merged branch's new test class's incomplete-provider. The reviewer for the second-merged ticket should call out the conflict resolution explicitly. APP-19 cannot, on its own, avoid this; it just has to be aware.

---

## File Structure

- Modify: `app/git_provider/base.py` — add `merge_pr` as an `@abstractmethod`.
- Modify: `app/git_provider/github_provider.py` — implement `merge_pr` using `Repository.get_pull(pr_number).merge(merge_method="squash", commit_title=..., commit_message=...)`. Raises `RuntimeError` on `GithubException` (merge conflict, branch protection block, rate-limit, anything else from the API).
- Modify: `app/git_provider/tests/test_base.py` — add `test_subclass_missing_merge_pr_fails` class; add `merge_pr` stub to every OTHER missing-method test class so they still construct.
- Modify: `app/git_provider/tests/test_github_provider.py` — add `test_merge_pr_*` tests for happy-path (squash), squash-method-default, conflict-raises-RuntimeError, branch-protection-block-raises, and the origin-URL parsing path.
- Modify: `core/views.py` — add `publish_policy(request, slug)` view (POST only, `@login_required`, `@require_http_methods(["POST"])`).
- Modify: `core/urls.py` — add `path("policies/<slug>/publish/", views.publish_policy, name="publish_policy")`.
- Modify: `core/templates/catalog.html` — render a per-row Publish button when `policy.gate_state == "reviewed"`. Button is a `<form method="post">` with CSRF token (no JavaScript).
- Create: `core/policymeta.py` — helper `read_pr_number_for(working_dir: Path, slug: str) -> int` that reads `<working_dir>/policies/<slug>.policymeta.yaml` (or the bundle variant `<working_dir>/policies/<slug>/.policymeta.yaml`) and returns the `pr_number` field. Returns `None` if the sidecar is absent. The sidecar format is the same shape APP-07's edit flow writes after `open_pr`.
- Create: `core/tests/test_publish_policy.py` — pytest tests for the view (login required, POST-only, gate guard, happy path, missing-PR-sidecar, merge-conflict surfaced as flash, non-reviewed-state-refused).
- Create: `core/tests/test_policymeta.py` — pytest tests for the sidecar reader (flat sidecar found, bundle sidecar found, missing sidecar returns None, malformed YAML raises).

No other files touched. `app/git_provider/github_config.py`, `app/working_copy/`, `ingest/`, `policycodex_site/settings.py` — all read-only for this ticket.

---

## Task 1: Worktree pre-flight

**Files:**
- None modified.

- [ ] **Step 1: Confirm worktree state**

```bash
git rev-parse HEAD
git branch --show-current
git status --short
```

Expected: BASE SHA `5017488` or a descendant; branch is the auto-worktree branch the harness gave you (`worktree-agent-<id>`); status is clean.

If anything is unexpected, STOP and report.

- [ ] **Step 2: Merge `main` into your worktree branch**

```bash
git fetch
git merge main --no-edit
```

Expected: "Already up to date." or fast-forward to `5017488` (or descendant).

If APP-18 has already merged to `main` before you started, the merge brings in APP-18's `approve_pr` abstract method and updates to `test_base.py`. That is fine; the plan accounts for that scenario in the parallel-dispatch note above.

- [ ] **Step 3: Confirm baseline test suite green**

```bash
/Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest -q 2>&1 | tail -3
```

Expected: `180 passed` (baseline). If APP-18 merged ahead of APP-19, expect a higher number; capture exactly what you see and use that as your delta-from baseline in the final report.

- [ ] **Step 4: Read the existing patterns this ticket follows**

Read each of these files briefly to confirm signatures:

- `/Users/chuck/PolicyWonk/app/git_provider/base.py` (the abstract method pattern, especially the docstring shape for `open_pr` and `read_pr_state`)
- `/Users/chuck/PolicyWonk/app/git_provider/github_provider.py:208-256` (`open_pr` and `read_pr_state` — `merge_pr` mirrors their origin-URL-then-PyGithub pattern)
- `/Users/chuck/PolicyWonk/app/git_provider/tests/test_github_provider.py:188-249` (`test_open_pr_uses_repo_from_origin_and_returns_metadata` and `test_read_pr_state_mapping` — the canonical PyGithub-mocking patterns for this codebase)
- `/Users/chuck/PolicyWonk/app/git_provider/tests/test_base.py` (the parametrized "missing method" pattern; `merge_pr` follows the same shape as `test_subclass_missing_pull_fails`)
- `/Users/chuck/PolicyWonk/core/views.py` (the function-based view + `@login_required` pattern; APP-06's `catalog` view is the closest existing reference)
- `/Users/chuck/PolicyWonk/core/urls.py` (URL routing style)
- `/Users/chuck/PolicyWonk/core/templates/catalog.html` (where the Publish button slots in; the existing `<li class="policy">` block is the insertion site)

- [ ] **Step 5: No commit yet.**

---

## Task 2: Add `merge_pr` to `GitProvider` ABC (TDD)

**Files:**
- Modify: `app/git_provider/base.py`
- Modify: `app/git_provider/tests/test_base.py`

- [ ] **Step 1: Write the failing test**

Append to `app/git_provider/tests/test_base.py` (inside the existing `TestGitProviderSubclassMissingMethods` class, alongside the existing tests):

```python
    def test_subclass_missing_merge_pr_fails(self):
        """Subclass missing merge_pr() cannot instantiate."""
        class IncompleteProvider(GitProvider):
            def clone(self, repo_url: str, dest: Path) -> None:
                pass
            def branch(self, name: str, working_dir: Path) -> None:
                pass
            def commit(self, message: str, files: list[Path], author_name: str, author_email: str, working_dir: Path) -> str:
                pass
            def push(self, branch: str, working_dir: Path) -> None:
                pass
            def pull(self, branch: str, working_dir: Path) -> None:
                pass
            def open_pr(self, title: str, body: str, head_branch: str, base_branch: str, working_dir: Path) -> dict:
                pass
            def read_pr_state(self, pr_number: int, working_dir: Path) -> str:
                pass

        with pytest.raises(TypeError):
            IncompleteProvider()
```

Also update every OTHER `test_subclass_missing_*_fails` method in the same class so each `IncompleteProvider` now ALSO defines `merge_pr`. Add this stub method to every other test class's `IncompleteProvider` body (alphabetical placement is fine; the existing tests do not enforce a specific order):

```python
            def merge_pr(self, pr_number: int, working_dir: Path, merge_method: str = "squash") -> dict:
                pass
```

Specifically: the 7 existing methods are `test_subclass_missing_clone_fails`, `test_subclass_missing_branch_fails`, `test_subclass_missing_commit_fails`, `test_subclass_missing_push_fails`, `test_subclass_missing_pull_fails`, `test_subclass_missing_open_pr_fails`, `test_subclass_missing_read_pr_state_fails`. Each one defines an `IncompleteProvider` that implements every method EXCEPT the one under test. After this edit, each of those 7 also implements `merge_pr` (so they continue to fail-to-instantiate ONLY because of the method named in the test, not also because of the new `merge_pr`).

The new `test_subclass_missing_merge_pr_fails` is the 8th and implements every method EXCEPT `merge_pr`.

- [ ] **Step 2: Run to confirm failure**

```bash
cd /Users/chuck/PolicyWonk && /Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest app/git_provider/tests/test_base.py -v 2>&1 | tail -15
```

Expected: `test_subclass_missing_merge_pr_fails` FAILS with the IncompleteProvider instantiating successfully (i.e., `pytest.raises(TypeError)` did not catch anything) because the ABC does not yet declare `merge_pr` as abstract.

All 7 existing tests should still pass (they now declare `merge_pr` in their stubs, which is harmless since the ABC does not yet require it).

- [ ] **Step 3: Add `merge_pr` to the ABC**

Open `app/git_provider/base.py`. After the existing `read_pr_state` method (at the end of the class), add:

```python
    @abstractmethod
    def merge_pr(
        self,
        pr_number: int,
        working_dir: Path,
        merge_method: str = "squash",
    ) -> dict:
        """Merge a pull request, transitioning Reviewed to Published.

        v0.1 default is squash so each merged policy edit lands as one
        clean commit on main. Callers may override per provider quirks.

        Args:
            pr_number: The pull request number.
            working_dir: Path to the repository working directory (used to
                resolve the origin URL and therefore the owner/repo).
            merge_method: One of "merge", "squash", or "rebase". Defaults
                to "squash" for v0.1.

        Returns:
            Dictionary containing merge metadata: {"merged": bool,
            "sha": str, "merge_method": str}. The sha is the new commit
            SHA on the base branch.

        Raises:
            RuntimeError: If the merge fails for any reason (conflict,
                branch protection blocked, rate-limit, API error, the PR
                is already merged, etc.). The exception message includes
                the underlying cause.
        """
        pass
```

- [ ] **Step 4: Run to confirm pass**

```bash
/Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest app/git_provider/tests/test_base.py -v 2>&1 | tail -15
```

Expected: 9 passing (1 abstract-class + 8 missing-method = 9 total). All 8 missing-method tests pass because the ABC now requires `merge_pr` and the test stubs each leave out exactly one method.

- [ ] **Step 5: Run the full repo suite to confirm nothing else broke**

```bash
/Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest -q 2>&1 | tail -3
```

Expected: ALL tests pass EXCEPT the existing `GitHubProvider` tests, which will now fail with a TypeError because `GitHubProvider` does not yet implement `merge_pr`. Specifically, tests like `test_github_provider_is_git_provider`, `test_constructor_loads_config_by_default`, etc. will fail at instantiation.

That is expected. Note the failing count for the next task.

- [ ] **Step 6: Commit**

```bash
git add app/git_provider/base.py app/git_provider/tests/test_base.py
git commit -m "feat(APP-19): add merge_pr abstract method to GitProvider"
```

---

## Task 3: Implement `GitHubProvider.merge_pr` (TDD)

**Files:**
- Modify: `app/git_provider/github_provider.py`
- Modify: `app/git_provider/tests/test_github_provider.py`

- [ ] **Step 1: Write the failing tests**

Append to `app/git_provider/tests/test_github_provider.py`:

```python
def test_merge_pr_calls_pygithub_with_squash_default(tmp_path):
    """merge_pr defaults to merge_method='squash' and returns merge metadata."""
    cfg = _fake_config(tmp_path)
    (tmp_path / "key.pem").write_text("FAKE PEM")
    wd = tmp_path / "wd"
    fake_pr = MagicMock(number=42)
    # PyGithub's pr.merge() returns an object with attrs merged + sha.
    fake_merge_result = MagicMock(merged=True, sha="cafebabe1234")
    fake_pr.merge.return_value = fake_merge_result
    fake_repo = MagicMock()
    fake_repo.get_pull.return_value = fake_pr
    fake_client = MagicMock()
    fake_client.get_repo.return_value = fake_repo
    with patch("app.git_provider.github_provider.subprocess.run") as run:
        run.return_value = MagicMock(returncode=0, stdout=b"https://github.com/foo/bar.git\n")
        p = GitHubProvider(config=cfg, github_client=fake_client)
        result = p.merge_pr(42, wd)
    fake_client.get_repo.assert_called_once_with("foo/bar")
    fake_repo.get_pull.assert_called_once_with(42)
    fake_pr.merge.assert_called_once()
    call_kwargs = fake_pr.merge.call_args.kwargs
    assert call_kwargs["merge_method"] == "squash"
    assert result == {"merged": True, "sha": "cafebabe1234", "merge_method": "squash"}


def test_merge_pr_honors_explicit_merge_method(tmp_path):
    """merge_pr passes through merge_method='merge' or 'rebase' when given."""
    cfg = _fake_config(tmp_path)
    (tmp_path / "key.pem").write_text("FAKE PEM")
    wd = tmp_path / "wd"
    fake_pr = MagicMock()
    fake_pr.merge.return_value = MagicMock(merged=True, sha="abc")
    fake_repo = MagicMock()
    fake_repo.get_pull.return_value = fake_pr
    fake_client = MagicMock()
    fake_client.get_repo.return_value = fake_repo
    with patch("app.git_provider.github_provider.subprocess.run") as run:
        run.return_value = MagicMock(returncode=0, stdout=b"https://github.com/foo/bar.git\n")
        p = GitHubProvider(config=cfg, github_client=fake_client)
        result = p.merge_pr(7, wd, merge_method="rebase")
    assert fake_pr.merge.call_args.kwargs["merge_method"] == "rebase"
    assert result["merge_method"] == "rebase"


def test_merge_pr_rejects_invalid_merge_method(tmp_path):
    """Only merge, squash, rebase are accepted; anything else raises ValueError."""
    cfg = _fake_config(tmp_path)
    (tmp_path / "key.pem").write_text("FAKE PEM")
    p = GitHubProvider(config=cfg, github_client=MagicMock())
    with pytest.raises(ValueError, match="merge_method"):
        p.merge_pr(1, tmp_path / "wd", merge_method="fast-forward")


def test_merge_pr_raises_runtime_error_on_github_exception(tmp_path):
    """A PyGithub GithubException (e.g. 409 merge conflict) becomes RuntimeError."""
    from github import GithubException
    cfg = _fake_config(tmp_path)
    (tmp_path / "key.pem").write_text("FAKE PEM")
    wd = tmp_path / "wd"
    fake_pr = MagicMock()
    fake_pr.merge.side_effect = GithubException(
        status=409, data={"message": "Merge conflict"}, headers=None
    )
    fake_repo = MagicMock()
    fake_repo.get_pull.return_value = fake_pr
    fake_client = MagicMock()
    fake_client.get_repo.return_value = fake_repo
    with patch("app.git_provider.github_provider.subprocess.run") as run:
        run.return_value = MagicMock(returncode=0, stdout=b"https://github.com/foo/bar.git\n")
        p = GitHubProvider(config=cfg, github_client=fake_client)
        with pytest.raises(RuntimeError, match="merge.*409|Merge conflict"):
            p.merge_pr(42, wd)


def test_merge_pr_raises_runtime_error_on_branch_protection_block(tmp_path):
    """Branch protection failures surface 405 with a Method Not Allowed message."""
    from github import GithubException
    cfg = _fake_config(tmp_path)
    (tmp_path / "key.pem").write_text("FAKE PEM")
    wd = tmp_path / "wd"
    fake_pr = MagicMock()
    fake_pr.merge.side_effect = GithubException(
        status=405,
        data={"message": "Required status check has not succeeded"},
        headers=None,
    )
    fake_repo = MagicMock()
    fake_repo.get_pull.return_value = fake_pr
    fake_client = MagicMock()
    fake_client.get_repo.return_value = fake_repo
    with patch("app.git_provider.github_provider.subprocess.run") as run:
        run.return_value = MagicMock(returncode=0, stdout=b"https://github.com/foo/bar.git\n")
        p = GitHubProvider(config=cfg, github_client=fake_client)
        with pytest.raises(RuntimeError, match="405|status check"):
            p.merge_pr(42, wd)


def test_merge_pr_raises_when_pr_already_merged(tmp_path):
    """If pr.merge() returns merged=False, surface a RuntimeError so callers don't
    silently report success. GitHub's API can return merged=False with a reason
    string when, e.g., the head SHA changed between read and merge."""
    cfg = _fake_config(tmp_path)
    (tmp_path / "key.pem").write_text("FAKE PEM")
    wd = tmp_path / "wd"
    fake_pr = MagicMock()
    fake_pr.merge.return_value = MagicMock(merged=False, sha=None)
    fake_repo = MagicMock()
    fake_repo.get_pull.return_value = fake_pr
    fake_client = MagicMock()
    fake_client.get_repo.return_value = fake_repo
    with patch("app.git_provider.github_provider.subprocess.run") as run:
        run.return_value = MagicMock(returncode=0, stdout=b"https://github.com/foo/bar.git\n")
        p = GitHubProvider(config=cfg, github_client=fake_client)
        with pytest.raises(RuntimeError, match="not merged"):
            p.merge_pr(42, wd)
```

- [ ] **Step 2: Run to confirm failure**

```bash
/Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest app/git_provider/tests/test_github_provider.py -v 2>&1 | tail -25
```

Expected: every `test_merge_pr_*` test fails (currently with `TypeError: Can't instantiate abstract class GitHubProvider` since the ABC requires `merge_pr` but the concrete class does not implement it). The pre-existing tests for `clone`, `branch`, `commit`, `push`, `pull`, `open_pr`, `read_pr_state` ALSO fail for the same reason. That is the expected RED state.

- [ ] **Step 3: Implement `merge_pr` in `GitHubProvider`**

Open `app/git_provider/github_provider.py`. Add a module-level constant near the top (just after the existing `_REPO_RE` constant):

```python
_VALID_MERGE_METHODS = ("merge", "squash", "rebase")
```

Then append a new method to the `GitHubProvider` class (after `read_pr_state`):

```python
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
```

- [ ] **Step 4: Run to confirm pass**

```bash
/Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest app/git_provider/tests/test_github_provider.py -v 2>&1 | tail -20
```

Expected: all `test_merge_pr_*` tests pass (6 new); all pre-existing tests also pass again (because the ABC requirement is now satisfied).

- [ ] **Step 5: Full repo test suite**

```bash
/Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest -q 2>&1 | tail -3
```

Expected: `186 passed` (180 baseline + 1 new test in `test_base.py` + 6 new tests in `test_github_provider.py` minus 1 if your baseline already includes APP-18; capture the exact number).

- [ ] **Step 6: Commit**

```bash
git add app/git_provider/github_provider.py app/git_provider/tests/test_github_provider.py
git commit -m "feat(APP-19): GitHubProvider.merge_pr (squash default, error wrapping)"
```

---

## Task 4: Policymeta sidecar reader (TDD)

The view needs to look up "which PR number belongs to this policy slug." APP-07's edit flow (Wave-3, dispatched in parallel) writes a `.policymeta.yaml` sidecar containing at least `pr_number`. APP-19 reads it. We define the minimum reader contract here so APP-19 is testable without depending on APP-07's exact implementation; APP-07's plan should match the same on-disk format.

**Files:**
- Create: `core/policymeta.py`
- Create: `core/tests/test_policymeta.py`

- [ ] **Step 1: Write the failing tests**

Create `core/tests/test_policymeta.py`:

```python
"""Tests for the per-policy .policymeta.yaml sidecar reader."""
from pathlib import Path

import pytest


def test_read_pr_number_for_flat_policy(tmp_path):
    """A flat policy stores its sidecar at policies/<slug>.policymeta.yaml."""
    from core.policymeta import read_pr_number_for
    policies = tmp_path / "policies"
    policies.mkdir()
    (policies / "code-of-conduct.md").write_text("---\ntitle: x\n---\n")
    (policies / "code-of-conduct.policymeta.yaml").write_text("pr_number: 42\n")
    assert read_pr_number_for(tmp_path, "code-of-conduct") == 42


def test_read_pr_number_for_bundle_policy(tmp_path):
    """A bundle policy stores its sidecar at policies/<slug>/.policymeta.yaml."""
    from core.policymeta import read_pr_number_for
    bundle = tmp_path / "policies" / "document-retention"
    bundle.mkdir(parents=True)
    (bundle / "policy.md").write_text("---\nfoundational: true\n---\n")
    (bundle / ".policymeta.yaml").write_text("pr_number: 99\n")
    assert read_pr_number_for(tmp_path, "document-retention") == 99


def test_read_pr_number_returns_none_when_sidecar_absent(tmp_path):
    """No sidecar means the policy has never been edited via the app; return None."""
    from core.policymeta import read_pr_number_for
    (tmp_path / "policies").mkdir()
    assert read_pr_number_for(tmp_path, "never-edited") is None


def test_read_pr_number_returns_none_when_policies_dir_absent(tmp_path):
    """No policies dir means a fresh install; return None (not an error)."""
    from core.policymeta import read_pr_number_for
    assert read_pr_number_for(tmp_path, "anything") is None


def test_read_pr_number_raises_on_malformed_yaml(tmp_path):
    """A corrupted sidecar should surface clearly rather than silently returning None."""
    from core.policymeta import read_pr_number_for, PolicymetaError
    policies = tmp_path / "policies"
    policies.mkdir()
    (policies / "broken.policymeta.yaml").write_text("not: [valid: yaml")
    with pytest.raises(PolicymetaError, match="policymeta"):
        read_pr_number_for(tmp_path, "broken")


def test_read_pr_number_raises_when_pr_number_missing(tmp_path):
    """A sidecar with no pr_number key is malformed."""
    from core.policymeta import read_pr_number_for, PolicymetaError
    policies = tmp_path / "policies"
    policies.mkdir()
    (policies / "no-pr.policymeta.yaml").write_text("other_field: x\n")
    with pytest.raises(PolicymetaError, match="pr_number"):
        read_pr_number_for(tmp_path, "no-pr")
```

- [ ] **Step 2: Run to confirm failure**

```bash
/Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest core/tests/test_policymeta.py -v 2>&1 | tail -10
```

Expected: `ModuleNotFoundError: No module named 'core.policymeta'` for every test.

- [ ] **Step 3: Implement the reader**

Create `core/policymeta.py`:

```python
"""Per-policy .policymeta.yaml sidecar reader.

The sidecar stores app-managed metadata that does NOT belong in the
policy's frontmatter (because it would clutter the published markdown).
Today it carries `pr_number`; future fields may include the head-branch
name or the last-known PR state.

Flat policies: `<working_dir>/policies/<slug>.policymeta.yaml`
Bundle policies: `<working_dir>/policies/<slug>/.policymeta.yaml`
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml


class PolicymetaError(RuntimeError):
    """Raised when a .policymeta.yaml file is present but malformed."""


def _candidate_paths(working_dir: Path, slug: str) -> list[Path]:
    policies_dir = working_dir / "policies"
    return [
        policies_dir / f"{slug}.policymeta.yaml",       # flat
        policies_dir / slug / ".policymeta.yaml",       # bundle
    ]


def read_pr_number_for(working_dir: Path, slug: str) -> Optional[int]:
    """Return the PR number tracked for `slug`, or None if no sidecar exists.

    Raises:
        PolicymetaError: If a sidecar exists but is not valid YAML, or if it
            is valid YAML but missing the required `pr_number` field.
    """
    for candidate in _candidate_paths(working_dir, slug):
        if not candidate.exists():
            continue
        try:
            data = yaml.safe_load(candidate.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise PolicymetaError(
                f"policymeta sidecar is not valid YAML: {candidate}: {exc}"
            ) from exc
        if not isinstance(data, dict) or "pr_number" not in data:
            raise PolicymetaError(
                f"policymeta sidecar at {candidate} is missing required field "
                f"`pr_number`"
            )
        try:
            return int(data["pr_number"])
        except (TypeError, ValueError) as exc:
            raise PolicymetaError(
                f"policymeta `pr_number` at {candidate} is not an integer: "
                f"{data['pr_number']!r}"
            ) from exc
    return None
```

- [ ] **Step 4: Run to confirm pass**

```bash
/Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest core/tests/test_policymeta.py -v 2>&1 | tail -10
```

Expected: 6 passing.

- [ ] **Step 5: Commit**

```bash
git add core/policymeta.py core/tests/test_policymeta.py
git commit -m "feat(APP-19): per-policy .policymeta.yaml sidecar reader"
```

---

## Task 5: `publish_policy` view (TDD)

**Files:**
- Modify: `core/views.py`
- Modify: `core/urls.py`
- Create: `core/tests/test_publish_policy.py`

The view's responsibilities:
1. POST only (GET returns 405).
2. `@login_required` — any authenticated user can publish in v0.1 (role-gating is a future ticket). Document this in the docstring.
3. Read the PR number from the sidecar via `read_pr_number_for`.
4. Pre-check the PR state via `GitHubProvider.read_pr_state`. Refuse anything other than `"reviewed"`.
5. Call `GitHubProvider.merge_pr(pr_number, working_dir, merge_method="squash")`.
6. On every outcome (success or any error class), add a Django messages.framework flash and redirect to `/catalog/`. No JSON, no rendered error page.

- [ ] **Step 1: Confirm messages framework is configured**

```bash
grep -n "django.contrib.messages\|MessageMiddleware\|MESSAGE_TAGS" /Users/chuck/PolicyWonk/policycodex_site/settings.py | head -10
```

Expected: `django.contrib.messages` in `INSTALLED_APPS` AND `django.contrib.messages.middleware.MessageMiddleware` in `MIDDLEWARE`. Both are present in Django's default `startproject` output, and APP-21's settings work already confirmed this file still has the defaults. If either is missing, STOP and report; that is out of scope for APP-19.

- [ ] **Step 2: Write the failing tests**

Create `core/tests/test_publish_policy.py`:

```python
"""Tests for the APP-19 publish action view."""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import override_settings
from django.urls import reverse

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(username="publisher", password="secret")


@pytest.fixture
def working_copy(tmp_path):
    """A minimal working copy with one policy + sidecar."""
    repo = tmp_path / "repo"
    policies = repo / "policies"
    policies.mkdir(parents=True)
    (policies / "code-of-conduct.md").write_text("---\ntitle: Code of Conduct\n---\n")
    (policies / "code-of-conduct.policymeta.yaml").write_text("pr_number: 42\n")
    return repo


def test_publish_policy_url_resolves():
    assert reverse("publish_policy", args=["my-slug"]) == "/policies/my-slug/publish/"


def test_publish_policy_requires_login(client):
    response = client.post("/policies/code-of-conduct/publish/")
    assert response.status_code == 302
    assert response.url.startswith("/login/")


def test_publish_policy_rejects_get(client, user):
    """GET is method-not-allowed; the action is mutation-only."""
    client.force_login(user)
    response = client.get("/policies/code-of-conduct/publish/")
    assert response.status_code == 405


def _patch_view_dependencies(*, working_dir, gate_state, merge_result=None, merge_exception=None):
    """Patch the view-layer collaborators. Returns the entered context manager
    so the test can inspect call args."""
    from core import views as core_views  # noqa: F401  (import to assert module path)

    config_mock = MagicMock()
    config_mock.working_dir = working_dir
    fake_provider = MagicMock()
    fake_provider.read_pr_state.return_value = gate_state
    if merge_exception is not None:
        fake_provider.merge_pr.side_effect = merge_exception
    elif merge_result is not None:
        fake_provider.merge_pr.return_value = merge_result
    else:
        fake_provider.merge_pr.return_value = {"merged": True, "sha": "abc", "merge_method": "squash"}

    return (
        patch("core.views.load_working_copy_config", return_value=config_mock),
        patch("core.views.GitHubProvider", return_value=fake_provider),
        fake_provider,
    )


def test_publish_policy_happy_path_merges_and_redirects(client, user, working_copy):
    client.force_login(user)
    cm_cfg, cm_prov, fake_provider = _patch_view_dependencies(
        working_dir=working_copy, gate_state="reviewed",
    )
    with cm_cfg, cm_prov:
        response = client.post("/policies/code-of-conduct/publish/")
    assert response.status_code == 302
    assert response.url == "/catalog/"
    fake_provider.read_pr_state.assert_called_once_with(42, working_copy)
    fake_provider.merge_pr.assert_called_once_with(42, working_copy, merge_method="squash")
    msgs = [str(m) for m in get_messages(response.wsgi_request)]
    assert any("published" in m.lower() or "merged" in m.lower() for m in msgs)


def test_publish_policy_refuses_drafted_pr(client, user, working_copy):
    """Gate guard: a Drafted (not-yet-approved) PR cannot be published."""
    client.force_login(user)
    cm_cfg, cm_prov, fake_provider = _patch_view_dependencies(
        working_dir=working_copy, gate_state="drafted",
    )
    with cm_cfg, cm_prov:
        response = client.post("/policies/code-of-conduct/publish/")
    assert response.status_code == 302
    assert response.url == "/catalog/"
    fake_provider.merge_pr.assert_not_called()
    msgs = [str(m) for m in get_messages(response.wsgi_request)]
    assert any("approval" in m.lower() or "reviewed" in m.lower() or "drafted" in m.lower() for m in msgs)


def test_publish_policy_refuses_already_published_pr(client, user, working_copy):
    """An already-merged PR cannot be re-published."""
    client.force_login(user)
    cm_cfg, cm_prov, fake_provider = _patch_view_dependencies(
        working_dir=working_copy, gate_state="published",
    )
    with cm_cfg, cm_prov:
        response = client.post("/policies/code-of-conduct/publish/")
    assert response.status_code == 302
    fake_provider.merge_pr.assert_not_called()
    msgs = [str(m) for m in get_messages(response.wsgi_request)]
    assert any("already" in m.lower() or "published" in m.lower() for m in msgs)


def test_publish_policy_handles_merge_conflict(client, user, working_copy):
    """merge_pr raising RuntimeError surfaces as a clear flash, not a 500."""
    client.force_login(user)
    cm_cfg, cm_prov, fake_provider = _patch_view_dependencies(
        working_dir=working_copy,
        gate_state="reviewed",
        merge_exception=RuntimeError("merge_pr failed for PR #42: 409 Merge conflict"),
    )
    with cm_cfg, cm_prov:
        response = client.post("/policies/code-of-conduct/publish/")
    assert response.status_code == 302
    assert response.url == "/catalog/"
    msgs = [str(m) for m in get_messages(response.wsgi_request)]
    assert any("merge" in m.lower() and ("conflict" in m.lower() or "fail" in m.lower()) for m in msgs)


def test_publish_policy_missing_sidecar_flashes_error(client, user, tmp_path):
    """A policy with no .policymeta.yaml has never been edited via the app and
    therefore has no PR to publish. Flash a clear error rather than 500ing."""
    client.force_login(user)
    repo = tmp_path / "repo"
    (repo / "policies").mkdir(parents=True)
    config_mock = MagicMock()
    config_mock.working_dir = repo
    with patch("core.views.load_working_copy_config", return_value=config_mock):
        with patch("core.views.GitHubProvider") as MockProvider:
            response = client.post("/policies/orphan/publish/")
            MockProvider.assert_not_called()  # never instantiated; we bail before
    assert response.status_code == 302
    assert response.url == "/catalog/"
    msgs = [str(m) for m in get_messages(response.wsgi_request)]
    assert any("no pending" in m.lower() or "no pull request" in m.lower() or "no pr" in m.lower() for m in msgs)


def test_publish_policy_handles_no_working_copy_configured(client, user):
    """If load_working_copy_config raises, flash error and redirect; do not 500."""
    client.force_login(user)
    with patch("core.views.load_working_copy_config", side_effect=RuntimeError("URL unset")):
        response = client.post("/policies/anything/publish/")
    assert response.status_code == 302
    assert response.url == "/catalog/"
    msgs = [str(m) for m in get_messages(response.wsgi_request)]
    assert any("not configured" in m.lower() or "onboarding" in m.lower() for m in msgs)
```

- [ ] **Step 3: Run to confirm failure**

```bash
/Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest core/tests/test_publish_policy.py -v 2>&1 | tail -20
```

Expected: `NoReverseMatch` for `publish_policy` URL name on every test; the URL is not yet wired.

- [ ] **Step 4: Implement the view**

Open `core/views.py`. Add the new imports near the existing imports:

```python
from django.contrib import messages
from django.views.decorators.http import require_http_methods

from app.git_provider.github_provider import GitHubProvider
from core.policymeta import PolicymetaError, read_pr_number_for
```

Append to the end of the file:

```python
@login_required
@require_http_methods(["POST"])
def publish_policy(request, slug):
    """Merge the open PR for `slug`, transitioning the gate to Published.

    v0.1 permission model: any authenticated user may publish. Role-gating
    (e.g. "only Publisher role") is a future ticket. The GitHub App token
    used by GitHubProvider has Contents + Pull-requests read/write
    (verified in REPO-03 checklist), which is the underlying authority.

    All outcomes (success or any error class) flash a message via Django's
    messages framework and redirect to /catalog/. No JSON, no rendered
    error page, no 500.
    """
    try:
        config = load_working_copy_config()
    except RuntimeError:
        messages.error(
            request,
            "Working copy is not configured. Complete the onboarding wizard first.",
        )
        return redirect("catalog")

    working_dir = config.working_dir

    try:
        pr_number = read_pr_number_for(working_dir, slug)
    except PolicymetaError as exc:
        messages.error(request, f"Policy metadata is malformed: {exc}")
        return redirect("catalog")

    if pr_number is None:
        messages.error(
            request,
            f"No pending pull request for '{slug}'. Open an edit first to create one.",
        )
        return redirect("catalog")

    provider = GitHubProvider()

    try:
        state = provider.read_pr_state(pr_number, working_dir)
    except Exception as exc:
        messages.error(request, f"Could not read PR state for #{pr_number}: {exc}")
        return redirect("catalog")

    if state == "published":
        messages.warning(request, f"PR #{pr_number} is already published.")
        return redirect("catalog")
    if state != "reviewed":
        messages.error(
            request,
            f"PR #{pr_number} is in state '{state}'. A reviewer must approve "
            "(transition to Reviewed) before it can be published.",
        )
        return redirect("catalog")

    try:
        result = provider.merge_pr(pr_number, working_dir, merge_method="squash")
    except RuntimeError as exc:
        messages.error(
            request,
            f"Merge failed for PR #{pr_number}: {exc}. Resolve the issue on "
            "GitHub (often a merge conflict or branch protection) and try again.",
        )
        return redirect("catalog")

    messages.success(
        request,
        f"Published '{slug}' (PR #{pr_number} merged as {result['sha'][:7]}).",
    )
    return redirect("catalog")
```

- [ ] **Step 5: Wire the URL**

Open `core/urls.py`. Add the publish route (preserving existing entries):

```python
"""URL routes for the core app."""
from django.urls import path

from . import views


urlpatterns = [
    path("", views.root_redirect, name="root"),
    path("health/", views.health, name="health"),
    path("catalog/", views.catalog, name="catalog"),
    path("policies/<slug:slug>/publish/", views.publish_policy, name="publish_policy"),
]
```

- [ ] **Step 6: Run to confirm pass**

```bash
/Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest core/tests/test_publish_policy.py -v 2>&1 | tail -20
```

Expected: 9 passing (URL resolves, login required, GET rejected, happy path, drafted refused, published refused, conflict handled, missing sidecar handled, no working copy handled).

- [ ] **Step 7: Commit**

```bash
git add core/views.py core/urls.py core/tests/test_publish_policy.py
git commit -m "feat(APP-19): publish_policy view with gate guard and flash messages"
```

---

## Task 6: Catalog template Publish button (TDD)

**Files:**
- Modify: `core/templates/catalog.html`
- Modify: `core/tests/test_catalog.py`

This task adds a per-row Publish button when the policy's gate state is `"reviewed"`. The view layer (`core.views.catalog`) does NOT yet attach gate state to each policy object; APP-17 (PR-state-to-gate mapping, dispatched in parallel) is the ticket that does that wiring. To keep APP-19 independently testable AND consistent with APP-17's eventual API, this plan defines the contract: the catalog view's context for each policy carries a `gate_state` attribute (one of `"drafted"`, `"reviewed"`, `"published"`, `"closed"`, or `None` for never-edited policies). The template renders the button when `gate_state == "reviewed"`.

We test the template by passing a stubbed `policies` list into the view (via the existing mock pattern in `test_catalog.py`) where each policy has a `gate_state` attribute. The view does not need to set this attribute itself for the template to render; the template is purely read-only.

- [ ] **Step 1: Write the failing tests**

Append to `core/tests/test_catalog.py`:

```python
def test_catalog_renders_publish_button_for_reviewed_policy(client, user):
    """A policy with gate_state='reviewed' renders a publish form."""
    from unittest.mock import patch
    client.force_login(user)
    policy = _stub_policy(slug="ready-to-publish", kind="flat", title="Ready")
    # Attach the gate_state attribute APP-17 will set.
    policy.gate_state = "reviewed"
    with override_settings(
        POLICYCODEX_POLICY_REPO_URL="https://example.com/x.git",
        POLICYCODEX_WORKING_COPY_ROOT="/tmp",
    ):
        with patch("core.views.Path.exists", return_value=True):
            with patch("core.views.BundleAwarePolicyReader") as MockReader:
                MockReader.return_value.read.return_value = iter([policy])
                response = client.get("/catalog/")
    body = response.content.decode()
    assert 'action="/policies/ready-to-publish/publish/"' in body
    assert 'method="post"' in body.lower()
    # CSRF token must be present.
    assert "csrfmiddlewaretoken" in body
    # Button text the user clicks.
    assert "Publish" in body


def test_catalog_does_not_render_publish_button_for_drafted_policy(client, user):
    """A policy in 'drafted' state must not show the publish button."""
    from unittest.mock import patch
    client.force_login(user)
    policy = _stub_policy(slug="still-drafting", kind="flat")
    policy.gate_state = "drafted"
    with override_settings(
        POLICYCODEX_POLICY_REPO_URL="https://example.com/x.git",
        POLICYCODEX_WORKING_COPY_ROOT="/tmp",
    ):
        with patch("core.views.Path.exists", return_value=True):
            with patch("core.views.BundleAwarePolicyReader") as MockReader:
                MockReader.return_value.read.return_value = iter([policy])
                response = client.get("/catalog/")
    body = response.content.decode()
    assert 'action="/policies/still-drafting/publish/"' not in body


def test_catalog_does_not_render_publish_button_for_already_published_policy(client, user):
    """A 'published' policy already merged shouldn't offer publish."""
    from unittest.mock import patch
    client.force_login(user)
    policy = _stub_policy(slug="already-shipped", kind="flat")
    policy.gate_state = "published"
    with override_settings(
        POLICYCODEX_POLICY_REPO_URL="https://example.com/x.git",
        POLICYCODEX_WORKING_COPY_ROOT="/tmp",
    ):
        with patch("core.views.Path.exists", return_value=True):
            with patch("core.views.BundleAwarePolicyReader") as MockReader:
                MockReader.return_value.read.return_value = iter([policy])
                response = client.get("/catalog/")
    body = response.content.decode()
    assert 'action="/policies/already-shipped/publish/"' not in body


def test_catalog_does_not_render_publish_button_for_never_edited_policy(client, user):
    """A policy with no gate_state attribute (never edited) shouldn't show publish."""
    from unittest.mock import patch
    client.force_login(user)
    policy = _stub_policy(slug="pristine", kind="flat")
    # No gate_state attribute. The template should treat this as "no button."
    with override_settings(
        POLICYCODEX_POLICY_REPO_URL="https://example.com/x.git",
        POLICYCODEX_WORKING_COPY_ROOT="/tmp",
    ):
        with patch("core.views.Path.exists", return_value=True):
            with patch("core.views.BundleAwarePolicyReader") as MockReader:
                MockReader.return_value.read.return_value = iter([policy])
                response = client.get("/catalog/")
    body = response.content.decode()
    assert 'action="/policies/pristine/publish/"' not in body
```

Note: the existing `LogicalPolicy` dataclass in `ingest/policy_reader.py` is frozen/immutable. The `_stub_policy` helper currently uses Django's `__init__` to build a `LogicalPolicy`, then the test mutates `policy.gate_state`. If `LogicalPolicy` is a frozen dataclass, this mutation will raise `dataclasses.FrozenInstanceError`. To avoid that, the test wraps each policy with a `SimpleNamespace` or similar mutable type.

Update `_stub_policy` (which lives in `test_catalog.py` from APP-06) if necessary. If `LogicalPolicy` is NOT frozen, no change is needed. Confirm by running:

```bash
grep -n "frozen\|@dataclass" /Users/chuck/PolicyWonk/ingest/policy_reader.py | head -3
```

If `frozen=True` appears, replace `_stub_policy` body with a `SimpleNamespace` that mirrors the same attribute shape:

```python
def _stub_policy(*, slug, kind="flat", title=None, foundational=False, provides=()):
    """Build a stand-in for an ingest.policy_reader.LogicalPolicy."""
    from types import SimpleNamespace
    from pathlib import Path
    pp = Path(f"/tmp/policies/{slug}.md") if kind == "flat" else Path(f"/tmp/policies/{slug}/policy.md")
    return SimpleNamespace(
        slug=slug,
        kind=kind,
        policy_path=pp,
        data_path=None if kind == "flat" else pp.parent / "data.yaml",
        frontmatter={"title": title or slug.replace("-", " ").title()},
        body="",
        foundational=foundational,
        provides=provides,
    )
```

If `LogicalPolicy` is not frozen, leave the existing helper as-is and just attach `policy.gate_state = ...` in each new test.

- [ ] **Step 2: Run to confirm failure**

```bash
/Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest core/tests/test_catalog.py -v -k publish 2>&1 | tail -10
```

Expected: 4 failing (none of the new tests pass because the template does not yet render a Publish button).

- [ ] **Step 3: Update the template**

Open `core/templates/catalog.html`. Replace the existing `<li class="policy">` block:

```html
        <li class="policy">
          <a href="#{{ policy.slug }}">{{ policy.frontmatter.title|default:policy.slug }}</a>
          <span class="kind-badge kind-{{ policy.kind }}">{{ policy.kind }}</span>
          {% if policy.foundational %}
            <span class="foundational-badge">(foundational)</span>
          {% endif %}
        </li>
```

with:

```html
        <li class="policy">
          <a href="#{{ policy.slug }}">{{ policy.frontmatter.title|default:policy.slug }}</a>
          <span class="kind-badge kind-{{ policy.kind }}">{{ policy.kind }}</span>
          {% if policy.foundational %}
            <span class="foundational-badge">(foundational)</span>
          {% endif %}
          {% if policy.gate_state %}
            <span class="gate-badge gate-{{ policy.gate_state }}">{{ policy.gate_state }}</span>
          {% endif %}
          {% if policy.gate_state == "reviewed" %}
            <form method="post" action="{% url 'publish_policy' slug=policy.slug %}" style="display:inline">
              {% csrf_token %}
              <button type="submit">Publish</button>
            </form>
          {% endif %}
        </li>
```

The `gate-badge` element is a thin nod to APP-17 (which will visualize gate state across all rows). APP-17 may rename the badge class or change the surrounding markup; this is fine. The load-bearing element for APP-19 is the `<form>` block, which APP-17 must NOT remove.

- [ ] **Step 4: Run to confirm pass**

```bash
/Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest core/tests/test_catalog.py -v 2>&1 | tail -15
```

Expected: all existing catalog tests still pass; 4 new publish-button tests pass. Total catalog tests: 9 (existing) + 4 (new) = 13.

- [ ] **Step 5: Display the messages framework flashes on the catalog page**

For the publish view's `messages.success/error/warning` flashes to actually render, the catalog template needs to iterate `{{ messages }}`. Add to `core/templates/catalog.html` immediately after the `<h2>Policy catalog</h2>` line:

```html
  {% if messages %}
    <ul class="messages">
      {% for message in messages %}
        <li class="message message-{{ message.tags }}">{{ message }}</li>
      {% endfor %}
    </ul>
  {% endif %}
```

This does not need its own test; the existing publish-view tests already verify `get_messages(response.wsgi_request)` returns the expected messages, which depends only on the messages framework being configured (verified in Task 5 Step 1).

- [ ] **Step 6: Full repo test suite**

```bash
cd /Users/chuck/PolicyWonk && /Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest -q 2>&1 | tail -3
```

Expected: baseline + 1 (test_base) + 6 (test_github_provider) + 6 (test_policymeta) + 9 (test_publish_policy) + 4 (test_catalog) = baseline + 26 new tests passing. From 180 baseline: 206. Capture the exact number.

- [ ] **Step 7: Commit**

```bash
git add core/templates/catalog.html core/tests/test_catalog.py
git commit -m "feat(APP-19): catalog template renders Publish button for reviewed policies"
```

---

## Task 7: Final verification + smoke + handoff

**Files:**
- None modified.

- [ ] **Step 1: Confirm `manage.py check` still clean**

```bash
/Users/chuck/PolicyWonk/spike/venv/bin/python manage.py check 2>&1 | tail -3
```

Expected: `System check identified no issues (0 silenced).` (One W001 warning is acceptable if `POLICYCODEX_POLICY_REPO_URL` is unset, per APP-21's onboarding gate; that is still exit 0.)

- [ ] **Step 2: Optional smoke against a live PR (skip without credentials)**

If the local environment has GitHub App credentials AND a real PR exists on the diocese's policy repo in `reviewed` state:

```bash
cd /Users/chuck/PolicyWonk
export POLICYCODEX_POLICY_REPO_URL="https://github.com/<org>/<repo>.git"
export POLICYCODEX_POLICY_BRANCH=main
export POLICYCODEX_WORKING_COPY_ROOT=/tmp/app19-smoke
/Users/chuck/PolicyWonk/spike/venv/bin/python manage.py pull_working_copy
# Manually craft a sidecar pointing at a real-but-test PR number:
echo "pr_number: <real-pr-number>" > /tmp/app19-smoke/<repo>/policies/<slug>.policymeta.yaml
# Start the server, log in, click Publish.
```

This is a hand-eye smoke. If credentials are not available, SKIP and note the skip in the self-report. The unit tests are authoritative.

- [ ] **Step 3: Confirm clean branch + commit history**

```bash
git status
git log --oneline main..HEAD
```

Expected: clean working tree; 5 commits since BASE `5017488`:

1. `feat(APP-19): add merge_pr abstract method to GitProvider`
2. `feat(APP-19): GitHubProvider.merge_pr (squash default, error wrapping)`
3. `feat(APP-19): per-policy .policymeta.yaml sidecar reader`
4. `feat(APP-19): publish_policy view with gate guard and flash messages`
5. `feat(APP-19): catalog template renders Publish button for reviewed policies`

If counts differ, surface in the self-report.

- [ ] **Step 4: Compose self-report**

Cover:
- Goal in one sentence.
- Branch name (`worktree-agent-<id>`) and final commit SHA.
- Files created / modified.
- Commit list with messages.
- Test count before / after (expect 180 → 206, or higher if APP-18 already merged).
- `manage.py check` result.
- Smoke result (Step 2): PASS / SKIPPED / FAIL with notes.
- Any deviations from the plan + rationale.
- Status: DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT.
- Explicit note on whether APP-18 merged ahead of APP-19 and whether the `test_base.py` merge conflict surfaced. If it did, describe the resolution.

- [ ] **Step 5: Handoff**

Do not merge to main. Do not push. The dispatching session will run spec-compliance review and code-quality review per `superpowers:subagent-driven-development`.

---

## Definition of Done

- `app/git_provider/base.py` declares `merge_pr` as `@abstractmethod` with signature `merge_pr(self, pr_number: int, working_dir: Path, merge_method: str = "squash") -> dict`.
- `app/git_provider/github_provider.py` implements `merge_pr` using `repo.get_pull(pr_number).merge(merge_method=...)`, defaulting `merge_method` to `"squash"`, raising `ValueError` for invalid `merge_method`, and raising `RuntimeError` on PyGithub `GithubException` or `merged=False` results.
- `app/git_provider/tests/test_base.py` has 8 missing-method test classes (`clone`, `branch`, `commit`, `push`, `pull`, `open_pr`, `read_pr_state`, `merge_pr`); each `IncompleteProvider` implements all 7 OTHER methods.
- `app/git_provider/tests/test_github_provider.py` has 6 new `test_merge_pr_*` tests covering squash default, explicit method override, invalid method rejection, `GithubException` 409 wrapping, `GithubException` 405 wrapping, and `merged=False` rejection.
- `core/policymeta.py` exists with `read_pr_number_for(working_dir, slug) -> Optional[int]` and a `PolicymetaError` exception class.
- `core/tests/test_policymeta.py` has 6 tests covering flat-sidecar, bundle-sidecar, absent-sidecar, absent-policies-dir, malformed-YAML, missing-pr_number-field.
- `core/views.py` has `publish_policy(request, slug)` decorated with `@login_required` and `@require_http_methods(["POST"])`.
- `core/urls.py` registers `path("policies/<slug:slug>/publish/", views.publish_policy, name="publish_policy")`.
- `core/templates/catalog.html` renders a `<form method="post">` Publish button only when `policy.gate_state == "reviewed"`; renders messages framework flashes near the top.
- `core/tests/test_publish_policy.py` has 9 tests: URL resolves, login required, GET rejected, happy path, drafted refused, published refused, merge conflict handled, missing sidecar handled, no working copy handled.
- `core/tests/test_catalog.py` has 4 new publish-button tests on top of the existing 9.
- Full repo test suite gains 26 tests (180 baseline → ~206; capture the exact number).
- `manage.py check` exits 0.
- 5 commits on the branch since BASE `5017488`, all with `APP-19` in the message.
- No edits outside the 9 files in **File Structure**.
- No em dashes anywhere in new content.
- No PT-specific tokens (`pt`, `PT`, `pensacola`, `tallahassee`) anywhere in new code or tests. PT names may appear ONLY in the optional smoke env exports in Task 7 (and that step uses generic `<org>/<repo>` placeholders).

---

## Self-Review

**Spec coverage:**
- Ticket says "Publish action in UI merges PR (requires merge permission)" → Task 5 view + Task 6 button + Task 3 `merge_pr` implementation ✓
- Gate model from CLAUDE.md: "Published = merged" → Task 5 view calls `merge_pr` only after `read_pr_state == "reviewed"` ✓
- Merge permission requirement → existing GitHub App config in `internal/REPO-03-GitHub-App-Checklist.md:33-34` has `Contents: Read and write` + `Pull requests: Read and write`; no new permission required (documented in plan header) ✓
- Failure modes (merge conflict, branch protection, rate-limit) → Task 3 tests cover 409 and 405 GithubException paths; Task 5 tests cover the view-layer surfacing as flash ✓
- v0.1 permission model (any authenticated user) → documented in `publish_policy` docstring (Task 5 Step 4) ✓
- Gate guard (refuse non-Reviewed) → Task 5 tests cover drafted-refused and published-refused ✓
- Squash merge method → Task 3 Step 3 (default + test) ✓
- Parallel-dispatch concern with APP-18 → header section flags it; Task 1 Step 2 anticipates the merge-from-main case ✓

**Placeholder scan:** No TBDs, no "TODO", no "implement later". Every step has a code block where code is needed. Every test has assertions. Every error has a clear message.

**Type consistency:**
- `merge_pr` signature `(pr_number: int, working_dir: Path, merge_method: str = "squash") -> dict` used identically in: ABC declaration (Task 2 Step 3), concrete implementation (Task 3 Step 3), `IncompleteProvider` stubs in `test_base.py` (Task 2 Step 1), view-layer call site (Task 5 Step 4), view-layer test mocks (Task 5 Step 2).
- Return shape `{"merged": bool, "sha": str, "merge_method": str}` consistent across implementation and tests.
- `read_pr_number_for(working_dir, slug)` signature consistent: Task 4 (definition), Task 5 (consumption).
- `PolicymetaError` exception class consistent across Task 4 (raised) and Task 5 (caught).
- URL name `"publish_policy"` consistent across `urls.py`, `reverse()` calls in tests, and `{% url %}` template tags.
- Template variable `policy.gate_state` is consistent across the template (Task 6 Step 3), the test stubs (Task 6 Step 1), and the documented APP-17 contract (header).

**Potential gotcha (already flagged):**
- Task 6 Step 1 includes a `LogicalPolicy` frozen-dataclass check. If `LogicalPolicy` is frozen, mutating `policy.gate_state = "reviewed"` in the test raises `FrozenInstanceError`; the plan provides a `SimpleNamespace` fallback. The implementer must read the actual `LogicalPolicy` definition once to decide.
- Task 5 Step 1 confirms `django.contrib.messages` is configured. Django's default `startproject` includes it, so this should be a no-op; the check is defensive.
- The parallel APP-18 conflict in `test_base.py` is mechanical, not architectural; whoever merges second resolves and the reviewer flags the resolution.

No other issues found.
