# APP-17 PR-State-to-Gate Mapping Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface the three-gate model (Drafted, Reviewed, Published) on the catalog page by mapping each policy to its current PR state via the diocese's branch-naming convention, with one batched GitHub call per page render.

**Architecture:** APP-04 already implemented the per-PR string mapping inside `GitHubProvider.read_pr_state` returning exactly `"drafted" | "reviewed" | "published" | "closed"`. APP-17 therefore is NOT about re-implementing the per-PR mapping. It does three things: (1) add one new GitProvider method `list_open_prs(working_dir) -> list[dict]` that batches "all open PRs" into a single GitHub API call and reports each PR's `head_branch` + already-mapped gate state; (2) add a small pure helper `slug_to_branch_prefix(slug) -> str` and `branch_to_slug(branch) -> str | None` that capture the v0.1 convention `policycodex/draft-<slug>` (used by APP-04's tests and by APP-07's edit form); (3) wire the catalog view to call `list_open_prs` once, build a `{slug: gate}` map, and pass each policy's gate into the template, defaulting to `"published"` when no open PR exists (the published state IS the main-branch state).

Performance choice: **batched, no cache.** One `GET /repos/{owner}/{repo}/pulls?state=open` per catalog render. Inside that one API call, the GitHub library hands us a paginated PRs collection; for each PR we read `pr.merged`, `pr.state`, `pr.head.ref`, and `pr.get_reviews()` (which IS a second call per PR). For v0.1 with a single diocese and a handful of open PRs on any given day, that cost is acceptable and avoids the cache-invalidation question. A future ticket can introduce a 5-minute cache; APP-17 does not.

**Tech Stack:** Django 5+, PyGithub (already a dep via APP-04), pytest, pytest-django.

**Ticket reference:** `PolicyWonk-v0.1-Tickets.md` APP-17 line 99 ("PR-state-to-gate mapping: Drafted (open), Reviewed (approved), Published (merged)").

**BASE:** `main` at SHA `5017488`.

**Discipline reminders:**
- TDD strict: every test in this plan must be observed-failing first, then passing. No skipping RED.
- No em dashes anywhere in new content (code, docstrings, comments, commit messages).
- Ship-generic: no `pt`, `PT`, `pensacola`, `tallahassee` tokens anywhere in the code, template, or test fixtures. The branch convention `policycodex/draft-<slug>` is the product's convention, not a diocese-specific one; it is fine to keep.
- Implementer dispatched via Agent tool `isolation: "worktree"` (the harness will auto-create `.claude/worktrees/agent-<id>/`).
- `>=` floor pins in any requirements file (none added by this ticket).

---

## Investigation result (do not skip reading)

`/Users/chuck/PolicyWonk/app/git_provider/github_provider.py:235-256` already implements the full mapping:

```python
def read_pr_state(self, pr_number: int, working_dir: Path) -> str:
    ...
    pr = repo.get_pull(pr_number)
    if pr.merged:
        return "published"
    if pr.state == "closed":
        return "closed"
    approvals = sum(
        1 for r in pr.get_reviews() if getattr(r, "state", None) == "APPROVED"
    )
    return "reviewed" if approvals >= 1 else "drafted"
```

`/Users/chuck/PolicyWonk/app/git_provider/tests/test_github_provider.py:221-249` already parametrizes all seven mapping cells (open+0=drafted, open+1=reviewed, open+3=reviewed, merged=published, closed-not-merged=closed). Do NOT rewrite or duplicate that mapping. APP-17 layers on top:
- `list_open_prs(working_dir) -> list[dict]` (new) builds an aggregate so the catalog view does not call `read_pr_state(pr_number, ...)` N times.
- Branch-to-slug parsing (new) lets the catalog look up "which PR matches this policy."
- Catalog template gets a third badge (Drafted/Reviewed/Published) using the per-policy gate state.

---

## File Structure

- Create: `app/git_provider/states.py` — pure module with `slug_to_branch_prefix(slug) -> str` and `branch_to_slug(branch) -> str | None`. Captures the v0.1 convention `policycodex/draft-<slug>`. Importable without Django or GitHub deps; trivial to unit-test.
- Modify: `app/git_provider/base.py` — add `list_open_prs(working_dir)` abstract method to `GitProvider`. Docstring nails the return shape.
- Modify: `app/git_provider/github_provider.py` — implement `list_open_prs(working_dir)`. Reuses the same "open + approvals -> gate" logic as `read_pr_state` but in batched form. Refactors the per-PR logic into a private helper `_pr_to_gate(pr) -> str` so both methods stay DRY.
- Modify: `app/git_provider/tests/test_github_provider.py` — add `test_list_open_prs_*` cases covering: no open PRs, one open PR with 0/1 approvals, multiple open PRs with mixed approvals, merged+closed PRs filtered out, return-shape stability.
- Modify: `app/git_provider/tests/test_base.py` — extend each `IncompleteProvider` test class to add a stub `list_open_prs` so existing tests keep passing; add one new `test_subclass_missing_list_open_prs_fails` test.
- Create: `app/git_provider/tests/test_states.py` — unit tests for `slug_to_branch_prefix` and `branch_to_slug` (round-trip, non-matching branches, slugs with hyphens, slugs that contain "draft-" substring).
- Modify: `core/views.py` — extend `catalog(request)` to call `GitHubProvider().list_open_prs(working_dir)`, build a `{slug: gate}` lookup via `branch_to_slug`, and attach `gate` to each policy via a small per-row dict OR by passing the lookup through to the template. Pick the dict-per-row approach so the template stays simple.
- Modify: `core/templates/catalog.html` — render a third badge (`<span class="gate-badge gate-{{ row.gate }}">{{ row.gate|title }}</span>`) on each policy row. Use `row.policy.frontmatter.title|default:row.policy.slug`, `row.policy.kind`, `row.policy.foundational`, `row.gate`.
- Modify: `core/tests/test_catalog.py` — extend existing catalog tests so the mocked policies render with the right gate badge; add tests that cover (a) policy with no open PR shows `Published`, (b) policy with `policycodex/draft-<slug>` open PR shows the mapped gate, (c) the page survives a `RuntimeError` from `list_open_prs` (network failure: degrades to "Published for all" rather than 500).

