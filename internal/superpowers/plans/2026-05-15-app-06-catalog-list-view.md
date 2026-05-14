# APP-06 Catalog List View Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A function-based Django view at `/catalog/` that reads the local working copy of the diocese's policy repo and renders foundational bundles + flat policies in one inventory list, with an empty-state for fresh installs.

**Architecture:** Function-based view (matches existing `core/views.py` `health` pattern; no CBV or model layer in this project). Composes `app/working_copy/config.load_working_copy_config()` → `BundleAwarePolicyReader(config.working_dir / "policies").read()` → list of `LogicalPolicy` → template context. Handles missing-config and missing-working-copy by rendering the catalog template with an `is_empty_onboarding=True` flag; no 500, no redirect, no crash. `@login_required` matches `LOGIN_URL = '/login/'` from `policycodex_site/settings.py`. Root `/` redirects to `/catalog/` (login required) to make the catalog the app's primary user-facing surface. This ticket also establishes `core/templates/base.html` as the project's first base layout template.

**Tech Stack:** Django 5+ function-based views, Django templates, pytest-django.

**Ticket reference:** `PolicyWonk-v0.1-Tickets.md` APP-06 line 43-44.

**BASE:** `main` at SHA `f6a65d3` (post-Wave-1 close, post-recipe docs).

**Discipline reminders:**
- TDD: every test must be observed-failing first.
- No em dashes anywhere in new content.
- Ship-generic: no `pt`, `PT`, `pensacola`, `tallahassee` tokens in template or view code (the catalog renders WHATEVER policies the working copy provides; it does not hardcode any diocese). Test fixtures use synthetic slugs.
- Tests use `pytest-django`'s `client` fixture (auto-provided) and the user/`force_login` pattern from `core/tests/test_auth.py`.

---

## File Structure

- Modify: `core/views.py` — add `catalog(request)` function and `root_redirect(request)` function.
- Modify: `core/urls.py` — add `/catalog/` route mapping to `catalog`; add root `''` route mapping to `root_redirect`.
- Create: `core/templates/base.html` — minimal HTML5 base layout with `{% block title %}` and `{% block content %}`; project's first base template. Header includes a sign-out link wired to `{% url 'logout' %}`.
- Create: `core/templates/catalog.html` — extends `base.html`; renders policies list with kind badges, foundational marker, title from frontmatter, and a placeholder detail link.
- Create: `core/tests/test_catalog.py` — pytest tests for view behavior (login required, empty states, render correctness, foundational marker, root redirect).

No other files touched. `app/working_copy/`, `ingest/`, settings.py — all read-only for this ticket.

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

Expected: BASE SHA `f6a65d3` or a descendant; branch is auto-worktree (`worktree-agent-<id>`); status clean.

- [ ] **Step 2: Merge `main` into your worktree branch**

```bash
git fetch
git merge main --no-edit
```

Expected: "Already up to date." or fast-forward to current `main`.

- [ ] **Step 3: Confirm baseline test suite green**

```bash
/Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest -q 2>&1 | tail -3
```

Expected: `156 passed` (or higher if APP-21 already merged; if so, expect `171 passed`).

**Capture the baseline number** for the final report.

- [ ] **Step 4: Read the existing patterns this ticket follows**

Read each of these files briefly to confirm signatures:

- `/Users/chuck/PolicyWonk/core/views.py` (the `health` function-based view pattern)
- `/Users/chuck/PolicyWonk/core/urls.py` (URL routing style)
- `/Users/chuck/PolicyWonk/core/tests/test_auth.py:8-17` (user fixture + `force_login` pattern)
- `/Users/chuck/PolicyWonk/core/tests/test_health.py:4-7` (simplest view-test pattern)
- `/Users/chuck/PolicyWonk/app/working_copy/config.py:11-39` (WorkingCopyConfig dataclass + load_working_copy_config function signatures)
- `/Users/chuck/PolicyWonk/ingest/policy_reader.py:22-66` (LogicalPolicy dataclass + BundleAwarePolicyReader API)

- [ ] **Step 5: No commit yet.**

---

## Task 2: Catalog URL + login-required + empty-state template (TDD)

