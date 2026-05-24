# AI-12-revised: Retention Bundle Read Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Source the AI extraction's taxonomy from the diocese's foundational-policy bundle (`data.yaml`) in the local working copy when one is available, falling back to the seed taxonomy otherwise, so a CFO edit to the retention bundle flows into the next extraction (the live-sync loop).

**Architecture:** A new Django-free helper `ai/taxonomy_loader.py` uses INGEST-07's `BundleAwarePolicyReader` to find the foundational policy whose `provides:` covers the required capabilities and load its `data.yaml`. It is dependency-light (PyYAML only) so both the standalone spike and the future app extraction can call it: the app passes the `working_dir` from `load_working_copy_config()`, while `spike/extract.py` resolves the working-copy `policies/` dir from the `POLICYCODEX_POLICIES_DIR` env var and falls back to the seed when unset or unmatched. The prompt-rendering (`_build_taxonomy_section`) is unchanged, so with no working copy configured the rendered prompt is byte-identical to today (no eval drift).

**Tech Stack:** Python 3.12+ stdlib + PyYAML, pytest. No Django in the new code path.

**Ticket reference:** `PolicyWonk-v0.1-Tickets.md` AI-12. Sourcing approach confirmed with Chuck 2026-05-24: Django-free loader + seed fallback (keeps the spike standalone; the app reuses the same helper). The AI-12-revised eval-drift risk was pre-closed 2026-05-24 (PT `data.yaml` payload is identical to the seed; recorded in the Week-4 sprint plan).

**BASE:** `main` at SHA `70687cd`.

**Discipline reminders:**
- TDD: every test observed failing first.
- No em dashes anywhere (code, comments, docstrings, commit messages). Use periods or hyphens.
- Capability names in `provides:` use HYPHENS (`classifications`, `retention-schedule`). The `data.yaml` top-level keys use UNDERSCORES (`classifications`, `retention_schedule`). Do not conflate them: the loader matches on `provides` (hyphen); `_build_taxonomy_section` reads `taxonomy["retention_schedule"]` (underscore).
- Do NOT change the prompt text (`_build_taxonomy_section`, `EXTRACTION_PROMPT`). Genericizing the hardcoded "Diocese of Pensacola-Tallahassee" header is REPO-10's job; changing prompt bytes here risks eval drift. This ticket only changes WHERE the taxonomy dict comes from.
- `BundleAwarePolicyReader` is Django-free (PyYAML only); import it freely. Do NOT import `app.working_copy.config` (Django-bound) into `spike/extract.py` or `ai/taxonomy_loader.py`.
- Ship-generic: find the foundational bundle by CAPABILITY (`provides`), never by a hardcoded slug like "document-retention".
- Use `/Users/chuck/PolicyWonk/ai/venv/bin/python` for every test run (no root venv; system python lacks pytest).
- Do not touch `core/`, `app/`, `handbook/`, `policycodex_site/`, or the eval JSONLs.

---

## File Structure

- Create: `ai/taxonomy_loader.py` - Django-free loader (`find_foundational_bundle`, `load_foundational_taxonomy`, `resolve_taxonomy`).
- Create: `ai/tests/test_taxonomy_loader.py` - unit tests over temp bundles.
- Modify: `spike/extract.py` - replace the seed-only module-level load with a `resolve_taxonomy` call (env-var working-copy dir, seed fallback, warning). Add a repo-root sys.path bootstrap so the standalone run can import `ai.taxonomy_loader`.
- Create: `spike/test_extract_taxonomy.py` - regression test that the default (no env var) still yields the seed taxonomy and a stable prompt section.

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
Expected: BASE SHA `70687cd` or a descendant; branch is your auto-worktree branch; status clean.

- [ ] **Step 2: Merge `main` into your worktree branch**

Run:
```bash
git fetch
git merge main --no-edit
```
Expected: "Already up to date." or a clean fast-forward.

- [ ] **Step 3: Confirm the seed taxonomy and baseline suite**

Run:
```bash
ls ai/taxonomies/pt_classification.yaml
/Users/chuck/PolicyWonk/ai/venv/bin/python -m pytest -q
```
Expected: the seed file exists; full suite passes (287 on BASE). Use this interpreter for every test run. If anything fails before you change a thing, STOP and report.

---

## Task 2: find_foundational_bundle

