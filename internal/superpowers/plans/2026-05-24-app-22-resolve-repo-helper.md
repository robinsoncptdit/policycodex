# APP-22 Extract `_resolve_repo` Helper Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the duplicated origin-URL lookup and repo-resolution subprocess/PyGithub boilerplate repeated across `app/git_provider/github_provider.py` by extracting two private helpers, with zero behavior change and zero net change in test count.

**Architecture:** Two new private methods on `GitHubProvider`: `_origin_url(working_dir) -> str` (the `git remote get-url origin` subprocess block, shared by `push`, `pull`, and the repo resolver) and `_resolve_repo(working_dir)` (origin URL → `_parse_owner_repo` → `self._client.get_repo`, shared by the five PR-related methods). This is a refactor performed **under the existing 35-test safety net** for this module — no tests are added or removed.

**Tech Stack:** Python 3.14, `subprocess`, PyGithub, pytest with `unittest.mock`. Interpreter: `ai/venv/bin/python`.

---

## IMPORTANT: ticket-text vs. actual-code discrepancy (read first)

The ticket parenthetical lists "`clone`, `branch`, `commit`, `push`, `pull`," but the code does **not** match that list:

- `clone` has no `git remote get-url` block (it sets origin URL at the end).
- `branch` runs only `git checkout -b`.
- `commit` runs `git add` / `git commit` / `git rev-parse`.

The duplication actually flagged by the three Wave-3 reviewers (and named in the ticket title) is **`_resolve_repo`**: the `git remote get-url origin` + `_parse_owner_repo` + `self._client.get_repo(...)` sequence repeated in the **five PR-related methods** — `open_pr`, `read_pr_state`, `list_open_prs`, `approve_pr`, `merge_pr`. Additionally, `push` and `pull` duplicate just the get-url block (then tokenize the URL rather than resolving a repo).

This plan targets the real duplication: `_resolve_repo` for the five PR methods, plus a lower-level `_origin_url` reused by `push`/`pull` and by `_resolve_repo`. Net effect: the get-url subprocess block appears exactly once, and the get_repo resolution appears exactly once.

## File Structure

- Modify only: `app/git_provider/github_provider.py`.
- No test file changes. The existing `app/git_provider/tests/test_github_provider.py` (35 tests) is the safety net; it asserts on the subprocess call **sequence** (e.g. `first_call[0][0] == ["git", "remote", "get-url", "origin"]`) and on `get_repo.assert_called_once_with(...)`, both of which the helpers preserve exactly.

---

### Task 1: Establish green baseline

- [ ] **Step 1: Run the module's existing tests**

Run: `ai/venv/bin/python -m pytest app/git_provider/tests/test_github_provider.py -q`
Expected: `35 passed`. (If not 35, stop and report — the baseline is wrong.)

- [ ] **Step 2: Confirm the exact get-url failure message to preserve**

The block to extract currently raises, in every method:
```python
raise RuntimeError(
    f"git remote get-url failed (exit {get_url.returncode}): "
    f"{get_url.stderr.decode(errors='replace')}"
)
```
The new helper MUST raise this identical string so any message-asserting test stays green.

---

### Task 2: Add `_origin_url` and `_resolve_repo` helpers (unused yet)

**Files:**
- Modify: `app/git_provider/github_provider.py` (add two methods on `GitHubProvider`, placed right after `_installation_token`, before `clone`)

- [ ] **Step 1: Add the helpers**

Insert after the `_installation_token` method (currently lines 73-74):

```python
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
```

- [ ] **Step 2: Run tests (still green; helpers unused)**

Run: `ai/venv/bin/python -m pytest app/git_provider/tests/test_github_provider.py -q`
Expected: `35 passed`.

- [ ] **Step 3: Commit**

```bash
git add app/git_provider/github_provider.py
git commit -m "refactor(APP-22): add _origin_url and _resolve_repo helpers"
```

---

### Task 3: Migrate the five PR-related methods to `_resolve_repo`

**Files:**
- Modify: `app/git_provider/github_provider.py` (`open_pr`, `read_pr_state`, `list_open_prs`, `approve_pr`, `merge_pr`)

In each of the five methods, replace this block:

```python
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
```

with the single line:

```python
        repo = self._resolve_repo(working_dir)
```

(`owner_repo` is not referenced downstream in any of the five methods — verify with a grep after editing.)