**Files:**
- Modify: `core/views.py`
- Modify: `core/urls.py`
- Create: `core/templates/base.html`
- Create: `core/templates/catalog.html`
- Create: `core/tests/test_catalog.py`

- [ ] **Step 1: Write the failing tests**

Create `core/tests/test_catalog.py`:

```python
"""Tests for the catalog list view."""
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(username="reviewer", password="secret")


def test_catalog_url_resolves():
    assert reverse("catalog") == "/catalog/"


def test_catalog_requires_login(client):
    response = client.get("/catalog/")
    assert response.status_code == 302
    assert response.url.startswith("/login/")
    assert "next=/catalog/" in response.url


def test_catalog_empty_state_when_repo_url_unset(client, user):
    client.force_login(user)
    with override_settings(POLICYCODEX_POLICY_REPO_URL=""):
        response = client.get("/catalog/")
    assert response.status_code == 200
    body = response.content.decode()
    assert "No policies yet" in body
    # Onboarding hint should appear in the empty state.
    assert "pull_working_copy" in body or "onboarding" in body.lower()
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd /Users/chuck/PolicyWonk && /Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest core/tests/test_catalog.py -v 2>&1 | tail -10
```

Expected: `NoReverseMatch` for `catalog` URL name; the other tests fail at URL resolution too.

- [ ] **Step 3: Create `core/templates/base.html`**

Write:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{% block title %}PolicyCodex{% endblock %}</title>
  </head>
  <body>
    <header>
      <h1><a href="{% url 'catalog' %}">PolicyCodex</a></h1>
      {% if user.is_authenticated %}
        <nav>
          <span>Signed in as {{ user.username }}.</span>
          <form method="post" action="{% url 'logout' %}" style="display:inline">
            {% csrf_token %}
            <button type="submit">Sign out</button>
          </form>
        </nav>
      {% endif %}
    </header>
    <main>
      {% block content %}{% endblock %}
    </main>
    <footer>
      <small>PolicyCodex v0.1</small>
    </footer>
  </body>
</html>
```

- [ ] **Step 4: Create `core/templates/catalog.html`**

Write:

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
      {% for policy in policies %}
        <li class="policy">
          <a href="#{{ policy.slug }}">{{ policy.frontmatter.title|default:policy.slug }}</a>
          <span class="kind-badge kind-{{ policy.kind }}">{{ policy.kind }}</span>
          {% if policy.foundational %}
            <span class="foundational-badge">(foundational)</span>
          {% endif %}
        </li>
      {% empty %}
        <li class="no-results">No policies in the working copy.</li>
      {% endfor %}
    </ul>
  {% endif %}
{% endblock %}
```

- [ ] **Step 5: Implement the view (empty-state path only for now)**

Open `core/views.py` and add to the end:

```python
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from app.working_copy.config import load_working_copy_config
from ingest.policy_reader import BundleAwarePolicyReader


@login_required
def catalog(request):
    """Render the policy inventory from the local working copy.

    Falls back to an empty-state template when the working copy is not
    yet configured (fresh install before onboarding) or not yet synced.
    """
    try:
        config = load_working_copy_config()
    except RuntimeError:
        return render(request, "catalog.html", {"is_empty_onboarding": True, "policies": []})

    policies_dir = config.working_dir / "policies"
    if not policies_dir.exists():
        return render(request, "catalog.html", {"is_empty_onboarding": True, "policies": []})

    policies = list(BundleAwarePolicyReader(policies_dir).read())
    return render(request, "catalog.html", {"is_empty_onboarding": False, "policies": policies})
```

If `core/views.py` already imports `from django.http import JsonResponse` (for the `health` view), leave that alone. The new imports above are additive.

- [ ] **Step 6: Wire the URL**

