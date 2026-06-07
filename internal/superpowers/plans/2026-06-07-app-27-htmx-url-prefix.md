# APP-27: `/htmx/` URL Prefix Convention — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish a namespaced `/htmx/` URL prefix in `core/urls.py` so future HTMX fragment endpoints (APP-28c) land under one segregated path and a future JSON API at `/api/v1/` cannot collide.

**Architecture:** Add a dedicated `core/htmx_urls.py` module that owns the `htmx` application namespace and currently holds an empty `urlpatterns` list. Wire it into `core/urls.py` via `path("htmx/", include("core.htmx_urls"))`. No endpoints exist yet — this lays the convention only. Future fragment views get added to `htmx_urls.py` and reverse-resolve as `htmx:<name>`.

**Tech Stack:** Django 6 URL routing (`include`, application namespaces), pytest-django.

**Test interpreter:** Run the suite as the controller with `ai/venv/bin/python -m pytest` (no root venv; system python lacks pytest).

---

## Background (read before starting)

`core/urls.py` today (verbatim):

```python
"""URL routes for the core app."""
from django.urls import path

from . import views


urlpatterns = [
    path("", views.root_redirect, name="root"),
    path("health/", views.health, name="health"),
    path("catalog/", views.catalog, name="catalog"),
    path("policies/approve/", views.approve_pr, name="approve_pr"),
    path("policies/<slug:slug>/edit/", views.policy_edit, name="policy_edit"),
    path(
        "policies/<slug:slug>/foundational-edit/",
        views.foundational_edit,
        name="foundational_edit",
    ),
    path("policies/<slug:slug>/publish/", views.publish_policy, name="publish_policy"),
    path("policies/<slug:slug>/", views.policy_detail, name="policy_detail"),
]
```

`core.urls` is included at `''` in `policycodex_site/urls.py`. The `policies/<slug:slug>/` pattern only matches paths beginning with `policies/`, so a new `htmx/` prefix cannot conflict with it; ordering is not load-bearing, but the `htmx/` include goes near the top for readability.

Setting `app_name = "htmx"` inside `core/htmx_urls.py` makes `include("core.htmx_urls")` register the `htmx` application namespace automatically (the modern Django idiom — no second arg to `include` needed). An empty `urlpatterns = []` is valid; the namespace is reserved and ready for APP-28c to fill.

**Scope guard (YAGNI):** Do NOT add any actual HTMX view or endpoint. The ticket is explicit: "no HTMX endpoints exist yet, so this lays the convention before they land." The module ships with an empty pattern list and a comment.

---

## File Structure

- `core/htmx_urls.py` — NEW. Owns the `htmx` application namespace; empty `urlpatterns` for now.
- `core/urls.py` — MODIFY. Switch the import to include `include`; add the `htmx/` include line.
- `core/tests/test_htmx_urls.py` — NEW. Asserts the module's namespace/emptiness and that the prefix is wired into `core.urls`.

---

### Task 1: Create the namespaced (empty) htmx URL module — test-first

**Files:**
- Create: `core/htmx_urls.py`
- Test: `core/tests/test_htmx_urls.py`

- [ ] **Step 1: Write the failing test**

Create `core/tests/test_htmx_urls.py` with:

```python
"""APP-27: the /htmx/ prefix convention is laid before any endpoints exist."""
from core import htmx_urls
from core import urls as core_urls


def test_htmx_urls_module_is_namespaced_and_empty():
    # The htmx fragment endpoints (APP-28c) will live here and reverse as
    # `htmx:<name>`. For now the namespace is reserved with no endpoints.
    assert htmx_urls.app_name == "htmx"
    assert htmx_urls.urlpatterns == []


def test_core_urls_includes_the_htmx_prefix():
    # The prefix must be wired into core.urls so a future JSON API at
    # /api/v1/ cannot collide with the HTMX fragment surface.
    prefixes = [str(p.pattern) for p in core_urls.urlpatterns]
    assert "htmx/" in prefixes
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `ai/venv/bin/python -m pytest core/tests/test_htmx_urls.py -v`
Expected: FAIL at import — `ModuleNotFoundError: No module named 'core.htmx_urls'`.

- [ ] **Step 3: Create the htmx URL module**

Create `core/htmx_urls.py` with:

```python
"""HTMX fragment routes for the core app, segregated under the /htmx/ prefix.

Keeping HTMX endpoints under their own namespaced prefix means a future JSON
API at /api/v1/ cannot collide, and the fragment endpoints retire cleanly if a
SPA replaces the server-rendered views. No endpoints exist yet (APP-27 lays the
convention); APP-28c adds the first ones (PDF upload -> live extraction,
typed-table row-add). New fragment views go here and reverse as `htmx:<name>`.
"""
from django.urls import path  # noqa: F401  (used once endpoints land)

app_name = "htmx"

urlpatterns = []
```

- [ ] **Step 4: Run the test to verify it still fails on the second assertion only**

Run: `ai/venv/bin/python -m pytest core/tests/test_htmx_urls.py -v`
Expected: `test_htmx_urls_module_is_namespaced_and_empty` PASSES; `test_core_urls_includes_the_htmx_prefix` still FAILS (`assert 'htmx/' in prefixes` — the include is not wired yet). This confirms Task 2 is the remaining work.

- [ ] **Step 5: Commit**

```bash
git add core/htmx_urls.py core/tests/test_htmx_urls.py
git commit -m "feat(app-27): add namespaced htmx URL module (empty, convention only)

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 2: Wire the `htmx/` prefix into `core/urls.py`