No other files touched. Working-copy code, ingest code, and Wave-2 templates stay stable.

---

## Task 1: Worktree pre-flight

**Files:**
- None modified.

- [ ] **Step 1: Confirm worktree state**

Run:

```bash
git rev-parse HEAD
git branch --show-current
git status --short
```

Expected: BASE SHA is `5017488` or a descendant; branch is the auto-worktree branch the harness gave you (something like `worktree-agent-<id>`); status is clean.

If anything is unexpected, STOP and report.

- [ ] **Step 2: Merge `main` into your worktree branch**

The harness's auto-worktree may have branched from a session-start commit older than current `main`. Run:

```bash
git fetch
git merge main --no-edit
```

Expected: either "Already up to date." or a clean fast-forward to current `main`.

- [ ] **Step 3: Confirm baseline test suite is green**

Run:

```bash
/Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest -q 2>&1 | tail -3
```

Expected: `180 passed` (current main count after APP-06 + APP-21 merged).

**Capture the baseline number** for the final report.

- [ ] **Step 4: Read the existing patterns this ticket follows**

Read each of these briefly to confirm signatures:

- `/Users/chuck/PolicyWonk/app/git_provider/base.py` (full file; understand the ABC pattern)
- `/Users/chuck/PolicyWonk/app/git_provider/github_provider.py:235-256` (the existing `read_pr_state` and its already-correct mapping)
- `/Users/chuck/PolicyWonk/app/git_provider/tests/test_github_provider.py:221-249` (the existing parametrized state-mapping test)
- `/Users/chuck/PolicyWonk/app/git_provider/tests/test_base.py:30-50` (the IncompleteProvider stub pattern)
- `/Users/chuck/PolicyWonk/ingest/policy_reader.py:22-34` (LogicalPolicy fields)
- `/Users/chuck/PolicyWonk/core/views.py:11-37` (current catalog view)
- `/Users/chuck/PolicyWonk/core/templates/catalog.html` (current row structure)
- `/Users/chuck/PolicyWonk/core/tests/test_catalog.py` (the user fixture + `force_login` + `BundleAwarePolicyReader` mocking pattern)

- [ ] **Step 5: No commit yet.**

---

## Task 2: Pure branch <-> slug helpers (TDD)

**Files:**
- Create: `app/git_provider/states.py`
- Create: `app/git_provider/tests/test_states.py`

- [ ] **Step 1: Write the failing tests**

Create `app/git_provider/tests/test_states.py`:

```python
"""Tests for the branch <-> slug naming convention helpers."""
import pytest

from app.git_provider.states import branch_to_slug, slug_to_branch_prefix


def test_slug_to_branch_prefix_simple():
    assert slug_to_branch_prefix("onboarding") == "policycodex/draft-onboarding"


def test_slug_to_branch_prefix_with_hyphens():
    assert slug_to_branch_prefix("document-retention") == "policycodex/draft-document-retention"


def test_branch_to_slug_simple():
    assert branch_to_slug("policycodex/draft-onboarding") == "onboarding"


def test_branch_to_slug_with_hyphens_in_slug():
    assert branch_to_slug("policycodex/draft-document-retention") == "document-retention"


def test_branch_to_slug_with_trailing_suffix():
    """APP-07 may add a per-edit suffix; the slug recovery must tolerate it."""
    assert branch_to_slug("policycodex/draft-onboarding-2") == "onboarding-2"


def test_branch_to_slug_returns_none_for_non_matching_branch():
    assert branch_to_slug("main") is None
    assert branch_to_slug("policycodex/something-else") is None
    assert branch_to_slug("feature/draft-onboarding") is None
    assert branch_to_slug("") is None


def test_round_trip_for_simple_slug():
    """slug_to_branch_prefix produces a branch that branch_to_slug recovers."""
    for slug in ("onboarding", "code-of-conduct", "document-retention"):
        assert branch_to_slug(slug_to_branch_prefix(slug)) == slug
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd /Users/chuck/PolicyWonk && /Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest app/git_provider/tests/test_states.py -v 2>&1 | tail -10
```

Expected: `ModuleNotFoundError: No module named 'app.git_provider.states'`.

- [ ] **Step 3: Create `app/git_provider/states.py`**

Write:

```python
"""Branch <-> slug naming convention helpers for PolicyCodex draft branches.

v0.1 convention: every policy edit lands on a branch named
`policycodex/draft-<slug>`, optionally with a trailing suffix to disambiguate
concurrent edits (e.g., `policycodex/draft-<slug>-2`). These helpers are pure
string functions: importable without Django or GitHub deps, trivial to test.
"""
from __future__ import annotations

_PREFIX = "policycodex/draft-"


def slug_to_branch_prefix(slug: str) -> str:
    """Return the canonical branch name for an edit of the given policy slug.

    APP-07's edit form uses this when opening a fresh branch; APP-17 uses it
    indirectly via `branch_to_slug` to recover the slug from a PR's head ref.
    """
    return f"{_PREFIX}{slug}"


def branch_to_slug(branch: str) -> str | None:
    """Recover the slug from a `policycodex/draft-<slug>[-<suffix>]` branch name.

    Returns None for branches that do not follow the convention. Note that a
    trailing numeric or alphabetical suffix becomes part of the returned slug;
    callers that care about exact-match should compare against the canonical
    `slug_to_branch_prefix(slug)` rather than relying on this function to strip
    suffixes.
    """
    if not branch or not branch.startswith(_PREFIX):
        return None
    tail = branch[len(_PREFIX):]
    return tail or None
```

- [ ] **Step 4: Run to confirm pass**

```bash
/Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest app/git_provider/tests/test_states.py -v 2>&1 | tail -10
```

Expected: 7 passing.

- [ ] **Step 5: Commit**

```bash
git add app/git_provider/states.py app/git_provider/tests/test_states.py
git commit -m "feat(APP-17): branch <-> slug helpers for policycodex/draft-* convention"
```

---

## Task 3: Add `list_open_prs` to the ABC + extend IncompleteProvider stubs (TDD)

**Files:**
- Modify: `app/git_provider/base.py`
- Modify: `app/git_provider/tests/test_base.py`