Open `core/urls.py`. Confirm the current content (should be the `health` view's URL). Add the catalog URL. The file should end up looking like (preserving existing entries):

```python
"""URL routes for the core app."""
from django.urls import path

from . import views


urlpatterns = [
    path("health/", views.health, name="health"),
    path("catalog/", views.catalog, name="catalog"),
]
```

Verify by `cat`-ing the file after the edit.

- [ ] **Step 7: Run to confirm pass**

```bash
/Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest core/tests/test_catalog.py -v 2>&1 | tail -10
```

Expected: 3 tests passing (`test_catalog_url_resolves`, `test_catalog_requires_login`, `test_catalog_empty_state_when_repo_url_unset`).

- [ ] **Step 8: Commit**

```bash
git add core/views.py core/urls.py core/templates/base.html core/templates/catalog.html core/tests/test_catalog.py
git commit -m "feat(APP-06): catalog URL + login_required + empty-state template"
```

---

## Task 3: Render policies from the working copy (TDD)

**Files:**
- Modify: `core/tests/test_catalog.py`

The view already handles the happy path (Task 2 implementation uses `BundleAwarePolicyReader`). This task adds tests for the rendering behavior with mocked policy data.

- [ ] **Step 1: Write the failing tests**

Append to `core/tests/test_catalog.py`:

```python
def _stub_policy(*, slug, kind="flat", title=None, foundational=False, provides=()):
    """Build a stand-in for an ingest.policy_reader.LogicalPolicy."""
    from pathlib import Path
    from ingest.policy_reader import LogicalPolicy
    pp = Path(f"/tmp/policies/{slug}.md") if kind == "flat" else Path(f"/tmp/policies/{slug}/policy.md")
    return LogicalPolicy(
        slug=slug,
        kind=kind,
        policy_path=pp,
        data_path=None if kind == "flat" else pp.parent / "data.yaml",
        frontmatter={"title": title or slug.replace("-", " ").title()},
        body="",
        foundational=foundational,
        provides=provides,
    )


def test_catalog_renders_policies_when_working_copy_exists(client, user):
    """Three policies (2 flat, 1 bundle) render with their titles."""
    client.force_login(user)
    policies = [
        _stub_policy(slug="onboarding", kind="flat", title="New Employee Onboarding"),
        _stub_policy(slug="code-of-conduct", kind="flat", title="Code of Conduct"),
        _stub_policy(
            slug="retention",
            kind="bundle",
            title="Document Retention Policy",
            foundational=True,
            provides=("classifications", "retention-schedule"),
        ),
    ]
    with override_settings(
        POLICYCODEX_POLICY_REPO_URL="https://example.com/x.git",
        POLICYCODEX_POLICY_BRANCH="main",
        POLICYCODEX_WORKING_COPY_ROOT="/tmp",
    ):
        with patch("core.views.Path.exists", return_value=True):
            with patch("core.views.BundleAwarePolicyReader") as MockReader:
                MockReader.return_value.read.return_value = iter(policies)
                response = client.get("/catalog/")

    assert response.status_code == 200
    body = response.content.decode()
    assert "New Employee Onboarding" in body
    assert "Code of Conduct" in body
    assert "Document Retention Policy" in body


def test_catalog_distinguishes_flat_from_bundle(client, user):
    """Both kind badges appear in the rendered list."""
    client.force_login(user)
    policies = [
        _stub_policy(slug="flat-one", kind="flat"),
        _stub_policy(slug="bundle-one", kind="bundle", foundational=True, provides=("classifications",)),
    ]
    with override_settings(
        POLICYCODEX_POLICY_REPO_URL="https://example.com/x.git",
        POLICYCODEX_WORKING_COPY_ROOT="/tmp",
    ):
        with patch("core.views.Path.exists", return_value=True):
            with patch("core.views.BundleAwarePolicyReader") as MockReader:
                MockReader.return_value.read.return_value = iter(policies)
                response = client.get("/catalog/")

    body = response.content.decode()
    assert "flat" in body.lower()
    assert "bundle" in body.lower()


def test_catalog_marks_foundational_bundles(client, user):
    """The `(foundational)` marker appears on foundational policies only."""
    client.force_login(user)
    policies = [
        _stub_policy(slug="plain", kind="flat", foundational=False),
        _stub_policy(
            slug="retention",
            kind="bundle",
            title="Retention Bundle",
            foundational=True,
            provides=("classifications", "retention-schedule"),
        ),
    ]
    with override_settings(
        POLICYCODEX_POLICY_REPO_URL="https://example.com/x.git",
        POLICYCODEX_WORKING_COPY_ROOT="/tmp",
    ):
        with patch("core.views.Path.exists", return_value=True):
            with patch("core.views.BundleAwarePolicyReader") as MockReader:
                MockReader.return_value.read.return_value = iter(policies)
                response = client.get("/catalog/")

    body = response.content.decode()
    # The bundle policy's section in the body should contain the marker;
    # the flat policy's should not.
    assert "(foundational)" in body
    # Crude check: the marker appears exactly once, attached to "Retention Bundle".
    assert body.count("(foundational)") == 1


def test_catalog_empty_state_when_policies_dir_missing(client, user):
    """When config resolves but policies_dir does not exist, show empty state."""
    client.force_login(user)
    with override_settings(
        POLICYCODEX_POLICY_REPO_URL="https://example.com/x.git",
        POLICYCODEX_WORKING_COPY_ROOT="/tmp",
    ):
        with patch("core.views.Path.exists", return_value=False):
            response = client.get("/catalog/")

    assert response.status_code == 200
    body = response.content.decode()
    assert "No policies yet" in body
```

- [ ] **Step 2: Run to confirm pass**

```bash
/Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest core/tests/test_catalog.py -v 2>&1 | tail -15
```

Expected: 7 passing (3 from Task 2 + 4 new). All new tests pass against the Task 2 implementation, which already calls `BundleAwarePolicyReader`.

If any tests fail, debug the `patch("core.views.Path.exists", ...)` target — `Path` must be imported into `core.views`'s namespace for the patch to take effect. The Task 2 implementation imports `from ingest.policy_reader import BundleAwarePolicyReader` and `from app.working_copy.config import load_working_copy_config`, neither of which exposes `Path`. The patches in these tests target `core.views.Path` directly, which the implementation needs to import as well. Fix: add `from pathlib import Path` to the top of `core/views.py` if it is not already imported. (The implementation uses `config.working_dir / "policies"` which returns a `Path` from the dataclass property, so `Path` itself does not strictly need to be in the views module's namespace UNLESS the tests patch it there. Make the import unconditional to support the tests.)

