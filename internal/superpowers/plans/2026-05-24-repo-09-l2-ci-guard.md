# REPO-09 L2 Foundational-Policy CI Guard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A vendorable GitHub Actions check that blocks any pull request whose diff deletes a `foundational: true` policy file or empties a foundational policy's declared `provides:` list, shipped as a generic template in this repo so any diocese can install it.

**Architecture:** A new top-level `repo-template/` directory in the PolicyCodex repo mirrors the layout that gets copied into a diocese's policy repo. It holds `.github/workflows/foundational-guard.yml` (thin glue) plus `.github/scripts/foundational_guard.py` (a standalone, dependency-light guard script). The script splits into a pure, fully-tested core (`parse_frontmatter`, `is_foundational`, `provides_of`, `find_violations`) and a thin git-driven wrapper (`collect_changes`, `main`) verified by integration tests against a real temp git repo. The script is vendored verbatim into the diocese repo on install, so it must NOT import any PolicyCodex package; its only third-party dependency is PyYAML, installed by the workflow. Tests live in `repo-template/tests/` (left behind on install; only `repo-template/.github/` is copied) and load the script by path.

**Tech Stack:** Python 3.12 stdlib + PyYAML, GitHub Actions, pytest.

**Ticket reference:** `PolicyWonk-v0.1-Tickets.md` REPO-09. L2 of the 4-layer model (`internal/PolicyWonk-Foundational-Policy-Design.md` line 139: "Pre-merge CI check: PR diff cannot remove a `foundational: true` file or empty a declared `provides:` capability"). Placement confirmed with Chuck 2026-05-24: generic `repo-template/` dir with a vendored script (precedent for PUBLISH-06's deploy workflow).

**BASE:** `main` at SHA `13746f8`.

**Discipline reminders:**
- TDD: every test observed failing first, before the implementation it covers.
- No em dashes anywhere (code, comments, docstrings, YAML, README, commit messages). Use periods or hyphens.
- Ship-generic: the template is diocese-agnostic. No `pt`, `PT`, `pensacola`, `tallahassee` tokens anywhere in `repo-template/` or its tests. The script keys off `foundational: true` frontmatter, never a hardcoded path or diocese.
- `>=` floor pins, not exact pins: the workflow installs `"pyyaml>=6.0"`.
- The guard script is STANDALONE. Do not `import` from `ingest`, `app`, `core`, or any PolicyCodex module. Duplicating the minimal frontmatter splitter is intentional and correct (the policy repo cannot depend on our package).
- Do not touch `core/`, `app/`, `ingest/`, `ai/`, `handbook/`, or `policycodex_site/`. This ticket only adds files under `repo-template/`.
- Pin GitHub Action versions to major tags (`actions/checkout@v4`, `actions/setup-python@v5`).

---

## File Structure

- Create: `repo-template/.github/scripts/foundational_guard.py` - the standalone guard script.
- Create: `repo-template/.github/workflows/foundational-guard.yml` - the workflow that runs the script on `pull_request`.
- Create: `repo-template/tests/test_foundational_guard.py` - pytest unit + integration tests (loads the script by path).
- Create: `repo-template/README.md` - generic install instructions for a diocese.

No existing files are modified. `pytest.ini` already discovers `test_*.py` anywhere in the repo, so no test-config change is needed.

---

## Task 1: Worktree pre-flight

**Files:** none modified.

- [ ] **Step 1: Confirm worktree state**

Run:
```bash
git rev-parse HEAD
git branch --show-current
git status --short
```
Expected: BASE SHA `13746f8` or a descendant; branch is your auto-worktree branch; status clean.

- [ ] **Step 2: Merge `main` into your worktree branch**

Run:
```bash
git fetch
git merge main --no-edit
```
Expected: "Already up to date." or a clean fast-forward.

- [ ] **Step 3: Confirm the test interpreter and baseline suite**

The repo has no root venv; the interpreter with pytest + PyYAML is `ai/venv/bin/python`. Run:
```bash
/Users/chuck/PolicyWonk/ai/venv/bin/python -m pytest -q
```
Expected: full suite passes (270 on BASE). Use this interpreter for every test run in this plan. If anything fails before you change a thing, STOP and report.

---

## Task 2: Frontmatter parsing helpers (standalone script core)

**Files:**
- Create: `repo-template/.github/scripts/foundational_guard.py`
- Create: `repo-template/tests/test_foundational_guard.py`

- [ ] **Step 1: Write the failing tests**

Create `repo-template/tests/test_foundational_guard.py`:

```python
"""Tests for the vendored foundational-policy CI guard.

The guard script lives at repo-template/.github/scripts/foundational_guard.py
and is copied verbatim into a diocese policy repo, so it must stay
standalone. We load it by path here rather than importing a package.
"""
import importlib.util
from pathlib import Path

_SCRIPT = (
    Path(__file__).resolve().parents[1] / ".github" / "scripts" / "foundational_guard.py"
)


def _load_guard():
    spec = importlib.util.spec_from_file_location("foundational_guard", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


guard = _load_guard()


def test_parse_frontmatter_reads_mapping():
    text = "---\nfoundational: true\nprovides:\n  - classifications\n---\nbody\n"
    fm = guard.parse_frontmatter(text)
    assert fm["foundational"] is True
    assert fm["provides"] == ["classifications"]


def test_parse_frontmatter_none_returns_empty():
    assert guard.parse_frontmatter(None) == {}


def test_parse_frontmatter_no_block_returns_empty():
    assert guard.parse_frontmatter("# just a heading\n") == {}


def test_is_foundational_and_provides_of():
    assert guard.is_foundational({"foundational": True}) is True
    assert guard.is_foundational({"foundational": False}) is False
    assert guard.is_foundational({}) is False
    assert guard.provides_of({"provides": ["a", "b"]}) == ["a", "b"]
    assert guard.provides_of({"provides": None}) == []
    assert guard.provides_of({}) == []
```

- [ ] **Step 2: Run to verify failure**

Run:
```bash
/Users/chuck/PolicyWonk/ai/venv/bin/python -m pytest repo-template/tests/test_foundational_guard.py -q
```
Expected: FAIL at import/collection (the script file does not exist yet).

- [ ] **Step 3: Create the script with the parsing helpers**

Create `repo-template/.github/scripts/foundational_guard.py`:

```python
#!/usr/bin/env python3
"""Foundational-policy CI guard (L2 protection layer).

Blocks a pull request whose diff either:
  (a) deletes a policy file that declares `foundational: true` in its
      YAML frontmatter, or
  (b) empties the `provides:` capability list of a still-foundational
      policy file.

Runs as a GitHub Actions check inside a diocese policy repo. It is
vendored into that repo (copied from the PolicyCodex `repo-template/`), so
it stays dependency-light and self-contained: it does NOT import any
PolicyCodex package. The only third-party dependency is PyYAML, installed
by the workflow.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass

import yaml

_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def parse_frontmatter(text):
    """Return a markdown document's YAML frontmatter as a dict.

    Returns {} when text is None, has no frontmatter block, or the block
    is not a YAML mapping. The guard fails open on unparseable frontmatter
    rather than crashing the CI run; the app's L3 startup check is the
    backstop for invalid bundles.
    """
    if not text:
        return {}
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}
    try:
        fm = yaml.safe_load(m.group(1))
    except yaml.YAMLError:
        return {}
    return fm if isinstance(fm, dict) else {}


def is_foundational(fm):
    return bool(fm.get("foundational"))


def provides_of(fm):
    value = fm.get("provides")
    return value if isinstance(value, list) else []
```

- [ ] **Step 4: Run to verify pass**

Run:
```bash
/Users/chuck/PolicyWonk/ai/venv/bin/python -m pytest repo-template/tests/test_foundational_guard.py -q
```
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add repo-template/.github/scripts/foundational_guard.py repo-template/tests/test_foundational_guard.py
git commit -m "feat(REPO-09): foundational-guard frontmatter parsing helpers"
```

---

## Task 3: Violation detection (pure core)

**Files:**
- Modify: `repo-template/.github/scripts/foundational_guard.py`
- Modify: `repo-template/tests/test_foundational_guard.py`

- [ ] **Step 1: Write the failing tests**

Append to `repo-template/tests/test_foundational_guard.py`:

```python
def _change(path, change_type, base_fm=None, head_fm=None):
    return guard.Change(
        path=path,
        change_type=change_type,
        base_frontmatter=base_fm or {},
        head_frontmatter=head_fm or {},
    )


def test_deleting_foundational_file_is_a_violation():
    changes = [_change("policies/document-retention/policy.md", "deleted",
                       base_fm={"foundational": True, "provides": ["classifications"]})]
    assert len(guard.find_violations(changes)) == 1


def test_deleting_non_foundational_file_is_allowed():
    changes = [_change("policies/code-of-conduct.md", "deleted",
                       base_fm={"title": "Code of Conduct"})]
    assert guard.find_violations(changes) == []


def test_emptying_provides_is_a_violation():
    changes = [_change("policies/document-retention/policy.md", "modified",
                       base_fm={"foundational": True, "provides": ["classifications", "retention-schedule"]},
                       head_fm={"foundational": True, "provides": []})]
    assert len(guard.find_violations(changes)) == 1


def test_removing_provides_key_is_a_violation():
    changes = [_change("policies/document-retention/policy.md", "modified",
                       base_fm={"foundational": True, "provides": ["classifications"]},
                       head_fm={"foundational": True})]
    assert len(guard.find_violations(changes)) == 1


def test_modifying_foundational_without_touching_provides_is_allowed():
    changes = [_change("policies/document-retention/policy.md", "modified",
                       base_fm={"foundational": True, "provides": ["classifications"]},
                       head_fm={"foundational": True, "provides": ["classifications"]})]
    assert guard.find_violations(changes) == []


def test_adding_foundational_file_is_allowed():
    changes = [_change("policies/new-foundation/policy.md", "added",
                       head_fm={"foundational": True, "provides": ["classifications"]})]
    assert guard.find_violations(changes) == []


def test_renaming_foundational_file_is_allowed():
    changes = [_change("policies/renamed/policy.md", "renamed",
                       base_fm={"foundational": True, "provides": ["classifications"]},
                       head_fm={"foundational": True, "provides": ["classifications"]})]
    assert guard.find_violations(changes) == []


def test_modifying_non_foundational_is_allowed():
    changes = [_change("policies/code-of-conduct.md", "modified",
                       base_fm={"title": "x"}, head_fm={"title": "y"})]
    assert guard.find_violations(changes) == []


def test_multiple_violations_aggregate():
    changes = [
        _change("policies/a/policy.md", "deleted",
                base_fm={"foundational": True, "provides": ["x"]}),
        _change("policies/b/policy.md", "modified",
                base_fm={"foundational": True, "provides": ["y"]},
                head_fm={"foundational": True, "provides": []}),
    ]
    assert len(guard.find_violations(changes)) == 2
```

- [ ] **Step 2: Run to verify failure**

Run:
```bash
/Users/chuck/PolicyWonk/ai/venv/bin/python -m pytest repo-template/tests/test_foundational_guard.py -q
```
Expected: FAIL with `AttributeError: module ... has no attribute 'Change'` (and `find_violations`).

- [ ] **Step 3: Add the Change dataclass and find_violations**

Append to `repo-template/.github/scripts/foundational_guard.py`:

```python
@dataclass(frozen=True)
class Change:
    path: str
    change_type: str  # "added" | "modified" | "deleted" | "renamed"
    base_frontmatter: dict
    head_frontmatter: dict


def find_violations(changes):
    """Return human-readable violation messages for a list of Change. Empty = OK."""
    violations = []
    for ch in changes:
        if ch.change_type == "deleted" and is_foundational(ch.base_frontmatter):
            violations.append(
                f"PR deletes foundational policy file: {ch.path}. Foundational "
                f"policies supply app configuration and cannot be deleted through "
                f"a PR. Soft-deprecate the affected entries instead."
            )
        elif ch.change_type == "modified" and is_foundational(ch.base_frontmatter):
            if provides_of(ch.base_frontmatter) and not provides_of(ch.head_frontmatter):
                violations.append(
                    f"PR empties the 'provides:' list of foundational policy: "
                    f"{ch.path}. Removing a declared capability breaks dependents."
                )
    return violations
```

- [ ] **Step 4: Run to verify pass**

Run:
```bash
/Users/chuck/PolicyWonk/ai/venv/bin/python -m pytest repo-template/tests/test_foundational_guard.py -q
```
Expected: 13 passed.

- [ ] **Step 5: Commit**

```bash
git add repo-template/.github/scripts/foundational_guard.py repo-template/tests/test_foundational_guard.py
git commit -m "feat(REPO-09): foundational-guard violation detection"
```

---

## Task 4: Git wiring + main (integration-tested)

**Files:**
- Modify: `repo-template/.github/scripts/foundational_guard.py`
- Modify: `repo-template/tests/test_foundational_guard.py`

- [ ] **Step 1: Write the failing integration tests**

Append to `repo-template/tests/test_foundational_guard.py`:

```python
import subprocess


def _run(cmd, cwd):
    subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True)


