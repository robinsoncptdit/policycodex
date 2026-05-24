# AI-13: Retention Gap Detection Design

**Date:** 2026-05-24
**Ticket:** AI-13 (S) - "Gap-detection pass: flag any policy whose type is not represented in the diocese's retention schedule"
**Depends on:** AI-12-revised (taxonomy bundle read, done), INGEST-07 (bundle-aware reader, done), APP-06 (catalog, done)
**Status:** Designed autonomously 2026-05-24 (Chuck in auto mode); interpretation decision flagged below for review.

## Goal

Surface, in the catalog, every policy whose type is not represented in the diocese's foundational retention bundle, so a human can re-classify it. A count plus the flagged rows.

## Key interpretation decision (flagged for review)

The ticket says "not represented in the diocese's **retention schedule**." The bundle `data.yaml` has two axes:
- `classifications`: a controlled list of `{id, name}` types (8 for PT). This is the type vocabulary the AI extraction injects (AI-11/AI-12).
- `retention_schedule`: free-text rows `{group, type, retention, medium, retained_at}`. The `type` is verbatim prose from the source PDF; `group` is a loose category-level label.

**Decision: gap = a policy whose `category` does not match any `classifications` entry (by `id` or `name`, case-insensitive), including policies with no category at all.**

Rationale: per-policy matching against the free-text `retention_schedule` rows is unreliable in v0.1 (the `type` strings are prose, the `group` labels do not map cleanly to category names). The `classifications` list is the controlled type vocabulary that lives in the same retention bundle and that extraction already uses, so membership there is the crisp, testable signal for "this policy's type is known to the diocese's retention taxonomy." A finer "every type has a retention rule" check awaits the canonical chapter-axis mapping noted as missing in CLAUDE.md; it is explicitly out of scope here.

Deprecated classifications (`deprecated: true`) stay in the list and therefore still count as represented, consistent with the soft-delete rule in the foundational-policy design (a deprecated id remains valid for existing references).

If Chuck wants matching against `retention_schedule` rows/groups instead, that is a scoped change to the `known_types` source set; the rest of the design is unaffected.

## Architecture

A Django-free pure helper in `ai/gap_detection.py` (mirrors `ai/taxonomy_loader.py`'s Django-free stance so the AI lane owns it), consumed by the catalog view. The view already loads the policies and knows `policies_dir`; it loads the bundle classifications via the existing `ai/taxonomy_loader.load_foundational_taxonomy(policies_dir, ["classifications"])`, computes per-row gap flags, and passes a count + per-row flag to the template. The template adds a banner (count) and a per-row badge (drill-down).

## Components

### 1. `ai/gap_detection.py` (new, Django-free)

```python
def known_types(classifications) -> set[str]:
    """Casefolded set of classification ids and names from bundle data.yaml."""

def is_gap(category, known: set[str]) -> bool:
    """True when category is missing/empty or not in `known`."""

def find_gaps(items, classifications) -> list:
    """items: iterable of (key, category). Returns the keys that are gaps."""
```

### 2. `core/views.py:catalog` (modify)

After building `policies`, load the bundle classifications defensively (degrade to no-gap-detection on any taxonomy load failure or when there is no bundle), compute `known_types`, set `is_gap` per row, and pass `gap_count` to the template. Gap detection runs only when classifications are actually available (`known` non-empty), so fresh installs and bundle-less repos flag nothing.

### 3. `core/templates/catalog.html` (modify)

- A banner above the policy list, shown only when `gap_count > 0`: "`N` policies have a type not in the retention taxonomy. Review and re-classify."
- A per-row badge `no retention match` inside the `{% for row in rows %}` loop when `row.is_gap`.

## Data flow

catalog view -> load policies (BundleAwarePolicyReader) -> load classifications (taxonomy_loader) -> `known_types` -> per policy: `is_gap(frontmatter.category, known)` -> rows carry `is_gap`, context carries `gap_count` -> template renders banner + badges.

## Error handling

- No working copy / no `policies/` dir: existing empty-state path, unchanged (no gap work runs).
- No foundational bundle / no `classifications`: `known` is empty, `gap_count` is 0, nothing flagged. Graceful.
- Taxonomy load raises (malformed bundle): the catalog already raises earlier via `BundleAwarePolicyReader`; the new taxonomy load is additionally wrapped in try/except and degrades to no gap detection rather than introducing a new 500 path.

## Testing

- `ai/tests/test_gap_detection.py`: `known_types` (ids + names, casefold, ignores non-dict rows); `is_gap` (present, absent, missing/empty category, case-insensitive, deprecated still counts as known); `find_gaps` (returns only gap keys, preserves order).
- `core/tests/test_catalog.py` (extend): a working copy with a bundle + one in-vocabulary policy + one out-of-vocabulary policy renders `gap_count == 1` and marks the right row; a working copy with no bundle flags nothing; a taxonomy-load error degrades to no gaps (no 500).

## Out of scope

- Matching against `retention_schedule` rows/groups (free-text; deferred).
- Auto re-classification or any write action (read-only surfacing only).
- A separate gap-report page or export (the catalog banner + badges are the v0.1 surface).
- Gap detection in the read-only detail view (APP-23 owns that surface; AI-13 is catalog-only).

## Affected files

- Create: `ai/gap_detection.py`, `ai/tests/test_gap_detection.py`.
- Modify: `core/views.py` (catalog), `core/templates/catalog.html`, `core/tests/test_catalog.py`.
