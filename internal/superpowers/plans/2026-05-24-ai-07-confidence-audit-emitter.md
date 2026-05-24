# AI-07 Confidence Audit Emitter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an `ai/audit.py` emitter that turns one AI-extraction dict into the YAML body of a `<slug>.audit.yaml` sidecar holding the per-field confidence scores the spec mandates be kept out of `policy.md`.

**Architecture:** A pure function `to_audit_yaml(extraction) -> str`, parallel to `ai/emit.py:to_markdown`. It is the exact inverse of `emit.py`: `emit.py` strips every confidence field from the policy markdown; `audit.py` keeps only the confidence fields (plus `title` + `source_file` for traceability) and drops everything else. The caller decides where to write the result, exactly as with `emit.py` (no file I/O, no slug derivation in this ticket — that belongs to the AI-10 inventory orchestrator). No UI; detail-view confidence badges defer to APP-23.

**Tech Stack:** Python 3.14, PyYAML (`yaml.safe_dump`), pytest. Interpreter: `ai/venv/bin/python`.

---

## Scope notes (read before starting)

- Spec basis: `PolicyWonk-v0.1-Spec.md` line 99 — "...with confidence scores recorded in a separate audit file." Ticket AI-07 scope was resolved 2026-05-24: the extraction prompt already scores every field; the deliverable is this separate sidecar emitter. **Do NOT add confidence to `policy.md`** (`emit.py` strips it and a test enforces that).
- The real confidence keys produced by the inventory pass (verified against `spike/outputs/*.json`): `category_confidence`, `owner_role_confidence`, `effective_date_confidence`, `last_review_date_confidence`, `next_review_date_confidence`, `retention_period_confidence`, `address_confidence`. Values are the strings `low` / `medium` / `high`.
- **Decided YAML shape (confirmed at plan review):** a nested `confidence:` map keyed by base field name, under top-level `title` + `source_file`. Canonical confidence keys always appear (null if missing) for stable diffs, mirroring `emit.py`'s "canonical first, null for missing" discipline. Any extra `*_confidence` keys not in the canonical set are appended alphabetized so nothing is silently lost.

Target shape:

```yaml
title: 'Internal Controls Policy – Diocese of Pensacola-Tallahassee (Section 101)'
source_file: '101 Internal Controls.pdf'
confidence:
  category: high
  owner_role: high
  effective_date: medium
  last_review_date: medium
  next_review_date: low
  retention_period: low
  address: medium
```

## File Structure

- Create: `ai/audit.py` — the `to_audit_yaml` emitter + the canonical confidence-field order constant.
- Create: `ai/tests/test_audit.py` — unit + round-trip tests.
- No other files change. `ai/emit.py` is untouched.

---

### Task 1: Canonical confidence map (canonical keys, null for missing)

**Files:**
- Create: `ai/audit.py`
- Test: `ai/tests/test_audit.py`

- [ ] **Step 1: Write the failing test**

```python
"""Tests for ai.audit.to_audit_yaml (AI-07: confidence audit sidecar emitter)."""
import json
from pathlib import Path

import pytest
import yaml

from ai.audit import CONFIDENCE_FIELD_ORDER, to_audit_yaml


SPIKE_OUTPUTS = Path(__file__).resolve().parents[2] / "spike" / "outputs"


def _load(md: str) -> dict:
    return yaml.safe_load(md)


def test_canonical_confidence_fields_collected():
    extraction = {
        "title": "T",
        "category": "Finance",
        "category_confidence": "high",
        "owner_role_confidence": "medium",
        "effective_date_confidence": "low",
        "last_review_date_confidence": "high",
        "next_review_date_confidence": "low",
        "retention_period_confidence": "medium",
        "address_confidence": "high",
    }
    doc = _load(to_audit_yaml(extraction))
    assert doc["confidence"] == {
        "category": "high",
        "owner_role": "medium",
        "effective_date": "low",
        "last_review_date": "high",
        "next_review_date": "low",
        "retention_period": "medium",
        "address": "high",
    }


def test_missing_confidence_emits_null():
    extraction = {"title": "T", "category_confidence": "high"}
    doc = _load(to_audit_yaml(extraction))
    # every canonical field is present; the absent ones are null
    for base in CONFIDENCE_FIELD_ORDER:
        assert base in doc["confidence"]
    assert doc["confidence"]["category"] == "high"
    assert doc["confidence"]["owner_role"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `ai/venv/bin/python -m pytest ai/tests/test_audit.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ai.audit'`