def _init_repo(tmp_path):
    _run(["git", "init", "-b", "main"], tmp_path)
    _run(["git", "config", "user.email", "t@example.com"], tmp_path)
    _run(["git", "config", "user.name", "Test"], tmp_path)
    return tmp_path


def _commit_all(tmp_path, msg):
    _run(["git", "add", "-A"], tmp_path)
    _run(["git", "commit", "-m", msg], tmp_path)
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp_path,
                          check=True, capture_output=True, text=True).stdout.strip()


_FOUNDATIONAL_MD = (
    "---\nfoundational: true\nprovides:\n  - classifications\n---\n"
    "Retention policy body.\n"
)


def test_integration_deleting_foundational_blocks(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path)
    bundle = repo / "policies" / "document-retention"
    bundle.mkdir(parents=True)
    (bundle / "policy.md").write_text(_FOUNDATIONAL_MD, encoding="utf-8")
    base = _commit_all(repo, "add foundational policy")
    (bundle / "policy.md").unlink()
    head = _commit_all(repo, "delete foundational policy")

    monkeypatch.chdir(repo)
    monkeypatch.setenv("BASE_SHA", base)
    monkeypatch.setenv("HEAD_SHA", head)
    assert guard.main() == 1


def test_integration_deleting_ordinary_policy_passes(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path)
    (repo / "policies").mkdir()
    (repo / "policies" / "code-of-conduct.md").write_text(
        "---\ntitle: Code of Conduct\n---\nBody.\n", encoding="utf-8")
    base = _commit_all(repo, "add ordinary policy")
    (repo / "policies" / "code-of-conduct.md").unlink()
    head = _commit_all(repo, "delete ordinary policy")

    monkeypatch.chdir(repo)
    monkeypatch.setenv("BASE_SHA", base)
    monkeypatch.setenv("HEAD_SHA", head)
    assert guard.main() == 0


