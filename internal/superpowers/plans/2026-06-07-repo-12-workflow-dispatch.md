# REPO-12: Manual `workflow_dispatch:` Trigger on Shipped Workflows — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `workflow_dispatch:` trigger to both shipped `repo-template` workflows so a maintainer can manually re-fire a run (`gh workflow run ... --ref main`) without a path-touching dummy commit.

**Architecture:** Both workflows currently only fire on `push`/`pull_request` events gated by `paths:` filters that do not match `.github/`-only changes. Adding the eventless `workflow_dispatch:` key to each `on:` block makes the workflows manually runnable from the Actions tab or `gh` CLI. No job logic changes. Template structural tests are extended to assert the trigger is present, and the HOWTO gains a one-line manual-rerun pointer.

**Tech Stack:** GitHub Actions YAML, PyYAML (parses bare `on:` as the Python boolean `True`, and a valueless `workflow_dispatch:` as `None`), pytest.

**Test interpreter:** Run the suite as the controller with `ai/venv/bin/python -m pytest` (no root venv exists; system python lacks pytest).

---

### Background (read before starting)

The two shipped workflows live under `repo-template/.github/workflows/` and are vendored verbatim into a diocese's policy repo at install:

- `build-handbook.yml` — fires on `push` to `main` with `paths: ['policies/**', 'handbook/**']`.
- `foundational-guard.yml` — fires on `pull_request` to `main` with `paths: ['policies/**']`.