If the import was missing, add it now, then re-run the tests.

- [ ] **Step 3: Commit**

```bash
git add core/views.py core/tests/test_catalog.py
git commit -m "feat(APP-06): render policies + foundational marker + missing-dir empty state"
```

---

## Task 4: Root redirect `/` → `/catalog/` (TDD)

**Files:**
- Modify: `core/views.py`
- Modify: `core/urls.py`
- Modify: `policycodex_site/urls.py` (only if root is currently bound there)
- Modify: `core/tests/test_catalog.py`

- [ ] **Step 1: Inspect current root URL handling**

```bash
grep -n "path\|root\|''" /Users/chuck/PolicyWonk/policycodex_site/urls.py
grep -n "path\|''" /Users/chuck/PolicyWonk/core/urls.py
```

Capture the current routing. The root `/` should currently produce a 404 (no view registered for `''`). If something IS bound to `''`, STOP and surface the situation; the plan assumes a clean root.

- [ ] **Step 2: Write the failing tests**

Append to `core/tests/test_catalog.py`:

```python
def test_root_redirects_authenticated_user_to_catalog(client, user):
    """For an authenticated user, GET / redirects to /catalog/."""
    client.force_login(user)
    response = client.get("/")
    assert response.status_code == 302
    assert response.url == "/catalog/"


def test_root_redirects_unauthenticated_user_to_login(client):
    """For an unauthenticated user, GET / redirects to /catalog/ first, which then
    redirects to /login/. We assert the immediate redirect target is /catalog/
    (the @login_required chain happens at /catalog/, not at /)."""
    response = client.get("/")
    assert response.status_code == 302
    assert response.url == "/catalog/"
    # Follow the chain.
    response = client.get(response.url)
    assert response.status_code == 302
    assert response.url.startswith("/login/")
```

- [ ] **Step 3: Run to confirm failure**

```bash
/Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest core/tests/test_catalog.py -v -k root 2>&1 | tail -10
```

