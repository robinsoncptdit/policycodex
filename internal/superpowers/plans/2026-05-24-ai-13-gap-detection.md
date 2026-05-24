# AI-13 Retention Gap Detection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Flag, in the catalog, every policy whose type (its `category` frontmatter) is not represented in the diocese's foundational retention bundle, surfacing a count plus a per-row badge.

**Architecture:** A Django-free pure helper `ai/gap_detection.py` computes which policies are gaps given the bundle's `classifications`. The catalog view loads those classifications via the existing `ai/taxonomy_loader.load_foundational_taxonomy`, computes per-row gap flags + a total, and the template renders a banner (count) and a per-row badge (drill-down). Gap detection degrades to off when no bundle / classifications are available, so fresh installs flag nothing.

**Tech Stack:** Python 3.14, Django (catalog view + template), pytest. Test interpreter: `/Users/chuck/PolicyWonk/ai/venv/bin/python` (run from the worktree root).

**Design doc:** `internal/superpowers/specs/2026-05-24-ai-13-gap-detection-design.md`

---

## Scope notes (read before starting)

- **Interpretation (decided in the design doc):** a policy is a gap when its `category` does not match any bundle `classifications` entry (by `id` or `name`, case-insensitive), including policies with no category. The free-text `retention_schedule` rows are NOT used for matching in v0.1.
- Deprecated classifications stay in the list and count as "represented" (soft-delete rule).
- Read-only surfacing in the catalog only. No write/re-classify action. No detail-view work (APP-23 owns that surface).
- Reuse `ai/taxonomy_loader.load_foundational_taxonomy` (the same loader AI extraction uses) so gap detection and extraction see identical classifications.
- Baseline suite: 346 tests.

## File Structure

- Create: `ai/gap_detection.py` - `known_types`, `is_gap`, `find_gaps` (Django-free).
- Create: `ai/tests/test_gap_detection.py` - unit tests.
- Modify: `core/views.py` - `catalog` loads classifications + computes gaps.
- Modify: `core/templates/catalog.html` - banner + per-row badge.
- Modify: `core/tests/test_catalog.py` - autouse taxonomy default + gap tests.

---

### Task 1: `ai/gap_detection.py` pure helpers

**Files:**
- Create: `ai/gap_detection.py`
- Test: `ai/tests/test_gap_detection.py`

- [ ] **Step 1: Write the failing tests**

```python
"""Tests for ai.gap_detection (AI-13: retention gap detection)."""
from ai.gap_detection import find_gaps, is_gap, known_types


def test_known_types_collects_ids_and_names():
    classifications = [
        {"id": "financial", "name": "Financial"},
        {"id": "personnel", "name": "Personnel"},
    ]
    assert known_types(classifications) == {
        "financial", "personnel",
    }


def test_known_types_casefolds_and_strips():
    assert known_types([{"id": " Financial ", "name": "FINANCE"}]) == {
        "financial", "finance",
    }


def test_known_types_skips_non_dict_and_missing_keys():
    classifications = [
        {"id": "ok"},
        "not-a-dict",
        {"name": None},
        {},
    ]
    assert known_types(classifications) == {"ok"}


def test_known_types_empty_or_none():
    assert known_types([]) == set()
    assert known_types(None) == set()


def test_is_gap_known_category_is_false():
    known = {"financial"}
    assert is_gap("Financial", known) is False


def test_is_gap_unknown_category_is_true():
    assert is_gap("Marketing", {"financial"}) is True


def test_is_gap_missing_category_is_true():
    assert is_gap(None, {"financial"}) is True
    assert is_gap("", {"financial"}) is True
    assert is_gap("   ", {"financial"}) is True


def test_is_gap_is_case_insensitive():
    assert is_gap("  finANCIAL ", {"financial"}) is False


def test_find_gaps_returns_only_gaps_in_order():
    classifications = [{"id": "financial"}, {"name": "Personnel"}]
    items = [
        ("a", "Financial"),     # known
        ("b", "Marketing"),     # gap
        ("c", None),            # gap (missing)
        ("d", "personnel"),     # known (name, casefold)
    ]
    assert find_gaps(items, classifications) == ["b", "c"]


def test_find_gaps_deprecated_classification_counts_as_known():
    # A deprecated classification stays in the list, so a policy using it is
    # not a gap (deprecated ids remain valid for existing references).
    classifications = [{"id": "legacy", "name": "Legacy", "deprecated": True}]
    assert find_gaps([("x", "Legacy")], classifications) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/Users/chuck/PolicyWonk/ai/venv/bin/python -m pytest ai/tests/test_gap_detection.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ai.gap_detection'`