- [ ] **Step 1: Write the failing test**

Open `app/git_provider/tests/test_base.py`. Find the existing `TestGitProviderSubclassMissingMethods` class. Append a new test method at the end of that class (same indentation as the existing `test_subclass_missing_*_fails` tests):

```python
    def test_subclass_missing_list_open_prs_fails(self):
        """Subclass missing list_open_prs() cannot instantiate."""
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

- [ ] **Step 2: Run to confirm failure**

```bash
/Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest app/git_provider/tests/test_base.py -v 2>&1 | tail -10
```

Expected: the new test currently passes (because `list_open_prs` is NOT yet abstract). Wait, that means it does NOT fail. To make it fail correctly (RED before GREEN), we must FIRST add `list_open_prs` to the ABC, which will then make the EXISTING IncompleteProvider tests that DO implement all current abstract methods fail because they no longer cover the new abstract method.

Re-frame: the RED state for this task is "the existing IncompleteProvider tests in test_base.py break when we add the new abstract method, because their stubs are now incomplete." Let's drive that order.

Skip ahead: add the abstract method first (Step 3), THEN re-run the test suite, observe the breakage, fix the existing IncompleteProvider stubs to include the new abstract, observe the new test pass, and the existing tests stay green.

- [ ] **Step 3: Add the abstract method**

Open `app/git_provider/base.py`. Append after the existing `read_pr_state` abstract method (just before the closing of the class):

```python
    @abstractmethod
    def list_open_prs(self, working_dir: Path) -> list[dict]:
        """List all currently-open pull requests on the repository, with each
        PR's head branch and pre-mapped gate state.

        This is a batched alternative to calling `read_pr_state` once per PR:
        one API call returns the whole open-PR set, which the catalog view uses
        to build a `{slug: gate}` map for badge rendering.

        Args:
            working_dir: Path to the repository working directory.

        Returns:
            A list of dicts, one per open PR. Each dict has:
              - "pr_number": int (the PR number on the provider)
              - "head_branch": str (the source branch; e.g., "policycodex/draft-foo")
              - "gate": str (one of "drafted" | "reviewed"; merged and closed
                PRs are NOT included because they are not "open")
              - "url": str (the PR's web URL, for future detail-view linking)
        """
        pass
```

- [ ] **Step 4: Run to confirm RED on the existing tests**

```bash
/Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest app/git_provider/tests/test_base.py -v 2>&1 | tail -15
```

Expected: the existing IncompleteProvider tests now pass FOR THE WRONG REASON (they expected the class to fail to instantiate due to a missing method, and adding a NEW required method means EVERY existing IncompleteProvider stub is now also missing `list_open_prs`, which is the SAME failure mode they already assert). They keep passing.

Re-frame the RED: the actually-broken test is `test_github_provider_is_git_provider` in `test_github_provider.py`, which DOES instantiate the full `GitHubProvider` class. That will now fail because `GitHubProvider` lacks `list_open_prs`. Verify:

```bash
/Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest app/git_provider/tests/test_github_provider.py::test_github_provider_is_git_provider -v 2>&1 | tail -10
```

Expected: TypeError mentioning that `GitHubProvider` cannot be instantiated because it has not implemented `list_open_prs`.

- [ ] **Step 5: Add the new IncompleteProvider test**

Append the new test method from Step 1 above to `TestGitProviderSubclassMissingMethods` in `app/git_provider/tests/test_base.py`. Now also update EACH of the existing `IncompleteProvider` definitions in the SAME file to add `list_open_prs` to their method stubs. Each existing test class defines a different `IncompleteProvider` that is missing exactly ONE method (the method under test) but implements all OTHERS. For every one of those classes, add this stub method alongside the others:

```python
            def list_open_prs(self, working_dir: Path) -> list[dict]:
                pass
```

There are seven such IncompleteProvider classes (one per existing abstract method test); add the stub to each one. The new `test_subclass_missing_list_open_prs_fails` is the only one that should NOT have the stub.

- [ ] **Step 6: Run to confirm**

```bash
/Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest app/git_provider/tests/test_base.py -v 2>&1 | tail -15
```

Expected: all 8 tests in the file pass (7 original + 1 new).

- [ ] **Step 7: Run the full git_provider test suite**

```bash
/Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest app/git_provider/tests/ -v 2>&1 | tail -10
```

Expected: tests in `test_github_provider.py` that instantiate `GitHubProvider` (e.g., `test_github_provider_is_git_provider`) now FAIL with TypeError about the missing `list_open_prs`. This is the correct RED for Task 4.

- [ ] **Step 8: Commit**

```bash
git add app/git_provider/base.py app/git_provider/tests/test_base.py
git commit -m "feat(APP-17): add list_open_prs abstract method to GitProvider"
```

---

## Task 4: Implement `list_open_prs` in GitHubProvider (TDD)

**Files:**
- Modify: `app/git_provider/github_provider.py`
- Modify: `app/git_provider/tests/test_github_provider.py`

- [ ] **Step 1: Write the failing tests**

Append to `app/git_provider/tests/test_github_provider.py`:

```python
def test_list_open_prs_empty_when_no_open_prs(tmp_path):
    cfg = _fake_config(tmp_path)
    (tmp_path / "key.pem").write_text("FAKE PEM")
    wd = tmp_path / "wd"
    fake_repo = MagicMock()
    fake_repo.get_pulls.return_value = []
    fake_client = MagicMock()
    fake_client.get_repo.return_value = fake_repo
    with patch("app.git_provider.github_provider.subprocess.run") as run:
        run.return_value = MagicMock(returncode=0, stdout=b"https://github.com/foo/bar.git\n")
        p = GitHubProvider(config=cfg, github_client=fake_client)
        result = p.list_open_prs(wd)
    assert result == []
    fake_repo.get_pulls.assert_called_once_with(state="open")