**Files:**
- Create: `ai/taxonomy_loader.py`
- Create: `ai/tests/test_taxonomy_loader.py`

- [ ] **Step 1: Write the failing tests**

Create `ai/tests/test_taxonomy_loader.py`:

```python
"""Tests for ai.taxonomy_loader (AI-12-revised: read taxonomy from the bundle)."""
from pathlib import Path

import yaml

from ai.taxonomy_loader import (
    find_foundational_bundle,
    load_foundational_taxonomy,
    resolve_taxonomy,
)

REQUIRED = ("classifications", "retention-schedule")


def _make_bundle(policies_dir, slug, provides, data):
    bundle = policies_dir / slug
    bundle.mkdir(parents=True)
    fm_provides = "\n".join(f"  - {p}" for p in provides)
    (bundle / "policy.md").write_text(
        f"---\nfoundational: true\nprovides:\n{fm_provides}\n---\nBody.\n",
        encoding="utf-8",
    )
    (bundle / "data.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")
    return bundle


def _make_flat(policies_dir, slug):
    (policies_dir / f"{slug}.md").write_text(
        "---\ntitle: Flat\n---\nBody.\n", encoding="utf-8"
    )


def test_find_returns_none_when_dir_missing(tmp_path):
    assert find_foundational_bundle(tmp_path / "nope", REQUIRED) is None


def test_find_returns_none_when_no_matching_bundle(tmp_path):
    policies = tmp_path / "policies"
    policies.mkdir()
    _make_flat(policies, "code-of-conduct")
    assert find_foundational_bundle(policies, REQUIRED) is None


def test_find_returns_data_path_for_matching_bundle(tmp_path):
    policies = tmp_path / "policies"
    policies.mkdir()
    _make_flat(policies, "code-of-conduct")
    bundle = _make_bundle(
        policies, "document-retention",
        ["classifications", "retention-schedule"],
        {"classifications": [{"id": "a", "name": "A"}], "retention_schedule": []},
    )
    assert find_foundational_bundle(policies, REQUIRED) == bundle / "data.yaml"


def test_find_requires_all_capabilities(tmp_path):
    policies = tmp_path / "policies"
    policies.mkdir()
    _make_bundle(policies, "partial", ["classifications"], {"classifications": []})
    assert find_foundational_bundle(policies, REQUIRED) is None
```

- [ ] **Step 2: Run to verify failure**

Run:
```bash
/Users/chuck/PolicyWonk/ai/venv/bin/python -m pytest ai/tests/test_taxonomy_loader.py -q
```
Expected: FAIL at import (`ai.taxonomy_loader` does not exist).

- [ ] **Step 3: Create the loader with find_foundational_bundle**

Create `ai/taxonomy_loader.py`:

```python
"""Locate and load a diocese's foundational taxonomy bundle.

Django-free so both the standalone spike (`spike/extract.py`) and the
app's extraction path can use it. The app passes the working_dir from
`app.working_copy.config.load_working_copy_config()`; the spike resolves
the policies dir from an env var. Both then call into here.

The foundational bundle is found by CAPABILITY (its `provides:` list),
never by a hardcoded slug, so any diocese's retention bundle works.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from ingest.policy_reader import BundleAwarePolicyReader


def find_foundational_bundle(policies_dir, required):
    """Return the data.yaml Path of the foundational policy whose `provides`
    covers every capability in `required`, or None.

    Returns None when `policies_dir` is missing or not a directory, or when
    no foundational bundle provides all required capabilities. A malformed
    bundle (invalid policy.md or data.yaml) raises BundleError from the
    reader; that surfaces deliberately rather than silently falling back.
    """
    policies_dir = Path(policies_dir)
    if not policies_dir.is_dir():
        return None
    required_set = set(required)
    for policy in BundleAwarePolicyReader(policies_dir).read():
        if policy.foundational and required_set.issubset(set(policy.provides)):
            return policy.data_path
    return None
```

- [ ] **Step 4: Run to verify pass**