- [ ] **Step 1: Edit `open_pr`** — replace the block, keep the rest (`repo.create_pull(...)` etc.) unchanged.

- [ ] **Step 2: Edit `read_pr_state`** — replace the block, keep `pr = repo.get_pull(pr_number)` / `return _pr_to_gate(pr)`.

- [ ] **Step 3: Edit `list_open_prs`** — replace the block, keep the `for pr in repo.get_pulls(state="open"):` loop.

- [ ] **Step 4: Edit `approve_pr`** — replace the block, keep `pr = repo.get_pull(pr_number)` / `create_review(...)`.

- [ ] **Step 5: Edit `merge_pr`** — replace the block, keep the `merge_method` validation (which stays **above** the resolve call, exactly where it is now) and the `try/except` merge logic.

- [ ] **Step 6: Verify no stray `owner_repo` / `get_url` references remain in those methods**

Run: `grep -n "owner_repo\|get_url" app/git_provider/github_provider.py`
Expected: matches only inside `_origin_url`, `_resolve_repo`, `push`, and `pull` (not in the five PR methods). `_parse_owner_repo` (the module function) still defined and used by `_resolve_repo`.

- [ ] **Step 7: Run tests**

Run: `ai/venv/bin/python -m pytest app/git_provider/tests/test_github_provider.py -q`
Expected: `35 passed`. If a test fails, the most likely cause is a changed subprocess call order or message — re-check against Task 1 Step 2.

- [ ] **Step 8: Commit**

```bash
git add app/git_provider/github_provider.py
git commit -m "refactor(APP-22): route 5 PR methods through _resolve_repo"
```

---

### Task 4: Migrate `push` and `pull` to `_origin_url`

**Files:**
- Modify: `app/git_provider/github_provider.py` (`push`, `pull`)

In both `push` and `pull`, replace this block:

```python
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
```

with:

```python
        origin_url = self._origin_url(working_dir)
```

Keep the following lines that already come next in both methods unchanged:

```python
        if not origin_url.startswith("https://github.com/"):
            raise ValueError(f"Origin is not an https://github.com/ URL: {origin_url}")
        token = self._installation_token()
        tokenized = origin_url.replace(...)
        ...
```

- [ ] **Step 1: Edit `push`** as above.

- [ ] **Step 2: Edit `pull`** as above.

- [ ] **Step 3: Run tests**

Run: `ai/venv/bin/python -m pytest app/git_provider/tests/test_github_provider.py -q`
Expected: `35 passed`. The push/pull tests assert `first_call[0][0] == ["git", "remote", "get-url", "origin"]`; `_origin_url` issues exactly that call first, so they stay green.

- [ ] **Step 4: Commit**

```bash
git add app/git_provider/github_provider.py
git commit -m "refactor(APP-22): route push/pull through _origin_url"
```

---

### Task 5: Full-suite verification + behavior-change audit

- [ ] **Step 1: Run the whole suite**

Run: `ai/venv/bin/python -m pytest -q`
Expected: `322 passed` (unchanged — this is a refactor; net test count is identical).

- [ ] **Step 2: Confirm the duplication is gone**

Run: `grep -c "git\", \"remote\", \"get-url\", \"origin\"" app/git_provider/github_provider.py`
Expected: `1` (the single occurrence inside `_origin_url`).

Run: `grep -c "self._client.get_repo" app/git_provider/github_provider.py`
Expected: `1` (the single occurrence inside `_resolve_repo`).

---

## Self-Review checklist (run before requesting review)

- Behavior unchanged: same subprocess calls, same order, same error messages, same `get_repo` arguments. ✔
- Net test count unchanged: 322 before, 322 after; no test added or removed. ✔
- get-url block now appears once; get_repo resolution appears once. ✔
- Discrepancy between ticket method-list and actual code documented (see top section). ✔
- No placeholders; every edit shows exact before/after. ✔

## Dispatch note

Implementer runs in `isolation: "worktree"`, Sonnet. First action inside the worktree: `git merge main` into the auto-branch. Critical Operational Note applies: never `cd /Users/chuck/PolicyWonk` for git ops; operate only inside the worktree. Two-stage review (spec then quality) before merge. Because this is a behavior-preserving refactor, the quality reviewer should specifically confirm no test was weakened or removed to make the suite pass.