- [ ] **Step 3: Write the implementation**

```python
"""Retention gap detection for the policy catalog (AI-13).

A policy is a "retention gap" when its type (the `category` frontmatter
field) is not represented in the diocese's foundational retention bundle.
"Represented" means the category matches one of the bundle's
`classifications` by `id` or `name`, case-insensitive. The free-text
`retention_schedule` rows are not used for matching in v0.1 (see the
AI-13 design doc).

Django-free, mirroring ai/taxonomy_loader.py, so the catalog view and any
future batch pass can share it.
"""
from __future__ import annotations

from typing import Iterable


def known_types(classifications) -> set[str]:
    """Return the casefolded set of classification ids and names.

    Accepts the `classifications` list from a bundle data.yaml (a list of
    {id, name} mappings). Non-mapping entries and falsy values are skipped.
    Deprecated classifications are included: a deprecated id stays valid for
    existing references per the foundational-policy design.
    """
    known: set[str] = set()
    for entry in classifications or []:
        if not isinstance(entry, dict):
            continue
        for key in ("id", "name"):
            value = entry.get(key)
            if value:
                known.add(str(value).strip().casefold())
    return known


def is_gap(category, known: set[str]) -> bool:
    """True when `category` is missing/blank or not in `known`."""
    if not category or not str(category).strip():
        return True
    return str(category).strip().casefold() not in known


def find_gaps(items: Iterable[tuple], classifications) -> list:
    """Return the keys from `items` whose category is a gap.

    `items` is an iterable of (key, category) pairs; order is preserved.
    """
    known = known_types(classifications)
    return [key for key, category in items if is_gap(category, known)]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/Users/chuck/PolicyWonk/ai/venv/bin/python -m pytest ai/tests/test_gap_detection.py -v`
Expected: PASS (10 tests)

- [ ] **Step 5: Commit**

```bash
git add ai/gap_detection.py ai/tests/test_gap_detection.py
git commit -m "feat(AI-13): gap-detection helpers (category vs bundle classifications)"
```

---

### Task 2: Wire gap detection into the catalog view

**Files:**
- Modify: `core/views.py` (imports + the `catalog` function)

- [ ] **Step 1: Add imports**

At the top of `core/views.py`, with the other `from ai...`/`from ingest...` imports, add:

```python
from ai.gap_detection import is_gap, known_types
from ai.taxonomy_loader import load_foundational_taxonomy
```

- [ ] **Step 2: Replace the row-building block in `catalog`**

Replace the current tail of `catalog` (the `policies = ...` through the final `return render(...)`):

```python
    policies = list(BundleAwarePolicyReader(policies_dir).read())
    gate_lookup = _build_gate_lookup(config.working_dir)
    rows = [
        {"policy": policy, "gate": gate_lookup.get(policy.slug, "published")}
        for policy in policies
    ]
    return render(request, "catalog.html", {"is_empty_onboarding": False, "rows": rows})
```

with:

```python
    policies = list(BundleAwarePolicyReader(policies_dir).read())
    gate_lookup = _build_gate_lookup(config.working_dir)

    # AI-13: flag policies whose type is not in the diocese's retention
    # bundle classifications. Load via the same taxonomy loader the AI
    # extraction uses, so both see identical types. Any load failure (no
    # bundle, malformed data.yaml) degrades to no gap detection rather than
    # 500-ing the catalog; gap flags only appear when classifications exist.
    try:
        taxonomy = load_foundational_taxonomy(policies_dir, ["classifications"])
    except Exception as exc:  # noqa: BLE001 - catalog must always render
        logger.warning("AI-13 taxonomy load failed (%s); gap detection off", exc)
        taxonomy = None
    known = known_types((taxonomy or {}).get("classifications"))

    rows = []
    gap_count = 0
    for policy in policies:
        gap = bool(known) and is_gap(policy.frontmatter.get("category"), known)
        if gap:
            gap_count += 1
        rows.append({
            "policy": policy,
            "gate": gate_lookup.get(policy.slug, "published"),
            "is_gap": gap,
        })

    return render(
        request,
        "catalog.html",
        {"is_empty_onboarding": False, "rows": rows, "gap_count": gap_count},
    )
```

- [ ] **Step 3: Run the existing catalog tests (they must still pass)**