Expected: 404 on the GET / call (no route registered).

- [ ] **Step 4: Add the redirect view**

Append to `core/views.py`:

```python
from django.shortcuts import redirect


def root_redirect(request):
    """Send the root URL `/` to `/catalog/`. `catalog` itself handles login_required."""
    return redirect("catalog")
```

- [ ] **Step 5: Wire the URL**

Open `policycodex_site/urls.py`. Find the root `urlpatterns` list. Add the root route at the top of the list. Example final shape (preserving existing entries; the exact existing content varies):

```python
from django.contrib import admin
from django.urls import include, path

from core import views as core_views


urlpatterns = [
    path("", core_views.root_redirect, name="root"),
    # ... existing entries (admin, login, logout, include("core.urls"), etc.) ...
]
```

If the existing `policycodex_site/urls.py` has a different structure, integrate the `path("", ...)` line into the existing `urlpatterns` list at the appropriate place (must come BEFORE any catch-all routes if any exist).

If the existing pattern is to include `core.urls` and put the root inside `core/urls.py` instead, that also works. Pick ONE place; do not duplicate.

- [ ] **Step 6: Run to confirm pass**

```bash
/Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest core/tests/test_catalog.py -v 2>&1 | tail -12
```

Expected: 9 passing (the 7 from Tasks 2-3 plus 2 new).

- [ ] **Step 7: Commit**

```bash
git add core/views.py policycodex_site/urls.py core/tests/test_catalog.py
git commit -m "feat(APP-06): redirect / to /catalog/ for the app's primary surface"
```

---

## Task 5: Final verification + smoke + handoff

**Files:**
- None modified.

- [ ] **Step 1: Confirm full repo test suite green**

```bash
cd /Users/chuck/PolicyWonk && /Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest -q 2>&1 | tail -3
```

Expected: baseline + 9 new tests passing. (If APP-21 also merged before APP-06, baseline is 171; APP-06 adds 9 for a total of 180. If APP-06 is dispatched first, baseline is 156; total 165.)

Capture the exact number.

- [ ] **Step 2: Confirm `manage.py check` still clean**

```bash
/Users/chuck/PolicyWonk/spike/venv/bin/python manage.py check 2>&1 | tail -3
```

Expected: `System check identified no issues (0 silenced).` (If APP-21 has merged and `POLICYCODEX_POLICY_REPO_URL` is unset, expect ONE Warning from APP-21; that is still exit 0.)

- [ ] **Step 3: Optional smoke against the live PT bundle**

If GitHub App credentials are available and you want to do a manual UI smoke:

```bash
cd /Users/chuck/PolicyWonk
export POLICYCODEX_POLICY_REPO_URL="https://github.com/Diocese-of-Pensacola-Tallahassee/pt-policy.git"
export POLICYCODEX_POLICY_BRANCH=main
export POLICYCODEX_WORKING_COPY_ROOT=/tmp/app06-smoke
/Users/chuck/PolicyWonk/spike/venv/bin/python manage.py pull_working_copy
# Create a superuser if one does not exist:
echo "from django.contrib.auth.models import User; User.objects.filter(username='admin').exists() or User.objects.create_user('admin', 'admin@example.com', 'admin')" | /Users/chuck/PolicyWonk/spike/venv/bin/python manage.py shell
# Start the server in the background and curl it:
/Users/chuck/PolicyWonk/spike/venv/bin/python manage.py runserver &
SERVER_PID=$!
sleep 2
curl -s -L http://127.0.0.1:8000/ -c /tmp/cookies.txt | head -20
# Login + visit catalog:
curl -s -X POST http://127.0.0.1:8000/login/ -d "username=admin&password=admin" -b /tmp/cookies.txt -c /tmp/cookies.txt
curl -s http://127.0.0.1:8000/catalog/ -b /tmp/cookies.txt | grep -E "Document Retention|foundational"
kill $SERVER_PID
```

Expected: the catalog renders, contains "Document Retention Policy" (from the PT bundle), contains the "(foundational)" marker.

If credentials are not available, SKIP this step. The unit tests are authoritative.

- [ ] **Step 4: Confirm clean branch + commit history**