- [ ] **Step 3: Write minimal implementation**

```python
"""Confidence audit-sidecar emitter for AI-extracted policy metadata.

The inverse of ``ai/emit.py``: where ``emit.py`` strips every confidence
field out of the policy markdown, this module keeps only the confidence
scores (plus ``title`` and ``source_file`` for traceability) and emits the
YAML body of a ``<slug>.audit.yaml`` sidecar. The caller decides where to
write the result and how to derive the slug (see AI-10).

Per the v0.1 spec (line 99), confidence scores are recorded in a separate
audit file, never in the human-readable policy markdown.

Design notes:

- Canonical confidence fields (``CONFIDENCE_FIELD_ORDER``) always appear in
  the ``confidence:`` map, with value ``null`` when the extraction omits
  them, so audit diffs stay stable across runs.
- Any extra ``*_confidence`` keys not in the canonical set are appended
  alphabetized, so a new scored field is never silently dropped.
- ``title`` and ``source_file`` are emitted as top-level identifying
  metadata (``source_file`` is read from the spike-internal ``_source_file``
  key); both are ``null`` when absent.
"""
from __future__ import annotations

from typing import Any

import yaml


# Canonical base field names (without the "_confidence" suffix), in a fixed
# order that mirrors ai/emit.py's FRONTMATTER_KEY_ORDER where the fields
# overlap. These always appear in the confidence map, null if missing.
CONFIDENCE_FIELD_ORDER: tuple[str, ...] = (
    "category",
    "owner_role",
    "effective_date",
    "last_review_date",
    "next_review_date",
    "retention_period",
    "address",
)

_CONFIDENCE_SUFFIX = "_confidence"


def _confidence_map(extraction: dict[str, Any]) -> dict[str, Any]:
    """Return the confidence sub-map: canonical fields first, extras appended."""
    result: dict[str, Any] = {}
    for base in CONFIDENCE_FIELD_ORDER:
        result[base] = extraction.get(f"{base}{_CONFIDENCE_SUFFIX}")

    canonical_keys = {f"{b}{_CONFIDENCE_SUFFIX}" for b in CONFIDENCE_FIELD_ORDER}
    extras = sorted(
        k
        for k in extraction
        if k.endswith(_CONFIDENCE_SUFFIX) and k not in canonical_keys
    )
    for key in extras:
        base = key[: -len(_CONFIDENCE_SUFFIX)]
        result[base] = extraction[key]
    return result


def to_audit_yaml(extraction: dict[str, Any]) -> str:
    """Convert an AI-extraction dict to the YAML body of an audit sidecar.

    The output is a block-style YAML document with top-level ``title`` and
    ``source_file`` keys followed by a ``confidence:`` map. Confidence scores
    are the only per-field data carried over from the extraction; all policy
    content lives in the markdown emitted by ``ai/emit.py``.
    """
    doc: dict[str, Any] = {
        "title": extraction.get("title"),
        "source_file": extraction.get("_source_file"),
        "confidence": _confidence_map(extraction),
    }
    return yaml.safe_dump(
        doc,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `ai/venv/bin/python -m pytest ai/tests/test_audit.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add ai/audit.py ai/tests/test_audit.py
git commit -m "feat(AI-07): confidence audit-sidecar emitter (canonical map)"
```

---

### Task 2: Top-level metadata + non-confidence exclusion

**Files:**
- Test: `ai/tests/test_audit.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_title_and_source_file_top_level():
    extraction = {
        "title": "Internal Controls Policy",
        "_source_file": "101 Internal Controls.pdf",
        "category_confidence": "high",
    }
    doc = _load(to_audit_yaml(extraction))
    assert doc["title"] == "Internal Controls Policy"
    assert doc["source_file"] == "101 Internal Controls.pdf"


def test_title_and_source_file_null_when_absent():
    doc = _load(to_audit_yaml({"category_confidence": "high"}))
    assert doc["title"] is None
    assert doc["source_file"] is None