Run:
```bash
/Users/chuck/PolicyWonk/ai/venv/bin/python -m pytest ai/tests/test_taxonomy_loader.py -q
```
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add ai/taxonomy_loader.py ai/tests/test_taxonomy_loader.py
git commit -m "feat(AI-12): find foundational taxonomy bundle by capability"
```

---

## Task 3: load_foundational_taxonomy + resolve_taxonomy

**Files:**
- Modify: `ai/taxonomy_loader.py`
- Modify: `ai/tests/test_taxonomy_loader.py`

- [ ] **Step 1: Write the failing tests**

Append to `ai/tests/test_taxonomy_loader.py`:

```python
def test_load_returns_parsed_dict(tmp_path):
    policies = tmp_path / "policies"
    policies.mkdir()
    _make_bundle(
        policies, "document-retention", list(REQUIRED),
        {
            "classifications": [{"id": "fin", "name": "Finance"}],
            "retention_schedule": [{"group": "G", "type": "T", "retention": "7y"}],
        },
    )
    data = load_foundational_taxonomy(policies, REQUIRED)
    assert data["classifications"][0]["id"] == "fin"
    assert data["retention_schedule"][0]["group"] == "G"


def test_load_returns_none_when_no_bundle(tmp_path):
    policies = tmp_path / "policies"
    policies.mkdir()
    assert load_foundational_taxonomy(policies, REQUIRED) is None


def test_resolve_prefers_bundle(tmp_path):
    policies = tmp_path / "policies"
    policies.mkdir()
    _make_bundle(
        policies, "document-retention", list(REQUIRED),
        {"classifications": [{"id": "b", "name": "Bundle"}], "retention_schedule": []},
    )
    seed = tmp_path / "seed.yaml"
    seed.write_text(
        yaml.safe_dump({"classifications": [{"id": "s", "name": "Seed"}], "retention_schedule": []}),
        encoding="utf-8",
    )
    taxonomy, source = resolve_taxonomy(policies, REQUIRED, seed)
    assert source == "bundle"
    assert taxonomy["classifications"][0]["id"] == "b"


def test_resolve_falls_back_to_seed_when_no_policies_dir(tmp_path):
    seed = tmp_path / "seed.yaml"
    seed.write_text(
        yaml.safe_dump({"classifications": [{"id": "s", "name": "Seed"}], "retention_schedule": []}),
        encoding="utf-8",
    )
    taxonomy, source = resolve_taxonomy(None, REQUIRED, seed)
    assert source == "seed"
    assert taxonomy["classifications"][0]["id"] == "s"


def test_resolve_falls_back_to_seed_when_no_matching_bundle(tmp_path):
    policies = tmp_path / "policies"
    policies.mkdir()
    _make_flat(policies, "code-of-conduct")
    seed = tmp_path / "seed.yaml"
    seed.write_text(
        yaml.safe_dump({"classifications": [{"id": "s", "name": "Seed"}], "retention_schedule": []}),
        encoding="utf-8",
    )
    taxonomy, source = resolve_taxonomy(str(policies), REQUIRED, seed)
    assert source == "seed"
    assert taxonomy["classifications"][0]["id"] == "s"
```

- [ ] **Step 2: Run to verify failure**

Run:
```bash
/Users/chuck/PolicyWonk/ai/venv/bin/python -m pytest ai/tests/test_taxonomy_loader.py -q
```
Expected: FAIL with `ImportError`/`AttributeError` for `load_foundational_taxonomy` / `resolve_taxonomy`.

- [ ] **Step 3: Add load_foundational_taxonomy and resolve_taxonomy**

Append to `ai/taxonomy_loader.py`:

```python
def load_foundational_taxonomy(policies_dir, required):
    """Load the data.yaml of the matching foundational bundle as a dict, or None."""
    data_path = find_foundational_bundle(policies_dir, required)
    if data_path is None:
        return None
    with data_path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def resolve_taxonomy(policies_dir, required, seed_path):
    """Return (taxonomy_dict, source) where source is "bundle" or "seed".

    Prefers the foundational bundle in `policies_dir` (the live working
    copy); falls back to `seed_path` when `policies_dir` is falsy or has no
    matching bundle. The caller decides whether to warn on a seed fallback.
    """
    if policies_dir:
        taxonomy = load_foundational_taxonomy(policies_dir, required)
        if taxonomy is not None:
            return taxonomy, "bundle"
    with Path(seed_path).open(encoding="utf-8") as fh:
        return yaml.safe_load(fh), "seed"
```

- [ ] **Step 4: Run to verify pass**

Run:
```bash
/Users/chuck/PolicyWonk/ai/venv/bin/python -m pytest ai/tests/test_taxonomy_loader.py -q
```
Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add ai/taxonomy_loader.py ai/tests/test_taxonomy_loader.py
git commit -m "feat(AI-12): load + resolve taxonomy (bundle preferred, seed fallback)"
```