```bash
git status
git log --oneline main..HEAD
```

Expected: clean working tree; 3 commits since BASE `f6a65d3`:

1. `feat(APP-06): catalog URL + login_required + empty-state template`
2. `feat(APP-06): render policies + foundational marker + missing-dir empty state`
3. `feat(APP-06): redirect / to /catalog/ for the app's primary surface`

If counts differ, surface in the self-report.

- [ ] **Step 5: Compose self-report**

Cover:
- Goal in one sentence.
- Branch name (`worktree-agent-<id>`) and final commit SHA.
- Files created / modified.
- Commit list.
- Test count before / after.
- `manage.py check` result.
- Smoke result (Step 3): PASS / SKIPPED / FAIL.
- Any deviations from the plan + rationale.
- Status: DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT.

- [ ] **Step 6: Handoff**

Do not merge to main. Do not push. The dispatching session will run spec-compliance and code-quality review per `superpowers:subagent-driven-development`.

---

## Definition of Done

- `core/views.py` has `catalog(request)` decorated with `@login_required` AND `root_redirect(request)`.
- `core/urls.py` has `path("catalog/", views.catalog, name="catalog")`.
- Root `/` is bound to `root_redirect` (in `policycodex_site/urls.py` OR `core/urls.py`, but not both).
- `core/templates/base.html` exists with `{% block title %}`, `{% block content %}`, and a sign-out form.
- `core/templates/catalog.html` extends `base.html`, renders the policies list with kind badges and a `(foundational)` marker on foundational policies, and renders an "No policies yet" empty state when `is_empty_onboarding` is True.
- `core/tests/test_catalog.py` has 9 tests passing: URL resolves, login required, empty-state (unset URL), empty-state (missing dir), happy-path render, kind distinction, foundational marker, root redirect (auth), root redirect (unauth).
- Empty-state handling covers BOTH `RuntimeError` from `load_working_copy_config` (env var unset) AND `policies_dir.exists() is False` (working copy not yet synced). The reader is NOT called in either case.
- 3 commits on the branch since BASE, all with `APP-06` in the message.
- No edits outside the 5 files in **File Structure**.
- No em dashes anywhere in new content.
- No PT-specific tokens in `core/views.py`, the templates, or the test file. PT names appear ONLY in the optional smoke env exports in Task 5 Step 3.

---

## Self-Review

**Spec coverage:**
- Ticket says "Catalog list view reading from local working copy of the policy repo" → Task 2 (URL + view + base behavior), Task 3 (real data path) ✓
- Foundational-policy design says catalog must render both bundles and flat files in one inventory → Task 3 test `test_catalog_distinguishes_flat_from_bundle` ✓
- Foundational marker required for downstream APP-20 (UI delete-gate) → Task 3 test `test_catalog_marks_foundational_bundles` ✓
- Chuck's decision: empty-state on missing working copy (no 500, no redirect) → Task 2 + Task 3 cover both empty-state paths ✓
- Chuck's decision: root redirect / → /catalog/ → Task 4 ✓
- Authentication via `@login_required` (matches APP-02's wired auth) → Task 2 ✓
- This ticket establishes the project's first base template → Task 2 Step 3 ✓

**Placeholder scan:** No "TODO", no "TBD", no "implement later". Every step has a code block where code is needed. Every test has assertions. Every template has actual HTML.

**Type consistency:**
- `LogicalPolicy` fields (`slug`, `kind`, `policy_path`, `data_path`, `frontmatter`, `body`, `foundational`, `provides`) used consistently in `_stub_policy` helper and template.
- View function signature `catalog(request)` consistent across views.py, urls.py, and test reverses (`"catalog"` URL name).
- Template variable names (`policies`, `is_empty_onboarding`) used identically in view context and template.
- The `(foundational)` marker text is fixed across the template and the test assertion `assert "(foundational)" in body`.

**Potential gotcha (already flagged):** Task 3 Step 2 has a debug note about `core.views.Path` import for the test patches to work. Implementer must add the explicit `from pathlib import Path` import to `core/views.py` even though the implementation does not strictly need it (the test patches rely on it being in the module namespace).

No other issues found.