def test_non_confidence_fields_excluded():
    extraction = {
        "title": "T",
        "category": "Finance",
        "owner_role": "CFO",
        "summary": "long body text",
        "retention_period_years": 7,
        "category_confidence": "high",
    }
    md = to_audit_yaml(extraction)
    doc = _load(md)
    # No policy content leaks anywhere in the audit document.
    assert "summary" not in doc
    assert "owner_role" not in doc          # only inside confidence map
    assert "retention_period_years" not in doc
    assert "long body text" not in md
    assert doc["confidence"]["category"] == "high"


def test_extra_confidence_keys_appended_alphabetized():
    extraction = {
        "category_confidence": "high",
        "zeta_confidence": "low",
        "alpha_confidence": "medium",
    }
    doc = _load(to_audit_yaml(extraction))
    keys = list(doc["confidence"].keys())
    # canonical order first, then extras alphabetized
    assert keys[: len(CONFIDENCE_FIELD_ORDER)] == list(CONFIDENCE_FIELD_ORDER)
    assert keys[len(CONFIDENCE_FIELD_ORDER):] == ["alpha", "zeta"]
```

- [ ] **Step 2: Run tests to verify they pass**

These exercise behavior already implemented in Task 1, so they should pass immediately. Run:
`ai/venv/bin/python -m pytest ai/tests/test_audit.py -v`
Expected: PASS (6 tests). If any fail, fix `ai/audit.py` until green — do not weaken the test.

- [ ] **Step 3: Commit**

```bash
git add ai/tests/test_audit.py
git commit -m "test(AI-07): assert metadata + non-confidence exclusion + extra-key order"
```

---

### Task 3: Block-style YAML + spike round-trip

**Files:**
- Test: `ai/tests/test_audit.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_block_style_not_inline():
    md = to_audit_yaml({"title": "T", "category_confidence": "high"})
    assert "{" not in md          # block style, not inline {a: b}
    assert "\n" in md


def test_round_trip_spike_output():
    path = SPIKE_OUTPUTS / "101 Internal Controls.json"
    if not path.exists():
        pytest.skip("Spike output not present in this worktree")
    extraction = json.loads(path.read_text())
    doc = _load(to_audit_yaml(extraction))
    assert doc["title"] == extraction["title"]
    assert doc["source_file"] == extraction["_source_file"]
    assert doc["confidence"]["category"] == extraction["category_confidence"]
    assert doc["confidence"]["address"] == extraction["address_confidence"]
```

- [ ] **Step 2: Run tests**

Run: `ai/venv/bin/python -m pytest ai/tests/test_audit.py -v`
Expected: PASS (8 tests; the round-trip skips if `spike/outputs/` is empty in the worktree — that is acceptable, the suite on a full checkout exercises it).

- [ ] **Step 3: Commit**

```bash
git add ai/tests/test_audit.py
git commit -m "test(AI-07): block-style + spike-output round-trip"
```

---

### Task 4: Full-suite verification

- [ ] **Step 1: Run the whole suite**

Run: `ai/venv/bin/python -m pytest -q`
Expected: `330 passed` (322 baseline + 8 new). The round-trip test counts as passed or skipped depending on `spike/outputs/` presence; on the parent checkout it passes.

- [ ] **Step 2: Confirm `emit.py` untouched and confidence still stripped from markdown**

Run: `ai/venv/bin/python -m pytest ai/tests/test_emit.py -q`
Expected: PASS, unchanged count. (Sanity that AI-07 did not regress the emit-side contract.)

---

## Self-Review checklist (run before requesting review)

- Spec line 99 ("separate audit file") is implemented by `to_audit_yaml`. ✔
- No confidence added to `policy.md` (`emit.py` untouched; its strip test still green). ✔
- No placeholders; every step has runnable code/commands. ✔
- Function/constant names consistent across tasks (`to_audit_yaml`, `CONFIDENCE_FIELD_ORDER`). ✔
- No file I/O or slug derivation (deferred to AI-10) — YAGNI. ✔

## Dispatch note

Implementer runs in `isolation: "worktree"`, Sonnet. First action inside the worktree: `git merge main` into the auto-branch. Critical Operational Note applies: never `cd /Users/chuck/PolicyWonk` for git ops; operate only inside the worktree. Two-stage review (spec then quality) before merge.