Run: `/Users/chuck/PolicyWonk/ai/venv/bin/python -m pytest core/tests/test_catalog.py -q`
Expected: PASS. (Task 3 adds the template bits; the view change alone keeps existing tests green because `gap_count`/`is_gap` are simply unused by the current template, and the new autouse fixture lands in Task 4. Existing tests call the real `load_foundational_taxonomy` against `/tmp/policies`; it returns None when that dir is absent, so `known` is empty and no gaps are flagged. If `/tmp/policies` happens to exist on this machine the result is still no-500; Task 4's autouse fixture removes that dependency entirely.)

- [ ] **Step 4: Commit**

```bash
git add core/views.py
git commit -m "feat(AI-13): compute retention gaps in the catalog view"
```

---

### Task 3: Banner + per-row badge in the template

**Files:**
- Modify: `core/templates/catalog.html`

- [ ] **Step 1: Add the banner inside the non-empty branch**

In `core/templates/catalog.html`, immediately after the `{% else %}` that opens the non-empty branch (before `<section class="approve-pr">`), add:

```html
    {% if gap_count %}
      <p class="gap-banner">
        {{ gap_count }} polic{{ gap_count|pluralize:"y,ies" }} flagged: type not in the retention taxonomy. Review and re-classify.
      </p>
    {% endif %}
```

- [ ] **Step 2: Add the per-row badge**

Inside the `{% for row in rows %}` loop, after the gate badge line
(`<span class="gate-badge ...">{{ row.gate|title }}</span>`), add:

```html
          {% if row.is_gap %}
            <span class="gap-badge">no retention match</span>
          {% endif %}
```

- [ ] **Step 3: Commit**

```bash
git add core/templates/catalog.html
git commit -m "feat(AI-13): catalog gap banner + per-row badge"
```

---

### Task 4: Catalog gap tests + deterministic taxonomy default

**Files:**
- Modify: `core/tests/test_catalog.py`

- [ ] **Step 1: Add an autouse fixture + extend the policy stub**

Add this autouse fixture near the top of `core/tests/test_catalog.py` (after the `stub_gh_provider` fixture). It makes every existing test see "no bundle" deterministically (independent of `/tmp` state); gap tests override it with an inner `patch`.

```python
@pytest.fixture(autouse=True)
def _no_taxonomy_by_default():
    """Default the catalog's taxonomy load to None so existing tests are
    independent of any real /tmp/policies. Gap tests re-patch the same
    target inside the test body (inner patch wins)."""
    with patch("core.views.load_foundational_taxonomy", return_value=None):
        yield
```

Extend `_stub_policy` to accept a category. Change its signature and frontmatter:

```python
def _stub_policy(*, slug, kind="flat", title=None, foundational=False, provides=(), category=None):
    """Build a stand-in for an ingest.policy_reader.LogicalPolicy."""
    from pathlib import Path
    from ingest.policy_reader import LogicalPolicy
    pp = Path(f"/tmp/policies/{slug}.md") if kind == "flat" else Path(f"/tmp/policies/{slug}/policy.md")
    frontmatter = {"title": title or slug.replace("-", " ").title()}
    if category is not None:
        frontmatter["category"] = category
    return LogicalPolicy(
        slug=slug,
        kind=kind,
        policy_path=pp,
        data_path=None if kind == "flat" else pp.parent / "data.yaml",
        frontmatter=frontmatter,
        body="",
        foundational=foundational,
        provides=provides,
    )
```

- [ ] **Step 2: Write the gap tests**

Append to `core/tests/test_catalog.py`:

```python
_TAXONOMY = {"classifications": [{"id": "financial", "name": "Financial"}]}


def test_catalog_flags_policy_with_unknown_category(client, user, stub_gh_provider):
    """One in-vocabulary policy + one out-of-vocabulary policy -> gap_count 1,
    badge on the out-of-vocabulary row."""
    client.force_login(user)
    policies = [
        _stub_policy(slug="known", kind="flat", title="Known", category="Financial"),
        _stub_policy(slug="unknown", kind="flat", title="Unknown", category="Marketing"),
    ]
    with override_settings(
        POLICYCODEX_POLICY_REPO_URL="https://example.com/x.git",
        POLICYCODEX_WORKING_COPY_ROOT="/tmp",
    ):
        with patch("core.views.Path.exists", return_value=True):
            with patch("core.views.BundleAwarePolicyReader") as MockReader:
                MockReader.return_value.read.return_value = iter(policies)
                with patch("core.views.load_foundational_taxonomy", return_value=_TAXONOMY):
                    response = client.get("/catalog/")

    body = response.content.decode()
    assert response.status_code == 200
    assert "gap-banner" in body
    assert "1 policy flagged" in body
    # Exactly one row badge.
    assert body.count("gap-badge") == 1


def test_catalog_no_gaps_when_all_categories_known(client, user, stub_gh_provider):
    client.force_login(user)
    policies = [
        _stub_policy(slug="a", kind="flat", category="Financial"),
        _stub_policy(slug="b", kind="flat", category="financial"),  # casefold match
    ]
    with override_settings(
        POLICYCODEX_POLICY_REPO_URL="https://example.com/x.git",
        POLICYCODEX_WORKING_COPY_ROOT="/tmp",
    ):
        with patch("core.views.Path.exists", return_value=True):
            with patch("core.views.BundleAwarePolicyReader") as MockReader:
                MockReader.return_value.read.return_value = iter(policies)
                with patch("core.views.load_foundational_taxonomy", return_value=_TAXONOMY):
                    response = client.get("/catalog/")

    body = response.content.decode()
    assert "gap-banner" not in body
    assert "gap-badge" not in body


def test_catalog_no_gap_detection_without_bundle(client, user, stub_gh_provider):
    """With no foundational bundle (taxonomy None, the autouse default), even an
    odd category is not flagged."""
    client.force_login(user)
    policies = [_stub_policy(slug="x", kind="flat", category="Whatever")]
    with override_settings(
        POLICYCODEX_POLICY_REPO_URL="https://example.com/x.git",
        POLICYCODEX_WORKING_COPY_ROOT="/tmp",
    ):
        with patch("core.views.Path.exists", return_value=True):
            with patch("core.views.BundleAwarePolicyReader") as MockReader:
                MockReader.return_value.read.return_value = iter(policies)
                response = client.get("/catalog/")

    body = response.content.decode()
    assert "gap-banner" not in body
    assert "gap-badge" not in body


def test_catalog_degrades_when_taxonomy_load_raises(client, user, stub_gh_provider):
    """A taxonomy load error must not 500 the catalog; it degrades to no gaps."""
    client.force_login(user)
    policies = [_stub_policy(slug="x", kind="flat", category="Marketing")]
    with override_settings(
        POLICYCODEX_POLICY_REPO_URL="https://example.com/x.git",
        POLICYCODEX_WORKING_COPY_ROOT="/tmp",
    ):
        with patch("core.views.Path.exists", return_value=True):
            with patch("core.views.BundleAwarePolicyReader") as MockReader:
                MockReader.return_value.read.return_value = iter(policies)
                with patch("core.views.load_foundational_taxonomy", side_effect=RuntimeError("boom")):
                    response = client.get("/catalog/")

    assert response.status_code == 200
    body = response.content.decode()
    assert "gap-banner" not in body
```

- [ ] **Step 3: Run the catalog tests**

Run: `/Users/chuck/PolicyWonk/ai/venv/bin/python -m pytest core/tests/test_catalog.py -v`
Expected: PASS (all existing + 4 new). If an existing test now fails because `load_foundational_taxonomy` is imported into `core.views` but the autouse patch target path is wrong, confirm the import in Task 2 Step 1 is `from ai.taxonomy_loader import load_foundational_taxonomy` (so the patch target `core.views.load_foundational_taxonomy` resolves).

- [ ] **Step 4: Commit**

```bash
git add core/tests/test_catalog.py
git commit -m "test(AI-13): catalog gap-detection tests + deterministic taxonomy default"
```

---

### Task 5: Full-suite verification

- [ ] **Step 1: Run the whole suite**

Run: `/Users/chuck/PolicyWonk/ai/venv/bin/python -m pytest -q`
Expected: `360 passed` (346 baseline + 10 gap_detection + 4 catalog).

---

## Self-Review checklist (run before requesting review)

- Spec coverage: gap helper (Task 1), catalog computation reusing taxonomy_loader (Task 2), banner + badge (Task 3), tests incl. no-bundle + degrade + deprecated (Tasks 1, 4). ✔
- Interpretation (classifications, not retention_schedule) documented in design + plan scope notes. ✔
- Graceful degrade: no bundle / load error -> no gaps, no 500. ✔
- No placeholders; every step has runnable code/commands. ✔
- Names consistent: `known_types`, `is_gap`, `find_gaps`, `gap_count`, `is_gap` row key, `gap-banner`, `gap-badge`. ✔
- Test isolation: autouse fixture removes the `/tmp/policies` real-walk dependency. ✔

## Dispatch note

Implementer runs in `isolation: "worktree"`, Sonnet. First action: `git merge main` into the auto-branch (baseline 346). Critical Operational Note: never `cd /Users/chuck/PolicyWonk` for git ops. Run pytest via `/Users/chuck/PolicyWonk/ai/venv/bin/python` from the worktree root. Two-stage review (spec then quality) before merge.