def test_list_open_prs_returns_one_drafted_pr(tmp_path):
    cfg = _fake_config(tmp_path)
    (tmp_path / "key.pem").write_text("FAKE PEM")
    wd = tmp_path / "wd"
    fake_pr = MagicMock(
        number=42,
        state="open",
        merged=False,
        html_url="https://github.com/foo/bar/pull/42",
    )
    fake_pr.head.ref = "policycodex/draft-onboarding"
    fake_pr.get_reviews.return_value = []
    fake_repo = MagicMock()
    fake_repo.get_pulls.return_value = [fake_pr]
    fake_client = MagicMock()
    fake_client.get_repo.return_value = fake_repo
    with patch("app.git_provider.github_provider.subprocess.run") as run:
        run.return_value = MagicMock(returncode=0, stdout=b"https://github.com/foo/bar.git\n")
        p = GitHubProvider(config=cfg, github_client=fake_client)
        result = p.list_open_prs(wd)
    assert result == [{
        "pr_number": 42,
        "head_branch": "policycodex/draft-onboarding",
        "gate": "drafted",
        "url": "https://github.com/foo/bar/pull/42",
    }]


def test_list_open_prs_marks_approved_pr_as_reviewed(tmp_path):
    cfg = _fake_config(tmp_path)
    (tmp_path / "key.pem").write_text("FAKE PEM")
    wd = tmp_path / "wd"
    approved = MagicMock(); approved.state = "APPROVED"
    commented = MagicMock(); commented.state = "COMMENTED"
    fake_pr = MagicMock(
        number=7,
        state="open",
        merged=False,
        html_url="https://github.com/foo/bar/pull/7",
    )
    fake_pr.head.ref = "policycodex/draft-retention"
    fake_pr.get_reviews.return_value = [commented, approved]
    fake_repo = MagicMock()
    fake_repo.get_pulls.return_value = [fake_pr]
    fake_client = MagicMock()
    fake_client.get_repo.return_value = fake_repo
    with patch("app.git_provider.github_provider.subprocess.run") as run:
        run.return_value = MagicMock(returncode=0, stdout=b"https://github.com/foo/bar.git\n")
        p = GitHubProvider(config=cfg, github_client=fake_client)
        result = p.list_open_prs(wd)
    assert len(result) == 1
    assert result[0]["gate"] == "reviewed"
    assert result[0]["head_branch"] == "policycodex/draft-retention"


def test_list_open_prs_returns_mixed_drafted_and_reviewed(tmp_path):
    cfg = _fake_config(tmp_path)
    (tmp_path / "key.pem").write_text("FAKE PEM")
    wd = tmp_path / "wd"

    pr_drafted = MagicMock(number=1, state="open", merged=False, html_url="u1")
    pr_drafted.head.ref = "policycodex/draft-foo"
    pr_drafted.get_reviews.return_value = []

    approved = MagicMock(); approved.state = "APPROVED"
    pr_reviewed = MagicMock(number=2, state="open", merged=False, html_url="u2")
    pr_reviewed.head.ref = "policycodex/draft-bar"
    pr_reviewed.get_reviews.return_value = [approved]

    fake_repo = MagicMock()
    fake_repo.get_pulls.return_value = [pr_drafted, pr_reviewed]
    fake_client = MagicMock()
    fake_client.get_repo.return_value = fake_repo
    with patch("app.git_provider.github_provider.subprocess.run") as run:
        run.return_value = MagicMock(returncode=0, stdout=b"https://github.com/foo/bar.git\n")
        p = GitHubProvider(config=cfg, github_client=fake_client)
        result = p.list_open_prs(wd)
    gates = {row["head_branch"]: row["gate"] for row in result}
    assert gates == {
        "policycodex/draft-foo": "drafted",
        "policycodex/draft-bar": "reviewed",
    }


def test_list_open_prs_passes_state_open_filter(tmp_path):
    """The library call must filter to state=open at the API layer (not via
    a post-fetch Python filter), to avoid pulling merged/closed history."""
    cfg = _fake_config(tmp_path)
    (tmp_path / "key.pem").write_text("FAKE PEM")
    wd = tmp_path / "wd"
    fake_repo = MagicMock()
    fake_repo.get_pulls.return_value = []
    fake_client = MagicMock()
    fake_client.get_repo.return_value = fake_repo
    with patch("app.git_provider.github_provider.subprocess.run") as run:
        run.return_value = MagicMock(returncode=0, stdout=b"https://github.com/foo/bar.git\n")
        p = GitHubProvider(config=cfg, github_client=fake_client)
        p.list_open_prs(wd)
    fake_repo.get_pulls.assert_called_once_with(state="open")
```

- [ ] **Step 2: Run to confirm failure**

```bash
/Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest app/git_provider/tests/test_github_provider.py -k list_open_prs -v 2>&1 | tail -15
```

Expected: 5 failures, all referencing TypeError "cannot instantiate GitHubProvider" because `list_open_prs` is still abstract (Task 3 made it required; Task 4 implements it).

- [ ] **Step 3: Refactor the per-PR gate logic into a private helper**

Open `app/git_provider/github_provider.py`. Add a private module-level helper just above the `GitHubProvider` class (after `_build_installation_token`):

```python
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
```

Then refactor `read_pr_state` to call this helper. Replace its body (lines 235-256) with:

```python
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
        return _pr_to_gate(pr)
```

- [ ] **Step 4: Run the existing read_pr_state mapping tests**

```bash
/Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest app/git_provider/tests/test_github_provider.py::test_read_pr_state_mapping -v 2>&1 | tail -10
```

Expected: 7 cases still passing (the refactor is behavior-preserving).

- [ ] **Step 5: Implement `list_open_prs`**

Append a new method to the `GitHubProvider` class, just after `read_pr_state`:

```python
    def list_open_prs(self, working_dir: Path) -> list[dict]:
        """Batched alternative to read_pr_state: one API call returns all open
        PRs along with their head branch + gate state, so the catalog view can
        build a {slug: gate} map without N round-trips."""
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
        result: list[dict] = []
        for pr in repo.get_pulls(state="open"):
            result.append({
                "pr_number": pr.number,
                "head_branch": pr.head.ref,
                "gate": _pr_to_gate(pr),
                "url": pr.html_url,
            })
        return result