def test_integration_emptying_provides_blocks(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path)
    bundle = repo / "policies" / "document-retention"
    bundle.mkdir(parents=True)
    (bundle / "policy.md").write_text(_FOUNDATIONAL_MD, encoding="utf-8")
    base = _commit_all(repo, "add foundational policy")
    (bundle / "policy.md").write_text(
        "---\nfoundational: true\nprovides: []\n---\nRetention policy body.\n",
        encoding="utf-8")
    head = _commit_all(repo, "empty provides")

    monkeypatch.chdir(repo)
    monkeypatch.setenv("BASE_SHA", base)
    monkeypatch.setenv("HEAD_SHA", head)
    assert guard.main() == 1


def test_integration_missing_env_returns_2(monkeypatch):
    monkeypatch.delenv("BASE_SHA", raising=False)
    monkeypatch.delenv("HEAD_SHA", raising=False)
    assert guard.main() == 2
```

- [ ] **Step 2: Run to verify failure**

Run:
```bash
/Users/chuck/PolicyWonk/ai/venv/bin/python -m pytest repo-template/tests/test_foundational_guard.py -q
```
Expected: FAIL with `AttributeError: module ... has no attribute 'main'`.

- [ ] **Step 3: Add the git wiring and main**

Append to `repo-template/.github/scripts/foundational_guard.py`:

```python
def _show(ref, path):
    """Return file content at ref:path, or None if it does not exist there."""
    try:
        return subprocess.run(
            ["git", "show", f"{ref}:{path}"],
            check=True, capture_output=True, text=True,
        ).stdout
    except subprocess.CalledProcessError:
        return None