---

## Task 4: Wire spike/extract.py to the resolver

**Files:**
- Modify: `spike/extract.py`
- Create: `spike/test_extract_taxonomy.py`

- [ ] **Step 1: Write the failing regression test**

Create `spike/test_extract_taxonomy.py`:

```python
"""AI-12-revised: spike/extract.py taxonomy resolution regression test.

With no POLICYCODEX_POLICIES_DIR set, extract.py must source the seed
taxonomy exactly as before (8 classifications) and render a stable prompt
section, so the change is a pure re-point with no default-behavior drift.
"""
import importlib


def test_extract_defaults_to_seed_taxonomy(monkeypatch):
    monkeypatch.delenv("POLICYCODEX_POLICIES_DIR", raising=False)
    import extract  # spike/ is on sys.path under pytest (rootdir insertion)
    importlib.reload(extract)
    assert extract._taxonomy_source == "seed"
    assert len(extract.TAXONOMY["classifications"]) == 8
    # The rendered prompt section still carries every classification id.
    for entry in extract.TAXONOMY["classifications"]:
        assert entry["id"] in extract.TAXONOMY_SECTION
```

- [ ] **Step 2: Run to verify failure**

Run:
```bash
/Users/chuck/PolicyWonk/ai/venv/bin/python -m pytest spike/test_extract_taxonomy.py -q
```
Expected: FAIL with `AttributeError: module 'extract' has no attribute '_taxonomy_source'` (the symbol does not exist yet).

- [ ] **Step 3: Re-point spike/extract.py**

In `spike/extract.py`, the imports block currently ends at:

```python
import yaml
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()
```

Insert, immediately after `load_dotenv()`:

```python
# Make the repo root importable so the standalone `python extract.py` run can
# load the shared taxonomy loader even when invoked from inside spike/.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from ai.taxonomy_loader import resolve_taxonomy  # noqa: E402 (needs the sys.path bootstrap above)
```

Then replace this block:

```python
# Seed taxonomy for the install-zero diocese (Pensacola-Tallahassee).
# Built from the diocese's Document Retention Policy (rev. Aug, 2022).
# When the Week-3 bundle scaffolding lands this file moves to
# policies/document-retention/data.yaml; the injection logic is the same.
TAXONOMY_PATH = Path(__file__).resolve().parent.parent / "ai" / "taxonomies" / "pt_classification.yaml"

def _load_taxonomy(path: Path = TAXONOMY_PATH) -> dict:
    """Read the PT taxonomy YAML once at import time."""
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)
```

with:

```python
# Taxonomy source (AI-12-revised). Prefer the diocese's foundational bundle
# in the local working copy so a published edit to the retention policy flows
# into the next extraction (live sync). Set POLICYCODEX_POLICIES_DIR to the
# working copy's policies/ dir to enable it. When unset or no matching bundle
# exists, fall back to the seed taxonomy below (the dev default). The bundle
# is found by capability (`provides:`), not by a hardcoded slug.
SEED_TAXONOMY_PATH = Path(__file__).resolve().parent.parent / "ai" / "taxonomies" / "pt_classification.yaml"
REQUIRED_CAPABILITIES = ("classifications", "retention-schedule")
```

Then replace this block:

```python
TAXONOMY = _load_taxonomy()
TAXONOMY_SECTION = _build_taxonomy_section(TAXONOMY)
```

with:

```python
_policies_dir = os.environ.get("POLICYCODEX_POLICIES_DIR")
TAXONOMY, _taxonomy_source = resolve_taxonomy(
    _policies_dir, REQUIRED_CAPABILITIES, SEED_TAXONOMY_PATH
)
if _taxonomy_source == "seed" and _policies_dir:
    print(
        f"  note: no foundational bundle in {_policies_dir}; using seed taxonomy",
        file=sys.stderr,
    )
TAXONOMY_SECTION = _build_taxonomy_section(TAXONOMY)
```

- [ ] **Step 4: Run to verify pass**