```

- [ ] **Step 6: Run all list_open_prs tests**

```bash
/Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest app/git_provider/tests/test_github_provider.py -k list_open_prs -v 2>&1 | tail -10
```

Expected: 5 passing.

- [ ] **Step 7: Run the full git_provider suite**

```bash
/Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest app/git_provider/tests/ -v 2>&1 | tail -10
```

Expected: all green. The previously-failing `test_github_provider_is_git_provider` (Task 3 Step 7) now passes because `GitHubProvider` implements all abstracts.

- [ ] **Step 8: Commit**

```bash
git add app/git_provider/github_provider.py app/git_provider/tests/test_github_provider.py
git commit -m "feat(APP-17): GitHubProvider.list_open_prs + _pr_to_gate refactor"
```

---

## Task 5: Wire the catalog view to fetch + attach gates (TDD)

**Files:**
- Modify: `core/views.py`
- Modify: `core/tests/test_catalog.py`

The catalog view currently passes `policies` (a `list[LogicalPolicy]`) to the template. We need to pass a list of dicts shaped like `{"policy": LogicalPolicy, "gate": "drafted" | "reviewed" | "published"}` so the template can render the gate badge per row.

- [ ] **Step 1: Write the failing tests**

Append to `core/tests/test_catalog.py`:

```python
def test_catalog_shows_published_gate_for_policies_without_open_pr(client, user):
    """Default gate when no open PR exists for the policy's slug."""
    client.force_login(user)
    policies = [
        _stub_policy(slug="onboarding", kind="flat", title="Onboarding"),
    ]
    with override_settings(
        POLICYCODEX_POLICY_REPO_URL="https://example.com/x.git",
        POLICYCODEX_WORKING_COPY_ROOT="/tmp",
    ):
        with patch("core.views.Path.exists", return_value=True):
            with patch("core.views.BundleAwarePolicyReader") as MockReader:
                MockReader.return_value.read.return_value = iter(policies)
                with patch("core.views.GitHubProvider") as MockProvider:
                    MockProvider.return_value.list_open_prs.return_value = []
                    response = client.get("/catalog/")

    body = response.content.decode()
    assert response.status_code == 200
    # A Published badge appears for the row.
    assert "gate-published" in body
    assert "Published" in body


def test_catalog_shows_drafted_gate_when_open_pr_has_no_approval(client, user):
    client.force_login(user)
    policies = [_stub_policy(slug="onboarding", kind="flat", title="Onboarding")]
    open_prs = [{
        "pr_number": 1,
        "head_branch": "policycodex/draft-onboarding",
        "gate": "drafted",
        "url": "https://example.com/p/1",
    }]
    with override_settings(
        POLICYCODEX_POLICY_REPO_URL="https://example.com/x.git",
        POLICYCODEX_WORKING_COPY_ROOT="/tmp",
    ):
        with patch("core.views.Path.exists", return_value=True):
            with patch("core.views.BundleAwarePolicyReader") as MockReader:
                MockReader.return_value.read.return_value = iter(policies)
                with patch("core.views.GitHubProvider") as MockProvider:
                    MockProvider.return_value.list_open_prs.return_value = open_prs
                    response = client.get("/catalog/")

    body = response.content.decode()
    assert "gate-drafted" in body
    assert "Drafted" in body
    assert "gate-published" not in body


def test_catalog_shows_reviewed_gate_when_open_pr_is_approved(client, user):
    client.force_login(user)
    policies = [_stub_policy(slug="retention", kind="bundle", title="Retention", foundational=True, provides=("classifications",))]
    open_prs = [{
        "pr_number": 9,
        "head_branch": "policycodex/draft-retention",
        "gate": "reviewed",
        "url": "https://example.com/p/9",
    }]
    with override_settings(
        POLICYCODEX_POLICY_REPO_URL="https://example.com/x.git",
        POLICYCODEX_WORKING_COPY_ROOT="/tmp",
    ):
        with patch("core.views.Path.exists", return_value=True):
            with patch("core.views.BundleAwarePolicyReader") as MockReader:
                MockReader.return_value.read.return_value = iter(policies)
                with patch("core.views.GitHubProvider") as MockProvider:
                    MockProvider.return_value.list_open_prs.return_value = open_prs
                    response = client.get("/catalog/")

    body = response.content.decode()
    assert "gate-reviewed" in body
    assert "Reviewed" in body


def test_catalog_mixed_gates_render_correctly(client, user):
    """Three policies: one with no PR, one drafted, one reviewed."""
    client.force_login(user)
    policies = [
        _stub_policy(slug="a-no-pr", kind="flat"),
        _stub_policy(slug="b-drafted", kind="flat"),
        _stub_policy(slug="c-reviewed", kind="flat"),
    ]
    open_prs = [
        {"pr_number": 1, "head_branch": "policycodex/draft-b-drafted", "gate": "drafted", "url": "u1"},
        {"pr_number": 2, "head_branch": "policycodex/draft-c-reviewed", "gate": "reviewed", "url": "u2"},
    ]
    with override_settings(
        POLICYCODEX_POLICY_REPO_URL="https://example.com/x.git",
        POLICYCODEX_WORKING_COPY_ROOT="/tmp",
    ):
        with patch("core.views.Path.exists", return_value=True):
            with patch("core.views.BundleAwarePolicyReader") as MockReader:
                MockReader.return_value.read.return_value = iter(policies)
                with patch("core.views.GitHubProvider") as MockProvider:
                    MockProvider.return_value.list_open_prs.return_value = open_prs
                    response = client.get("/catalog/")

    body = response.content.decode()
    # One of each badge appears.
    assert body.count("gate-published") == 1
    assert body.count("gate-drafted") == 1
    assert body.count("gate-reviewed") == 1


def test_catalog_ignores_open_prs_whose_head_branch_is_not_convention(client, user):
    """A PR on a branch like `feature/something` does not match any slug; it
    should be silently ignored (no crash, no misattribution)."""
    client.force_login(user)
    policies = [_stub_policy(slug="onboarding", kind="flat")]
    open_prs = [{
        "pr_number": 99,
        "head_branch": "feature/unrelated",
        "gate": "drafted",
        "url": "u99",
    }]
    with override_settings(
        POLICYCODEX_POLICY_REPO_URL="https://example.com/x.git",
        POLICYCODEX_WORKING_COPY_ROOT="/tmp",
    ):
        with patch("core.views.Path.exists", return_value=True):
            with patch("core.views.BundleAwarePolicyReader") as MockReader:
                MockReader.return_value.read.return_value = iter(policies)
                with patch("core.views.GitHubProvider") as MockProvider:
                    MockProvider.return_value.list_open_prs.return_value = open_prs
                    response = client.get("/catalog/")

    body = response.content.decode()
    # The unrelated PR did not match; the policy still shows Published.
    assert "gate-published" in body
    assert "gate-drafted" not in body