Neither path filter matches a `.github/`-only change, so a fix-forward PR that edits a workflow itself never re-fires the build. This gap was hit twice during installs (Node-24 PR #4 on 2026-05-24, and PUBLISH-07's preflight fix PR #6→#7 on 2026-05-26); each time a throwaway one-line `handbook/README.md` HTML-comment touch was needed to nudge the trigger. `workflow_dispatch:` removes the need for that hack.

**PyYAML parsing note (already relied on by existing tests):** `yaml.safe_load` parses the bare key `on:` as the Python boolean `True`, so existing tests read the triggers via `wf.get("on", wf.get(True))`. A valueless `workflow_dispatch:` line parses to a key whose value is `None`. Both facts matter for the test assertions below.

**Scope guard:** Only the two `repo-template` workflows are in scope. Do NOT touch `.github/workflows/claude.yml` or `.github/workflows/claude-code-review.yml` — those are dev-time tooling, not shipped product.

---

## File Structure

- `repo-template/.github/workflows/build-handbook.yml` — add `workflow_dispatch:` to `on:`.
- `repo-template/.github/workflows/foundational-guard.yml` — add `workflow_dispatch:` to `on:`.
- `repo-template/tests/test_build_handbook.py` — add a test asserting `workflow_dispatch` is a declared trigger.
- `repo-template/tests/test_foundational_guard.py` — add a workflow-YAML structural test asserting both `pull_request` and `workflow_dispatch` triggers are declared (this file currently has no workflow-YAML test at all; add the import + path constant).
- `HOWTO-GitHub-Team-Setup.md` — add a one-line manual-rerun pointer in Part 4, Step 4.

---

### Task 1: Add `workflow_dispatch:` to `build-handbook.yml` (test-first)

**Files:**
- Modify: `repo-template/.github/workflows/build-handbook.yml:3-8`
- Test: `repo-template/tests/test_build_handbook.py`

- [ ] **Step 1: Write the failing test**

Add this test function to the end of `repo-template/tests/test_build_handbook.py`:

```python
def test_workflow_allows_manual_dispatch():
    # REPO-12: `.github/`-only changes do not match the push path filter, so a
    # workflow-only fix-forward cannot re-fire the build via a commit. The
    # manual trigger lets a maintainer run `gh workflow run build-handbook.yml
    # --ref main` instead of a throwaway path-touching commit.
    wf = yaml.safe_load(WORKFLOW.read_text())
    # PyYAML parses the bare `on:` key as boolean True.
    on = wf.get("on", wf.get(True))
    assert "workflow_dispatch" in on
```

- [ ] **Step 2: Run test to verify it fails**

Run: `ai/venv/bin/python -m pytest repo-template/tests/test_build_handbook.py::test_workflow_allows_manual_dispatch -v`
Expected: FAIL with `assert 'workflow_dispatch' in on` (KeyError-free assertion failure — `on` has only `push`).

- [ ] **Step 3: Add the trigger to the workflow**

In `repo-template/.github/workflows/build-handbook.yml`, change the `on:` block from:

```yaml
on:
  push:
    branches: [main]
    paths:
      - 'policies/**'
      - 'handbook/**'
```

to:

```yaml
on:
  push:
    branches: [main]
    paths:
      - 'policies/**'
      - 'handbook/**'
  # REPO-12: `.github/`-only changes (e.g. a fix-forward to this workflow) do
  # not match the path filter above, so they cannot re-fire the build via a
  # commit. This lets a maintainer re-run manually:
  #   gh workflow run build-handbook.yml --ref main
  workflow_dispatch:
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `ai/venv/bin/python -m pytest repo-template/tests/test_build_handbook.py -v`
Expected: PASS — the new test plus all pre-existing `build-handbook` tests stay green (the existing `test_workflow_exists_and_triggers_on_push_to_main` still reads `on["push"]` correctly since `push` is untouched).

- [ ] **Step 5: Commit**

```bash
git add repo-template/.github/workflows/build-handbook.yml repo-template/tests/test_build_handbook.py
git commit -m "feat(repo-12): add workflow_dispatch trigger to build-handbook.yml

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 2: Add `workflow_dispatch:` to `foundational-guard.yml` (test-first)

**Files:**
- Modify: `repo-template/.github/workflows/foundational-guard.yml:3-7`
- Test: `repo-template/tests/test_foundational_guard.py`

Note: `test_foundational_guard.py` currently tests only the guard *script* and has no workflow-YAML test. This task adds the first one, so it also adds a `yaml` import and a `WORKFLOW` path constant.

- [ ] **Step 1: Add the imports/constant and the failing test**

At the top of `repo-template/tests/test_foundational_guard.py`, add `import yaml` alongside the existing imports, and add a workflow path constant near the `_SCRIPT` constant:

```python
import yaml
```

```python
_WORKFLOW = (
    Path(__file__).resolve().parents[1] / ".github" / "workflows" / "foundational-guard.yml"
)
```

Then add this test function at the end of the file:

```python
def test_workflow_triggers_on_pull_request_and_manual_dispatch():
    # The guard still fires on PRs touching policies/**, and REPO-12 adds a
    # manual trigger so a maintainer can re-run it after a workflow-only
    # fix-forward that the path filter would otherwise miss:
    #   gh workflow run foundational-guard.yml --ref main
    wf = yaml.safe_load(_WORKFLOW.read_text())
    # PyYAML parses the bare `on:` key as boolean True.
    on = wf.get("on", wf.get(True))
    assert on["pull_request"]["branches"] == ["main"]
    assert "policies/**" in on["pull_request"]["paths"]
    assert "workflow_dispatch" in on
```

- [ ] **Step 2: Run test to verify it fails**

Run: `ai/venv/bin/python -m pytest repo-template/tests/test_foundational_guard.py::test_workflow_triggers_on_pull_request_and_manual_dispatch -v`
Expected: FAIL with `assert 'workflow_dispatch' in on` (the `pull_request` assertions pass; only the dispatch key is missing).

- [ ] **Step 3: Add the trigger to the workflow**

In `repo-template/.github/workflows/foundational-guard.yml`, change the `on:` block from:

```yaml
on:
  pull_request:
    branches: [main]
    paths:
      - 'policies/**'
```

to:

```yaml
on:
  pull_request:
    branches: [main]
    paths:
      - 'policies/**'
  # REPO-12: lets a maintainer re-run the guard manually after a
  # workflow-only fix-forward that the path filter above would miss:
  #   gh workflow run foundational-guard.yml --ref main
  workflow_dispatch:
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `ai/venv/bin/python -m pytest repo-template/tests/test_foundational_guard.py -v`
Expected: PASS — the new workflow-YAML test plus all pre-existing guard-script tests stay green.

- [ ] **Step 5: Commit**

```bash
git add repo-template/.github/workflows/foundational-guard.yml repo-template/tests/test_foundational_guard.py
git commit -m "feat(repo-12): add workflow_dispatch trigger to foundational-guard.yml

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 3: Document the manual re-run in the HOWTO

**Files:**
- Modify: `HOWTO-GitHub-Team-Setup.md:109`

No test (docs change). This is a prose pointer so an installer knows the manual-rerun command exists after a workflow-only edit.

- [ ] **Step 1: Add the pointer to Part 4, Step 4**

In `HOWTO-GitHub-Team-Setup.md`, find Step 4 of Part 4 (the line beginning `4. **Trigger a deploy.** Push any commit to`). Append one sentence to the end of that paragraph (after "Visit it and confirm the handbook loads."):

```
To re-run manually later (for example after a workflow-only change under `.github/` that the path filter does not catch), run `gh workflow run build-handbook.yml --ref main`, or use **Run workflow** on the **Build handbook** page of the Actions tab.
```

- [ ] **Step 2: Verify the edit reads cleanly**

Run: `grep -n "gh workflow run build-handbook.yml --ref main" HOWTO-GitHub-Team-Setup.md`
Expected: one match, inside Part 4 Step 4.

- [ ] **Step 3: Commit**

```bash
git add HOWTO-GitHub-Team-Setup.md
git commit -m "docs(repo-12): document manual workflow re-run after workflow-only changes

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 4: Full-suite verification and ticket close-out

**Files:** none (verification + bookkeeping).

- [ ] **Step 1: Run the full suite**

Run: `ai/venv/bin/python -m pytest -q`
Expected: PASS — suite count rises from 493 by 2 (the two new tests) to 495, zero failures.

- [ ] **Step 2: Confirm both workflows still parse as valid YAML**

Run:
```bash
ai/venv/bin/python -c "import yaml; [yaml.safe_load(open(p)) for p in ['repo-template/.github/workflows/build-handbook.yml','repo-template/.github/workflows/foundational-guard.yml']]; print('both parse OK')"
```
Expected: `both parse OK`.

- [ ] **Step 3: Mark REPO-12 done in the tickets board**

In `PolicyWonk-v0.1-Tickets.md`, update the REPO-12 row status to resolved with the date `2026-06-07` and the new suite count (495). Match the close-out style of the surrounding resolved rows.

- [ ] **Step 4: Append a Daily Log entry**

In `internal/PolicyWonk-Daily-Log.md`, append a dated entry recording REPO-12 resolution: `workflow_dispatch:` added to both shipped workflows, two template tests added, HOWTO Part 4 pointer added, suite 493→495.

- [ ] **Step 5: Commit the bookkeeping**

```bash
git add PolicyWonk-v0.1-Tickets.md internal/PolicyWonk-Daily-Log.md
git commit -m "docs(repo-12): mark REPO-12 done, log workflow_dispatch addition

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Self-Review

**1. Spec coverage (ticket scope vs. tasks):**
- "Add the trigger to both workflows in `repo-template/.github/workflows/`" → Task 1 (build-handbook), Task 2 (foundational-guard). ✔
- "Extend the template tests (`test_build_handbook.py` and the foundational-guard equivalent) to assert the trigger is present" → Task 1 Step 1, Task 2 Step 1. ✔ (Note: the foundational-guard test file had no workflow-YAML test, so Task 2 adds the import + path constant as well.)
- "Update `HOWTO-GitHub-Team-Setup.md` with a one-line manual re-run pointer" → Task 3. ✔

**2. Placeholder scan:** No TBD/TODO/"handle edge cases"/"similar to Task N". All code and prose shown in full. ✔

**3. Type/name consistency:** `WORKFLOW` is the existing constant name in `test_build_handbook.py`; Task 2 deliberately uses `_WORKFLOW` to match that file's underscore-prefixed `_SCRIPT` constant convention. The `wf.get("on", wf.get(True))` idiom matches the existing tests in both files. The `gh workflow run <file> --ref main` form matches the ticket's stated command. ✔