**Files:**
- Modify: `core/urls.py:2` (import) and `core/urls.py:7-20` (add the include)

- [ ] **Step 1: Confirm the still-failing test from Task 1**

Run: `ai/venv/bin/python -m pytest core/tests/test_htmx_urls.py::test_core_urls_includes_the_htmx_prefix -v`
Expected: FAIL — `assert 'htmx/' in prefixes`.

- [ ] **Step 2: Update the import in `core/urls.py`**

Change:

```python
from django.urls import path
```

to:

```python
from django.urls import include, path
```

- [ ] **Step 3: Add the `htmx/` include**

In `core/urls.py`, insert the include immediately after the `health/` line, so the block reads:

```python
urlpatterns = [
    path("", views.root_redirect, name="root"),
    path("health/", views.health, name="health"),
    # APP-27: HTMX fragment endpoints are segregated under /htmx/ (namespace
    # `htmx`). Empty for now; APP-28c adds the first fragment views.
    path("htmx/", include("core.htmx_urls")),
    path("catalog/", views.catalog, name="catalog"),
    path("policies/approve/", views.approve_pr, name="approve_pr"),
    path("policies/<slug:slug>/edit/", views.policy_edit, name="policy_edit"),
    path(
        "policies/<slug:slug>/foundational-edit/",
        views.foundational_edit,
        name="foundational_edit",
    ),
    path("policies/<slug:slug>/publish/", views.publish_policy, name="publish_policy"),
    path("policies/<slug:slug>/", views.policy_detail, name="policy_detail"),
]
```

- [ ] **Step 4: Run the htmx tests to verify they pass**

Run: `ai/venv/bin/python -m pytest core/tests/test_htmx_urls.py -v`
Expected: both tests PASS.

- [ ] **Step 5: Commit**

```bash
git add core/urls.py
git commit -m "feat(app-27): wire the /htmx/ prefix into core URLconf

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 3: Full-suite verification and close-out

**Files:** none (verification + bookkeeping).

- [ ] **Step 1: Run the full suite**

Run: `ai/venv/bin/python -m pytest -q`
Expected: PASS — suite rises from 495 by 2 (the two new tests) to 497, zero failures. The new include changes no existing route, so no existing test regresses.

- [ ] **Step 2: Sanity-check the URLconf loads and `/htmx/` 404s cleanly**

Run:
```bash
ai/venv/bin/python -c "import django, os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','policycodex_site.settings'); django.setup(); from django.urls import get_resolver; get_resolver().url_patterns; print('URLconf loads OK')"
```
Expected: `URLconf loads OK` (no `ImproperlyConfigured`/import error). An empty namespace include must not break URLconf loading.

- [ ] **Step 3: Mark APP-27 done on the tickets board**

In `PolicyWonk-v0.1-Tickets.md`, append a resolution note to the APP-27 row (date `2026-06-07`, the commit hashes, new suite count 497), matching the close-out style of surrounding resolved rows. Note the deliverable was a dedicated `core/htmx_urls.py` namespaced module wired at `htmx/`, no endpoints (per the ticket's "convention only" scope).

- [ ] **Step 4: Append a Daily Log entry**

In `internal/PolicyWonk-Daily-Log.md`, append a dated entry: APP-27 done — `/htmx/` prefix convention laid via `core/htmx_urls.py` (app_name `htmx`, empty urlpatterns) included at `htmx/` in `core/urls.py`; unblocks APP-28c live-HTMX endpoints; suite 495->497.

- [ ] **Step 5: Commit the bookkeeping**

```bash
git add PolicyWonk-v0.1-Tickets.md internal/PolicyWonk-Daily-Log.md internal/superpowers/plans/2026-06-07-app-27-htmx-url-prefix.md
git commit -m "docs(app-27): mark APP-27 done, log /htmx/ prefix convention

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Self-Review

**1. Spec coverage (ticket scope vs. tasks):**
- "Add an `/htmx/` URL prefix to `core/urls.py`" → Task 2 (`path("htmx/", include("core.htmx_urls"))`). ✔
- "so a future JSON API at `/api/v1/` does not collide" → the prefix segregates the HTMX surface; documented in both the module docstring and the urls comment. ✔
- "no HTMX endpoints exist yet, so this lays the convention before they land" → `urlpatterns = []`; scope guard forbids adding endpoints. ✔

**2. Placeholder scan:** No TBD/TODO/"handle edge cases"/"similar to Task N". All code shown in full. The lone `# noqa: F401` on the `path` import is intentional (it is unused until endpoints land; the import is pre-placed so APP-28c adds routes without touching imports). ✔

**3. Type/name consistency:** `app_name = "htmx"` matches the namespace asserted in the test and referenced as `htmx:<name>` in the docstring. The include target string `"core.htmx_urls"` matches the created module path `core/htmx_urls.py`. The test reads `core_urls.urlpatterns` patterns as `str(p.pattern)` and asserts `"htmx/"`, which is exactly what `path("htmx/", ...)` stringifies to. ✔