def test_catalog_degrades_gracefully_when_list_open_prs_raises(client, user):
    """Provider raising RuntimeError (e.g., network failure or unconfigured
    credentials) must not 500 the catalog. The page renders with every policy
    treated as Published."""
    client.force_login(user)
    policies = [_stub_policy(slug="onboarding", kind="flat")]
    with override_settings(
        POLICYCODEX_POLICY_REPO_URL="https://example.com/x.git",
        POLICYCODEX_WORKING_COPY_ROOT="/tmp",
    ):
        with patch("core.views.Path.exists", return_value=True):
            with patch("core.views.BundleAwarePolicyReader") as MockReader:
                MockReader.return_value.read.return_value = iter(policies)
                with patch("core.views.GitHubProvider") as MockProvider:
                    MockProvider.return_value.list_open_prs.side_effect = RuntimeError("network down")
                    response = client.get("/catalog/")

    assert response.status_code == 200
    body = response.content.decode()
    assert "gate-published" in body
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd /Users/chuck/PolicyWonk && /Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest core/tests/test_catalog.py -k gate -v 2>&1 | tail -15
```

Expected: 6 new failures. Most likely `AttributeError` on patching `core.views.GitHubProvider` (not yet imported there) or simply template-doesn't-contain-"gate-published" assertion failures.

- [ ] **Step 3: Update `core/views.py`**

Replace the file contents with:

```python
from pathlib import Path

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render

from app.git_provider import GitHubProvider
from app.git_provider.states import branch_to_slug
from app.working_copy.config import load_working_copy_config
from ingest.policy_reader import BundleAwarePolicyReader


def health(request):
    return JsonResponse({"status": "ok"})


def _build_gate_lookup(working_dir: Path) -> dict[str, str]:
    """Call list_open_prs once and return a {slug: gate} map.

    Returns an empty dict on any provider failure: the catalog gracefully
    falls back to treating every policy as Published when GitHub is
    unreachable. Logging the failure is a follow-up; v0.1 prioritizes the
    page rendering over surfacing the network error.
    """
    try:
        provider = GitHubProvider()
        open_prs = provider.list_open_prs(working_dir)
    except Exception:
        return {}

    lookup: dict[str, str] = {}
    for pr in open_prs:
        slug = branch_to_slug(pr.get("head_branch", ""))
        if slug is None:
            continue
        # If two PRs target the same slug (shouldn't happen with branch
        # protection, but defensive), keep the more-advanced gate.
        existing = lookup.get(slug)
        if existing == "reviewed":
            continue
        lookup[slug] = pr.get("gate", "drafted")
    return lookup


@login_required
def catalog(request):
    """Render the policy inventory from the local working copy.

    Falls back to an empty-state template when the working copy is not
    yet configured (fresh install before onboarding) or not yet synced.
    """
    try:
        config = load_working_copy_config()
    except RuntimeError:
        return render(request, "catalog.html", {"is_empty_onboarding": True, "rows": []})

    policies_dir: Path = config.working_dir / "policies"
    if not policies_dir.exists():
        return render(request, "catalog.html", {"is_empty_onboarding": True, "rows": []})

    policies = list(BundleAwarePolicyReader(policies_dir).read())
    gate_lookup = _build_gate_lookup(config.working_dir)
    rows = [
        {"policy": policy, "gate": gate_lookup.get(policy.slug, "published")}
        for policy in policies
    ]
    return render(request, "catalog.html", {"is_empty_onboarding": False, "rows": rows})


def root_redirect(request):
    """Send the root URL `/` to `/catalog/`. `catalog` itself handles login_required."""
    return redirect("catalog")
```

Note: this renames the template context from `policies` to `rows` (each row is `{"policy": ..., "gate": ...}`). The template update in Task 6 matches. The existing Wave-2 catalog tests that look for "(foundational)" and per-policy titles need to keep working; the template must continue to render those fields off `row.policy.*`.

- [ ] **Step 4: Run the new gate tests**

```bash
/Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest core/tests/test_catalog.py -k gate -v 2>&1 | tail -15
```

Expected: still failing because the template still references `policies`, not `rows`. That is fine; Task 6 fixes the template.

- [ ] **Step 5: No commit yet.** Task 6's template update must land in the same commit to keep main always-green-on-checkout.

---

## Task 6: Render the gate badge in the catalog template + adjust existing tests (TDD)

**Files:**
- Modify: `core/templates/catalog.html`
- Modify: `core/tests/test_catalog.py`

- [ ] **Step 1: Update the template**

Replace `core/templates/catalog.html` contents with:

```html
{% extends "base.html" %}

{% block title %}Catalog | PolicyCodex{% endblock %}