Run:
```bash
/Users/chuck/PolicyWonk/ai/venv/bin/python -m pytest spike/test_extract_taxonomy.py -q
```
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add spike/extract.py spike/test_extract_taxonomy.py
git commit -m "feat(AI-12): re-point spike extraction to the working-copy bundle (seed fallback)"
```

---

## Task 5: Full-suite verification

**Files:** none modified.

- [ ] **Step 1: Run the new tests verbosely**

Run:
```bash
/Users/chuck/PolicyWonk/ai/venv/bin/python -m pytest ai/tests/test_taxonomy_loader.py spike/test_extract_taxonomy.py -v
```
Expected: 10 passed (9 loader + 1 spike regression).

- [ ] **Step 2: Run the entire suite**

Run:
```bash
/Users/chuck/PolicyWonk/ai/venv/bin/python -m pytest -q
```
Expected: full suite PASS. Baseline 287; this ticket adds 10 tests, so expect 297. The `spike/eval` tests must still pass unchanged: they score committed `spike/outputs/*.json` offline and never call `extract.py`, so the re-point cannot move eval scores. Report the exact observed number.

- [ ] **Step 3: Confirm scope, prompt-stability, and banned tokens**

Run:
```bash
git diff main --stat
git diff main -- spike/extract.py | grep -E "^[+-]" | grep -iE "EXTRACTION_PROMPT|_build_taxonomy_section|Pensacola|Section 3.0" || echo "prompt-rendering text untouched"
grep -n "—" ai/taxonomy_loader.py ai/tests/test_taxonomy_loader.py spike/test_extract_taxonomy.py || echo "clean: no em dashes"
```
Expected: `--stat` shows only `ai/taxonomy_loader.py`, `ai/tests/test_taxonomy_loader.py`, `spike/extract.py`, `spike/test_extract_taxonomy.py`. The prompt-rendering grep prints "prompt-rendering text untouched" (the diff only changes the load path, not `_build_taxonomy_section` or `EXTRACTION_PROMPT`). The em-dash guard prints "clean".

---

## Out of Scope / follow-ups

- **Genericize the prompt's PT header.** `_build_taxonomy_section` still emits "## Diocese taxonomy reference (Diocese of Pensacola-Tallahassee)" and "Section 3.0 of the diocesan retention policy". Those are static prompt strings; changing them risks eval drift and belongs to REPO-10 (which re-runs eval). This ticket intentionally leaves the prompt bytes unchanged.
- **App-side extraction wiring.** The app does not yet have an integrated extraction pass. When it lands, it calls `resolve_taxonomy(load_working_copy_config().working_dir / "policies", REQUIRED_CAPABILITIES, seed_path)` (Django available there). No new loader work needed; that is why the loader is Django-free.
- **AI-13 gap detection** consumes the same bundle `data.yaml` this ticket wires; it is a separate Wave-2 ticket.

---

## Self-Review (run by the author after drafting)

1. **Spec coverage.** AI-12 "moves the read location to the policy repo and lets edits flow live": Task 2-3 build the bundle reader keyed on the working copy; Task 4 makes the spike prefer the working-copy bundle (env-var-pointed) with a seed fallback, so a published bundle edit flows into the next extraction. "Via INGEST-07's BundleAwarePolicyReader": used in `find_foundational_bundle`. The Django-coupling fork was resolved (Chuck, 2026-05-24) in favor of the Django-free loader; the app reuses it later (Out of Scope note).
2. **Placeholder scan.** Every code step is complete; every command has an expected result. No TBD / "handle edge cases" / "similar to".
3. **Type/string consistency.** `REQUIRED = ("classifications", "retention-schedule")` (hyphen, capability names) is used consistently in tests and `REQUIRED_CAPABILITIES` in the spike; the `data.yaml` key read by `_build_taxonomy_section` is `retention_schedule` (underscore) and the test fixtures use that underscore key. `resolve_taxonomy` returns `(dict, str)` with source values `"bundle"`/`"seed"`, matched by `extract._taxonomy_source` checks and the loader tests. `find_foundational_bundle` returns a `Path` (the bundle's `data_path` from `LogicalPolicy`), asserted as `bundle / "data.yaml"` in `test_find_returns_data_path_for_matching_bundle` (consistent with `BundleAwarePolicyReader` setting `data_path = bundle_dir / "data.yaml"`). The seed path `ai/taxonomies/pt_classification.yaml` is unchanged from the original `TAXONOMY_PATH`, so env-unset behavior is identical (no eval drift).