_STATUS = {"A": "added", "M": "modified", "D": "deleted", "R": "renamed"}


def collect_changes(base_sha, head_sha):
    """Build the Change list for every changed markdown file in base..head."""
    diff = subprocess.run(
        ["git", "diff", "--name-status", "-M", base_sha, head_sha],
        check=True, capture_output=True, text=True,
    ).stdout
    changes = []
    for line in diff.splitlines():
        parts = line.split("\t")
        code = parts[0][0]  # first char: A / M / D / R
        change_type = _STATUS.get(code, "modified")
        old_path = parts[1]
        new_path = parts[-1]  # same as old_path except for renames
        if not new_path.endswith(".md"):
            continue
        base_text = None if code == "A" else _show(base_sha, old_path)
        head_text = None if code == "D" else _show(head_sha, new_path)
        changes.append(Change(
            path=new_path,
            change_type=change_type,
            base_frontmatter=parse_frontmatter(base_text),
            head_frontmatter=parse_frontmatter(head_text),
        ))
    return changes


def main():
    base = os.environ.get("BASE_SHA")
    head = os.environ.get("HEAD_SHA")
    if not base or not head:
        print("foundational-guard: BASE_SHA and HEAD_SHA must be set.", file=sys.stderr)
        return 2
    violations = find_violations(collect_changes(base, head))
    if violations:
        print("Foundational-policy guard FAILED:", file=sys.stderr)
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        return 1
    print("Foundational-policy guard passed: no protected deletions or emptied capabilities.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run to verify pass**

Run:
```bash
/Users/chuck/PolicyWonk/ai/venv/bin/python -m pytest repo-template/tests/test_foundational_guard.py -q
```
Expected: 17 passed.

- [ ] **Step 5: Commit**

```bash
git add repo-template/.github/scripts/foundational_guard.py repo-template/tests/test_foundational_guard.py
git commit -m "feat(REPO-09): git diff wiring + main entrypoint for foundational-guard"
```

---

## Task 5: Workflow YAML + generic install README

**Files:**
- Create: `repo-template/.github/workflows/foundational-guard.yml`
- Create: `repo-template/README.md`

- [ ] **Step 1: Create the workflow**

Create `repo-template/.github/workflows/foundational-guard.yml`:

```yaml
name: Foundational policy guard

on:
  pull_request:
    branches: [main]
    paths:
      - 'policies/**'

jobs:
  foundational-guard:
    runs-on: ubuntu-latest
    steps:
      - name: Check out the pull request
        uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Install dependencies
        run: pip install "pyyaml>=6.0"
      - name: Run the foundational-policy guard
        env:
          BASE_SHA: ${{ github.event.pull_request.base.sha }}
          HEAD_SHA: ${{ github.event.pull_request.head.sha }}
        run: python .github/scripts/foundational_guard.py
```

- [ ] **Step 2: Create the generic install README**

Create `repo-template/README.md`:

```markdown
# Diocese policy-repo template

These files are copied into a diocese's private policy repository to add
PolicyCodex's repo-side automation. They are generic: nothing here names a
specific diocese.

## What is here

- `.github/workflows/foundational-guard.yml` - the L2 protection layer. On
  every pull request that touches `policies/`, it blocks the merge if the
  diff deletes a foundational policy file (one with `foundational: true` in
  its frontmatter) or empties a foundational policy's `provides:` list.
- `.github/scripts/foundational_guard.py` - the standalone script the
  workflow runs. It depends only on PyYAML.

## Install into a policy repo

1. Copy the contents of `repo-template/.github/` into the policy repo's
   `.github/` directory and open a PR.
2. After it merges, add the `foundational-guard` check to the policy repo's
   `main` branch protection as a required status check (Settings -> Rules,
   or the repo ruleset). This makes the guard blocking rather than advisory.

## Tests

The script's tests live in `repo-template/tests/` in the PolicyCodex repo
and run as part of the PolicyCodex suite. They are not copied into the
policy repo.
```

- [ ] **Step 3: Lint the workflow YAML parses**

Run:
```bash
/Users/chuck/PolicyWonk/ai/venv/bin/python -c "import yaml; yaml.safe_load(open('repo-template/.github/workflows/foundational-guard.yml')); print('workflow YAML OK')"
```
Expected: `workflow YAML OK`.

- [ ] **Step 4: Commit**

```bash
git add repo-template/.github/workflows/foundational-guard.yml repo-template/README.md
git commit -m "feat(REPO-09): foundational-guard workflow + generic install README"
```

---

## Task 6: Full-suite verification

**Files:** none modified.

- [ ] **Step 1: Run the new tests verbosely**

Run:
```bash
/Users/chuck/PolicyWonk/ai/venv/bin/python -m pytest repo-template/tests/test_foundational_guard.py -v
```
Expected: 17 passed.

- [ ] **Step 2: Run the entire repo suite**

Run:
```bash
/Users/chuck/PolicyWonk/ai/venv/bin/python -m pytest -q
```
Expected: full suite PASS. Baseline is 270 on BASE; this ticket adds 17 tests, so expect 287 passing and no other count changes. Report the exact observed number per superpowers:verification-before-completion. If any pre-existing test regresses, STOP and report.

- [ ] **Step 3: Confirm scope and banned tokens**

Run:
```bash
git diff main --stat
grep -rniE "pensacola|tallahassee|[^a-z]pt[^a-z]" repo-template/ || echo "clean: no diocese tokens"
grep -rn "—" repo-template/ || echo "clean: no em dashes"
```
Expected: `--stat` shows only files under `repo-template/`; both grep guards print their "clean" line.

---

## Out of Scope (deploy step, handled separately by the project lead)

- **Installing the guard into PT's `pt-policy` repo** and adding `foundational-guard` as a required status check on its `main` ruleset is a deploy action, not part of this code plan. It is the GitHub-settings analog of REPO-08 (Chuck owns the settings change; Scarlet copies `repo-template/.github/` into `pt-policy` via a PR). Track it as a short REPO-09 install note in `internal/` at deploy time. For v0.1 PT the action is hand-installed once.
- **`act`/live-PR end-to-end testing** of the workflow YAML itself. The script is integration-tested against a real temp git repo; the workflow is thin glue verified on first real PR. Do not add `act` to the toolchain for v0.1.
- **Guarding `data.yaml` deletion** (a bundle's machine-readable sidecar has no frontmatter, so it is outside REPO-09's "file declaring `foundational: true`" scope). L3 (APP-21 startup self-check) is the backstop for a bundle left invalid by a deleted `data.yaml`. Note as a possible REPO-09 follow-up if real dioceses hit it.

---

## Self-Review (run by the author after drafting)

1. **Spec coverage.** The two L2 requirements from the design doc are both covered: deleting a `foundational: true` file (Task 3 `find_violations` deleted branch; Task 4 integration test `test_integration_deleting_foundational_blocks`) and emptying a declared `provides:` (Task 3 emptied/removed-key tests; Task 4 `test_integration_emptying_provides_blocks`). Generic placement per Chuck's 2026-05-24 decision (Task 2-5 all under `repo-template/`). The diocese install + required-check wiring is explicitly deferred to deploy (Out of Scope).
2. **Placeholder scan.** Every code and YAML step contains complete content; every command has an expected result. No TBD / "handle edge cases" / "similar to".
3. **Type/string consistency.** `Change` fields (`path`, `change_type`, `base_frontmatter`, `head_frontmatter`) are identical across the dataclass (Task 3), the `_change` test helper (Task 3), and `collect_changes` (Task 4). `change_type` string values (`"added"/"modified"/"deleted"/"renamed"`) match between `_STATUS` (Task 4) and every test. The workflow's job name `foundational-guard` matches the required-check name in the README and the deploy note. The script path `repo-template/.github/scripts/foundational_guard.py` matches the test's `parents[1] / ".github" / "scripts"` resolution (test at `repo-template/tests/` -> `parents[1]` is `repo-template/`). The workflow runs `python .github/scripts/foundational_guard.py`, which is correct relative to the policy repo root after install.