{% block content %}
  <h2>Policy catalog</h2>

  {% if is_empty_onboarding %}
    <section class="empty-state">
      <p>No policies yet.</p>
      <p>
        Run the onboarding wizard, or sync the diocese's policy repo by running
        <code>python manage.py pull_working_copy</code> on the server.
      </p>
    </section>
  {% else %}
    <ul class="policy-list">
      {% for row in rows %}
        <li class="policy">
          <a href="#{{ row.policy.slug }}">{{ row.policy.frontmatter.title|default:row.policy.slug }}</a>
          <span class="kind-badge kind-{{ row.policy.kind }}">{{ row.policy.kind }}</span>
          {% if row.policy.foundational %}
            <span class="foundational-badge">(foundational)</span>
          {% endif %}
          <span class="gate-badge gate-{{ row.gate }}">{{ row.gate|title }}</span>
        </li>
      {% empty %}
        <li class="no-results">No policies in the working copy.</li>
      {% endfor %}
    </ul>
  {% endif %}
{% endblock %}
```

- [ ] **Step 2: Update the existing Wave-2 catalog tests**

The Wave-2 tests in `core/tests/test_catalog.py` (lines that build `policies` via `_stub_policy` and assert against the rendered body) still work as-is for body-text assertions like "Document Retention Policy" — those text strings still appear via `{{ row.policy.frontmatter.title }}`. But if any Wave-2 test mocks `BundleAwarePolicyReader` AND patches the response shape via `MockReader.return_value.read.return_value = iter(...)`, the new code path also calls `GitHubProvider().list_open_prs(...)`. Without a mock for `core.views.GitHubProvider`, the live `GitHubProvider()` constructor will try to read credentials from disk and FAIL at import-time.

To keep the existing tests green:

Option A (minimal): every existing Wave-2 test that gets past the empty-state path needs to ALSO mock `GitHubProvider`. The simplest fix is to add `patch("core.views.GitHubProvider")` to each affected test, with `.return_value.list_open_prs.return_value = []` so the gate lookup is empty (all "published"). The body-text assertions for kind/title/foundational still pass.

Option B (preferred): introduce a pytest fixture `auto_mock_github_provider` in `core/tests/test_catalog.py` that auto-patches `core.views.GitHubProvider.list_open_prs` to return `[]` for every test that hits the non-empty-onboarding path. Use the `autouse=True` parameter to apply it implicitly.

Use Option B. Add this fixture near the top of `core/tests/test_catalog.py` (just after the `user` fixture):

```python
@pytest.fixture
def stub_gh_provider():
    """Patch GitHubProvider used by core.views to a MagicMock with list_open_prs=[].

    Tests that need a non-empty open-PR set override this by re-patching the
    same path inside the test body (the inner `with patch(...)` wins).
    """
    with patch("core.views.GitHubProvider") as MockProvider:
        MockProvider.return_value.list_open_prs.return_value = []
        yield MockProvider
```

Then update each existing test that exercises the happy-path (where `Path.exists` is patched to True) to take `stub_gh_provider` as a parameter. Specifically these Wave-2 tests:
- `test_catalog_renders_policies_when_working_copy_exists`
- `test_catalog_distinguishes_flat_from_bundle`
- `test_catalog_marks_foundational_bundles`

For each, change the signature from `(client, user)` to `(client, user, stub_gh_provider)`.

The empty-state tests (`test_catalog_empty_state_when_repo_url_unset`, `test_catalog_empty_state_when_policies_dir_missing`) do NOT need the fixture because the early-return happens before `GitHubProvider()` is constructed.

The new gate tests added in Task 5 do their own inner `with patch("core.views.GitHubProvider")`; they do NOT need the fixture.

- [ ] **Step 3: Run the full catalog test file**

```bash
/Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest core/tests/test_catalog.py -v 2>&1 | tail -20
```

Expected: all tests pass (the 9 Wave-2 tests + the 6 new gate tests from Task 5 = 15 total).

If any Wave-2 test fails, debug:
- "TemplateSyntaxError" or "VariableDoesNotExist" likely means a template change references a field that the stub policy lacks.
- "TypeError: GitHubProvider() ..." likely means a Wave-2 test reached the happy path without the `stub_gh_provider` fixture; add it.

- [ ] **Step 4: Run the full repo test suite**

```bash
cd /Users/chuck/PolicyWonk && /Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest -q 2>&1 | tail -3
```

Expected: `180` (baseline) + 7 (Task 2 states) + 1 (Task 3 base ABC) + 5 (Task 4 list_open_prs) + 6 (Task 5 gate tests) = **199 passing**. Note: no Wave-2 tests were added or removed; they only had their fixture wired.

Capture the exact number.

- [ ] **Step 5: Confirm `manage.py check` clean**

```bash
/Users/chuck/PolicyWonk/spike/venv/bin/python manage.py check 2>&1 | tail -3
```

Expected: `System check identified no issues (0 silenced).` (Or one APP-21 Warning if `POLICYCODEX_POLICY_REPO_URL` is unset; that is still exit 0 and fine.)

- [ ] **Step 6: Commit**

```bash
git add core/views.py core/templates/catalog.html core/tests/test_catalog.py
git commit -m "feat(APP-17): render gate badge per policy in catalog view"
```

---

## Task 7: Final verification + smoke + handoff

**Files:**
- None modified.

- [ ] **Step 1: Confirm clean branch + commit history**

```bash
git status
git log --oneline main..HEAD
```

Expected: clean working tree; 4 commits since BASE `5017488`:

1. `feat(APP-17): branch <-> slug helpers for policycodex/draft-* convention`
2. `feat(APP-17): add list_open_prs abstract method to GitProvider`
3. `feat(APP-17): GitHubProvider.list_open_prs + _pr_to_gate refactor`
4. `feat(APP-17): render gate badge per policy in catalog view`

If counts differ, surface in the self-report.

- [ ] **Step 2: Optional smoke against the live PT bundle**

Only if GitHub App credentials AND the PT working copy are available locally:

```bash
cd /Users/chuck/PolicyWonk
export POLICYCODEX_POLICY_REPO_URL="https://github.com/Diocese-of-Pensacola-Tallahassee/pt-policy.git"
export POLICYCODEX_POLICY_BRANCH=main
export POLICYCODEX_WORKING_COPY_ROOT=/tmp/app17-smoke
/Users/chuck/PolicyWonk/spike/venv/bin/python manage.py pull_working_copy
echo "from django.contrib.auth.models import User; User.objects.filter(username='admin').exists() or User.objects.create_user('admin', 'admin@example.com', 'admin')" | /Users/chuck/PolicyWonk/spike/venv/bin/python manage.py shell
/Users/chuck/PolicyWonk/spike/venv/bin/python manage.py runserver &
SERVER_PID=$!
sleep 2
curl -s -c /tmp/c.txt http://127.0.0.1:8000/login/ > /dev/null
CSRF=$(grep csrftoken /tmp/c.txt | awk '{print $7}')
curl -s -X POST http://127.0.0.1:8000/login/ -b /tmp/c.txt -c /tmp/c.txt -d "username=admin&password=admin&csrfmiddlewaretoken=$CSRF" -e http://127.0.0.1:8000/login/ > /dev/null
curl -s http://127.0.0.1:8000/catalog/ -b /tmp/c.txt | grep -E "gate-(drafted|reviewed|published)"
kill $SERVER_PID
```

Expected: at least one `gate-published` badge in the output (the foundational policy and any flat policies merged to main render Published). If a draft PR is open in the PT repo, expect `gate-drafted` or `gate-reviewed` lines too.

If credentials are not available, SKIP and note in the self-report.

- [ ] **Step 3: Compose self-report**

Cover:
- Goal in one sentence.
- Branch name (`worktree-agent-<id>`) and final commit SHA.
- Files created / modified.
- Commit list with messages.
- Test count before / after (expect 180 -> 199).
- `manage.py check` result.
- Smoke result (Step 2): PASS / SKIPPED / FAIL with notes.
- Any deviations from the plan + rationale.
- Status: DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT.

- [ ] **Step 4: Handoff**

Do not merge to main. Do not push. The dispatching session (Scarlet) will route the branch through spec-compliance review and code-quality review per `superpowers:subagent-driven-development`.

---

## Definition of Done

- `app/git_provider/states.py` exists with `slug_to_branch_prefix(slug)` and `branch_to_slug(branch)` as pure functions; module imports cleanly without Django or GitHub deps.
- `app/git_provider/base.py` declares `list_open_prs(working_dir)` as an `@abstractmethod` with a docstring nailing the return shape (`pr_number`, `head_branch`, `gate`, `url`).
- `app/git_provider/github_provider.py` has a module-level `_pr_to_gate(pr)` helper used by BOTH `read_pr_state` and `list_open_prs`; mapping rules are unchanged from APP-04 (merged -> published, closed-not-merged -> closed, open+approval -> reviewed, open+no-approval -> drafted).
- `list_open_prs` makes exactly one `repo.get_pulls(state="open")` call.
- `core/views.py` `catalog` view passes a `rows=[{"policy": ..., "gate": ...}, ...]` context; `gate` defaults to `"published"` when no matching open PR exists.
- `core/views.py` `_build_gate_lookup` catches `Exception` from the provider and returns `{}` so the catalog never 500s on network failure.
- `core/templates/catalog.html` renders the three badges (kind, foundational, gate) in that order on each policy row.
- `core/tests/test_catalog.py` adds 6 new tests (published-default, drafted, reviewed, mixed, ignore-non-convention-branch, degrades-on-RuntimeError); existing 9 Wave-2 tests pass via the `stub_gh_provider` fixture.
- `app/git_provider/tests/test_states.py` adds 7 new tests.
- `app/git_provider/tests/test_base.py` adds 1 new test (`test_subclass_missing_list_open_prs_fails`) and updates the existing 7 `IncompleteProvider` stubs to include a `list_open_prs` stub method.
- `app/git_provider/tests/test_github_provider.py` adds 5 new tests for `list_open_prs`; the existing parametrized `test_read_pr_state_mapping` still passes (7 cases) post-refactor.
- Full repo test suite: 180 -> 199 passing.
- 4 commits on the branch since BASE `5017488`, all with `APP-17` in the message.
- No edits outside the 9 files in **File Structure**.
- No em dashes anywhere in new content.
- No PT-specific tokens (`pt`, `PT`, `pensacola`, `tallahassee`) anywhere in the diff. PT names appear ONLY in the optional smoke env exports in Task 7.

---

## Self-Review

**Spec coverage:**
- Ticket says "PR-state-to-gate mapping: Drafted (open), Reviewed (approved), Published (merged)" → APP-04 already implemented the per-PR mapping inside `read_pr_state`; APP-17 (a) batches it via `list_open_prs`, (b) surfaces it in the catalog UI (per the ticket-row implication: a mapping isn't useful unless a consumer reads it). ✓
- CLAUDE.md "Every gate transition is a pull request state (Drafted = open, Reviewed = approved, Published = merged)" → reflected verbatim in `_pr_to_gate` and in the default-Published-when-no-open-PR behavior. ✓
- Dependency in tickets row: APP-04 (provider methods) + APP-07 (edit form opens PR) → Task 2 captures the same `policycodex/draft-<slug>` convention APP-07 will write to; Task 4 reuses APP-04's mapping logic. ✓
- Performance: one batched API call per catalog render (decision documented in Architecture). ✓
- Graceful degradation: provider failure -> rows render with all-Published; no 500 (Task 5 test `test_catalog_degrades_gracefully_when_list_open_prs_raises`). ✓

**Placeholder scan:** No TBDs, no "TODO", no "implement later". Every step has code. Every test has assertions.

**Type consistency:**
- `list_open_prs` return shape: `list[dict]` with keys `pr_number` (int), `head_branch` (str), `gate` (str), `url` (str) — used identically across the ABC docstring (Task 3), the implementation (Task 4), the GitHubProvider tests (Task 4), and the view code (Task 5).
- Template context variable `rows: list[dict]` with `row.policy` and `row.gate` — used identically across the view (Task 5), the template (Task 6), and the new tests (Task 5).
- Branch-naming convention `policycodex/draft-<slug>` — used identically across `app/git_provider/states.py` (Task 2), the existing APP-04 tests (already in `test_github_provider.py`), and the new `list_open_prs` tests (Task 4).
- Gate values: exactly `"drafted" | "reviewed" | "published" | "closed"` — same vocabulary as APP-04's ABC docstring (`app/git_provider/base.py:100`) and the new Task 3 docstring.

**Potential gotchas (flagged):**
- Task 3 has an unusual RED order: the new IncompleteProvider test passes vacuously until we make `list_open_prs` abstract, at which point the OTHER tests in the file pass for new reasons. The actually-driving RED test is `test_github_provider_is_git_provider` in `test_github_provider.py`. The plan calls this out in Task 3 Step 4 and Step 7.
- Task 6 renames the template context from `policies` to `rows`. The Wave-2 tests that survive use body-text assertions; the rename is a template-only break and is fixed in the same commit.
- `_build_gate_lookup` catches `Exception` (broad) intentionally: any provider failure (network, auth, rate-limit) must not 500 the catalog. A narrower `RuntimeError` would miss `github.GithubException`, `socket.error`, etc. The breadth is justified for a render-time fallback.

No other issues found.
