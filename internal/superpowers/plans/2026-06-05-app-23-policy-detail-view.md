# APP-23: Read-Only Policy Detail View + L1 Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `/policies/<slug>/` read-only detail view (title, metadata, `provides:`, body, gate state) carrying the same L1 foundational gate as the catalog, and turn the catalog's dead `#slug` anchor into a real link to it.

**Architecture:** A new `policy_detail` view in `core/views.py` reuses the existing `_find_policy(slug)` and `_build_gate_lookup(working_dir)` helpers, renders a new `core/templates/policy_detail.html`, and 404s on unknown slugs. The L1 gate mirrors the catalog branch exactly: foundational policies show the typed-table-editor banner + `foundational_edit` link and hide the flat-edit link; non-foundational policies show the ordinary `policy_edit` link. No mutation happens in this view.

**Tech Stack:** Django 5+ (function view + template), pytest-django. No new dependencies.

---

## Context for the implementer

You are working in the PolicyCodex repo — a Django app that manages a Catholic diocese's policy documents stored as markdown in a Git repo. You have **zero** context beyond this plan; everything you need is below.

**Run tests with this exact interpreter** (there is no root venv; system python lacks pytest):

```
ai/venv/bin/python -m pytest <args>
```

**Key existing code you will reuse (already on `main`, do not modify unless a step says so):**

- `core/views.py`
  - `_find_policy(slug)` → returns a `LogicalPolicy` for the slug or `None`. It composes `load_working_copy_config()` + `BundleAwarePolicyReader(policies_dir).read()` and matches `policy.slug == slug`. Returns `None` on any infrastructure problem (no config, missing dir, slug not found).
  - `_build_gate_lookup(working_dir)` → returns a `{slug: gate}` dict by calling `GitHubProvider().list_open_prs(...)`. **Degrades to `{}`** (every policy treated as `published`) on any provider failure. Gate strings are `"drafted"`, `"reviewed"`, `"published"`.
  - `load_working_copy_config()` (imported from `app.working_copy.config`) → returns a config object with `.working_dir` (a `Path`) and `.branch`. Raises `RuntimeError` when the working copy is not configured.
- `ingest/policy_reader.py` — `LogicalPolicy` is a frozen dataclass with fields: `slug: str`, `kind: str` (`"flat"` or `"bundle"`), `policy_path: Path`, `data_path: Path | None`, `frontmatter: Mapping[str, object]`, `body: str`, `foundational: bool`, `provides: tuple[str, ...]`.
- `core/urls.py` — current routes include `policies/approve/`, `policies/<slug:slug>/edit/`, `policies/<slug:slug>/foundational-edit/`, `policies/<slug:slug>/publish/`. URL **names**: `catalog`, `policy_edit`, `foundational_edit`, `publish_policy`, `approve_pr`.
- `core/templates/catalog.html` — line 47 currently renders a **dead** anchor: `<a href="#{{ row.policy.slug }}">{{ row.policy.frontmatter.title|default:row.policy.slug }}</a>`. The catalog's L1 gate block (lines 63-67) is the pattern to mirror: foundational → `action-edit-foundational` link to `foundational_edit`; else → `action-edit` link to `policy_edit`.
- `core/templates/base.html` — provides `{% block title %}` and `{% block content %}`, renders `messages`, and a header/footer. Extend it.

**Key decisions already locked (do not reopen):**

1. **Body is rendered as escaped preformatted text** (`<pre>{{ policy.body }}</pre>`), NOT as rendered markdown. There is no markdown library in the dependency set, and the public rendered view is the Astro handbook. This admin detail view is for inspection; Django auto-escaping inside `<pre>` keeps it XSS-safe and dependency-free.
2. **Gate is computed by reusing `_build_gate_lookup`** (one `list_open_prs` call), not a new code path. On any failure it defaults to `"published"`, identical to the catalog.
3. **The detail route is registered LAST** in `urlpatterns` so the more-specific `edit/`, `foundational-edit/`, `publish/`, and the explicit `approve/` routes keep precedence. (`policies/<slug:slug>/` cannot match a URL that has an extra trailing segment like `/edit/`, and `policies/approve/` is declared earlier, so this is belt-and-suspenders.)
4. **L1 gate is presentation-only** here, exactly like the catalog: it hides/show the edit affordance. The server-side 403 already lives in `policy_edit` (foundational slugs are refused there); this view never mutates, so it needs no server-side guard.

---

## File Structure

- **Modify** `core/urls.py` — add the `policy_detail` route (named `policy_detail`), registered last.
- **Modify** `core/views.py` — add the `policy_detail` view function.
- **Create** `core/templates/policy_detail.html` — the read-only detail template, grown across Tasks 1-3.
- **Create** `core/tests/test_policy_detail.py` — the view + template tests.
- **Modify** `core/templates/catalog.html` — replace the dead `#slug` anchor (line 47) with a real `policy_detail` link.
- **Modify** `core/tests/test_catalog.py` — add one test asserting the catalog row links to the detail view.

---

## Task 1: Route + view + minimal template (skeleton, 404, login)

**Files:**
- Modify: `core/urls.py`
- Modify: `core/views.py`
- Create: `core/templates/policy_detail.html`
- Create: `core/tests/test_policy_detail.py`

- [ ] **Step 1: Write the failing tests**

Create `core/tests/test_policy_detail.py`:

```python
"""Tests for the read-only policy detail view (APP-23)."""
from pathlib import Path
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse

from ingest.policy_reader import LogicalPolicy

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(username="reviewer", password="secret")


def _stub_policy(
    *, slug, kind="flat", title=None, body="",
    foundational=False, provides=(), frontmatter=None,
):
    """Build a stand-in for an ingest.policy_reader.LogicalPolicy."""
    pp = (
        Path(f"/tmp/policies/{slug}.md")
        if kind == "flat"
        else Path(f"/tmp/policies/{slug}/policy.md")
    )
    fm = {"title": title or slug.replace("-", " ").title()}
    if frontmatter:
        fm.update(frontmatter)
    return LogicalPolicy(
        slug=slug,
        kind=kind,
        policy_path=pp,
        data_path=None if kind == "flat" else pp.parent / "data.yaml",
        frontmatter=fm,
        body=body,
        foundational=foundational,
        provides=provides,
    )


def _get_detail(client, slug, policies, open_prs=None):
    """GET /policies/<slug>/ with the working copy + reader + provider stubbed."""
    with override_settings(
        POLICYCODEX_POLICY_REPO_URL="https://example.com/x.git",
        POLICYCODEX_POLICY_BRANCH="main",
        POLICYCODEX_WORKING_COPY_ROOT="/tmp",
    ):
        with patch("core.views.Path.exists", return_value=True):
            with patch("core.views.BundleAwarePolicyReader") as MockReader:
                MockReader.return_value.read.return_value = iter(policies)
                with patch("core.views.GitHubProvider") as MockProvider:
                    MockProvider.return_value.list_open_prs.return_value = open_prs or []
                    return client.get(f"/policies/{slug}/")


def test_policy_detail_url_resolves():
    assert reverse("policy_detail", kwargs={"slug": "onboarding"}) == "/policies/onboarding/"


def test_policy_detail_requires_login(client):
    response = client.get("/policies/onboarding/")
    assert response.status_code == 302
    assert response.url.startswith("/login/")
    assert "next=/policies/onboarding/" in response.url


def test_policy_detail_404_for_unknown_slug(client, user):
    client.force_login(user)
    policies = [_stub_policy(slug="something-else", kind="flat")]
    response = _get_detail(client, "no-such-policy", policies)
    assert response.status_code == 404


def test_policy_detail_renders_title(client, user):
    client.force_login(user)
    policies = [_stub_policy(slug="onboarding", kind="flat", title="New Employee Onboarding")]
    response = _get_detail(client, "onboarding", policies)
    assert response.status_code == 200
    assert "New Employee Onboarding" in response.content.decode()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `ai/venv/bin/python -m pytest core/tests/test_policy_detail.py -q`
Expected: FAIL — `policy_detail` is not a registered URL name (`NoReverseMatch`) and `/policies/onboarding/` 404s at the routing layer.

- [ ] **Step 3: Add the view**

In `core/views.py`, add this function (place it after `policy_edit` and before `foundational_edit`, or anywhere among the view functions — it only needs `_find_policy`, `_build_gate_lookup`, `load_working_copy_config`, `Http404`, `render`, all already imported at the top of the file):

```python
@login_required
def policy_detail(request, slug):
    """Read-only detail view for a single policy (APP-23).

    Renders the title, frontmatter, provides:, body, and gate state. Applies
    the same L1 foundational gate as the catalog: foundational policies show
    the typed-table-editor banner and no flat-edit affordance; non-foundational
    policies show an Edit link. This view never mutates.
    """
    policy = _find_policy(slug)
    if policy is None:
        raise Http404(f"Policy not found: {slug}")

    # Reuse the catalog's gate lookup so the detail badge matches the list
    # badge exactly. Degrades to "published" on any provider/config failure.
    try:
        config = load_working_copy_config()
        gate = _build_gate_lookup(config.working_dir).get(slug, "published")
    except RuntimeError:
        gate = "published"

    return render(request, "policy_detail.html", {"policy": policy, "gate": gate})
```

- [ ] **Step 4: Register the route**

In `core/urls.py`, add this as the **last** entry of `urlpatterns` (after the `publish/` route):

```python
    path("policies/<slug:slug>/", views.policy_detail, name="policy_detail"),
```

- [ ] **Step 5: Create the minimal template**

Create `core/templates/policy_detail.html`:

```html
{% extends "base.html" %}

{% block title %}{{ policy.frontmatter.title|default:policy.slug }} | PolicyCodex{% endblock %}

{% block content %}
  <h2>{{ policy.frontmatter.title|default:policy.slug }}</h2>
  <p class="policy-slug"><code>policies/{{ policy.slug }}</code></p>

  <p><a href="{% url 'catalog' %}">Back to catalog</a></p>
{% endblock %}
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `ai/venv/bin/python -m pytest core/tests/test_policy_detail.py -q`
Expected: PASS (4 tests).

- [ ] **Step 7: Commit**

```bash
git add core/urls.py core/views.py core/templates/policy_detail.html core/tests/test_policy_detail.py
git commit -m "feat(core): read-only policy detail view route + skeleton (APP-23)"
```

---

## Task 2: Render metadata, provides, body, and gate badge

**Files:**
- Modify: `core/templates/policy_detail.html`
- Modify: `core/tests/test_policy_detail.py`

- [ ] **Step 1: Write the failing tests**

Append to `core/tests/test_policy_detail.py`:

```python
def test_policy_detail_renders_body(client, user):
    client.force_login(user)
    body = "## Purpose\n\nThis policy governs onboarding."
    policies = [_stub_policy(slug="onboarding", kind="flat", body=body)]
    response = _get_detail(client, "onboarding", policies)
    content = response.content.decode()
    assert "This policy governs onboarding." in content


def test_policy_detail_renders_frontmatter_metadata(client, user):
    client.force_login(user)
    policies = [_stub_policy(
        slug="onboarding",
        kind="flat",
        title="Onboarding",
        frontmatter={"owner": "HR Director", "effective_date": "2026-01-01"},
    )]
    response = _get_detail(client, "onboarding", policies)
    content = response.content.decode()
    assert "owner" in content
    assert "HR Director" in content
    assert "effective_date" in content
    assert "2026-01-01" in content


def test_policy_detail_shows_provides_for_foundational(client, user):
    client.force_login(user)
    policies = [_stub_policy(
        slug="document-retention",
        kind="bundle",
        title="Document Retention",
        foundational=True,
        provides=("classifications", "retention-schedule"),
    )]
    response = _get_detail(client, "document-retention", policies)
    content = response.content.decode()
    assert "classifications" in content
    assert "retention-schedule" in content


def test_policy_detail_omits_provides_for_non_foundational(client, user):
    client.force_login(user)
    policies = [_stub_policy(slug="onboarding", kind="flat")]
    response = _get_detail(client, "onboarding", policies)
    content = response.content.decode()
    assert "Provides" not in content


def test_policy_detail_shows_gate_badge(client, user):
    client.force_login(user)
    policies = [_stub_policy(slug="onboarding", kind="flat")]
    open_prs = [{
        "pr_number": 3,
        "head_branch": "policycodex/draft-onboarding",
        "gate": "drafted",
        "url": "https://example.com/p/3",
    }]
    response = _get_detail(client, "onboarding", policies, open_prs=open_prs)
    content = response.content.decode()
    assert "gate-drafted" in content
    assert "Drafted" in content


def test_policy_detail_defaults_to_published_gate(client, user):
    client.force_login(user)
    policies = [_stub_policy(slug="onboarding", kind="flat")]
    response = _get_detail(client, "onboarding", policies, open_prs=[])
    content = response.content.decode()
    assert "gate-published" in content
    assert "Published" in content
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `ai/venv/bin/python -m pytest core/tests/test_policy_detail.py -q`
Expected: FAIL — the minimal template renders neither body, metadata, provides, nor gate badge.

- [ ] **Step 3: Grow the template**

Replace the entire contents of `core/templates/policy_detail.html` with:

```html
{% extends "base.html" %}

{% block title %}{{ policy.frontmatter.title|default:policy.slug }} | PolicyCodex{% endblock %}

{% block content %}
  <h2>{{ policy.frontmatter.title|default:policy.slug }}</h2>
  <p class="policy-slug"><code>policies/{{ policy.slug }}</code></p>

  <p class="badges">
    <span class="kind-badge kind-{{ policy.kind }}">{{ policy.kind }}</span>
    {% if policy.foundational %}
      <span class="foundational-badge">(foundational)</span>
    {% endif %}
    <span class="gate-badge gate-{{ gate }}">{{ gate|title }}</span>
  </p>

  {% if policy.foundational and policy.provides %}
    <section class="provides">
      <h3>Provides</h3>
      <ul>
        {% for item in policy.provides %}
          <li>{{ item }}</li>
        {% endfor %}
      </ul>
    </section>
  {% endif %}

  <section class="frontmatter">
    <h3>Metadata</h3>
    <table>
      <tbody>
        {% for key, value in policy.frontmatter.items %}
          <tr><th>{{ key }}</th><td>{{ value }}</td></tr>
        {% endfor %}
      </tbody>
    </table>
  </section>

  <section class="policy-body">
    <h3>Document</h3>
    <pre>{{ policy.body }}</pre>
  </section>

  <p><a href="{% url 'catalog' %}">Back to catalog</a></p>
{% endblock %}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `ai/venv/bin/python -m pytest core/tests/test_policy_detail.py -q`
Expected: PASS (10 tests).

- [ ] **Step 5: Commit**

```bash
git add core/templates/policy_detail.html core/tests/test_policy_detail.py
git commit -m "feat(core): render metadata, provides, body, gate badge on detail view (APP-23)"
```

---

## Task 3: L1 foundational gate (edit affordances)

**Files:**
- Modify: `core/templates/policy_detail.html`
- Modify: `core/tests/test_policy_detail.py`

- [ ] **Step 1: Write the failing tests**

Append to `core/tests/test_policy_detail.py`:

```python
def test_policy_detail_non_foundational_shows_edit_link(client, user):
    client.force_login(user)
    policies = [_stub_policy(slug="onboarding", kind="flat", title="Onboarding")]
    response = _get_detail(client, "onboarding", policies)
    content = response.content.decode()
    assert 'href="/policies/onboarding/edit/"' in content
    assert "action-edit-foundational" not in content


def test_policy_detail_foundational_hides_flat_edit_shows_typed_table(client, user):
    client.force_login(user)
    policies = [_stub_policy(
        slug="document-retention",
        kind="bundle",
        title="Document Retention",
        foundational=True,
        provides=("classifications",),
    )]
    response = _get_detail(client, "document-retention", policies)
    content = response.content.decode()
    # Flat-edit link is hidden for foundational policies.
    assert 'href="/policies/document-retention/edit/"' not in content
    # The typed-table editor link + banner are present instead.
    assert "action-edit-foundational" in content
    assert 'href="/policies/document-retention/foundational-edit/"' in content
    assert "typed-table" in content
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `ai/venv/bin/python -m pytest core/tests/test_policy_detail.py -q`
Expected: FAIL — the template has no actions block yet, so neither edit link renders.

- [ ] **Step 3: Add the L1 actions block to the template**

In `core/templates/policy_detail.html`, insert this block immediately **before** the `<p><a href="{% url 'catalog' %}">Back to catalog</a></p>` line:

```html
  {# L1 foundational gate (APP-20/APP-23): foundational policies edit only #}
  {# through the typed-table UI; flat policies show the ordinary edit link. #}
  {# This view never mutates; the server-side 403 lives in policy_edit. #}
  <p class="actions">
    {% if policy.foundational %}
      <span class="foundational-banner">
        This policy is foundational; edit through the typed-table UI.
      </span>
      <a class="action-edit-foundational" href="{% url 'foundational_edit' slug=policy.slug %}">Edit (typed table)</a>
    {% else %}
      <a class="action-edit" href="{% url 'policy_edit' slug=policy.slug %}">Edit</a>
    {% endif %}
  </p>

```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `ai/venv/bin/python -m pytest core/tests/test_policy_detail.py -q`
Expected: PASS (12 tests).

- [ ] **Step 5: Commit**

```bash
git add core/templates/policy_detail.html core/tests/test_policy_detail.py
git commit -m "feat(core): L1 foundational gate on detail view edit affordances (APP-23)"
```

---

## Task 4: Wire the catalog row to the detail view

**Files:**
- Modify: `core/templates/catalog.html:47`
- Modify: `core/tests/test_catalog.py`

- [ ] **Step 1: Write the failing test**

Append to `core/tests/test_catalog.py` (the `_stub_policy` helper and `stub_gh_provider` fixture already exist in that file):

```python
def test_catalog_row_links_to_detail_view(client, user, stub_gh_provider):
    """The policy-title anchor points at the real detail URL, not a dead #slug."""
    client.force_login(user)
    policies = [_stub_policy(slug="onboarding", kind="flat", title="Onboarding")]
    with override_settings(
        POLICYCODEX_POLICY_REPO_URL="https://example.com/x.git",
        POLICYCODEX_WORKING_COPY_ROOT="/tmp",
    ):
        with patch("core.views.Path.exists", return_value=True):
            with patch("core.views.BundleAwarePolicyReader") as MockReader:
                MockReader.return_value.read.return_value = iter(policies)
                response = client.get("/catalog/")

    body = response.content.decode()
    assert 'href="/policies/onboarding/"' in body
    # The dead in-page anchor must be gone.
    assert 'href="#onboarding"' not in body
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `ai/venv/bin/python -m pytest core/tests/test_catalog.py::test_catalog_row_links_to_detail_view -q`
Expected: FAIL — catalog.html still renders `href="#onboarding"`.

- [ ] **Step 3: Replace the dead anchor**

In `core/templates/catalog.html`, replace line 47:

```html
          <a href="#{{ row.policy.slug }}">{{ row.policy.frontmatter.title|default:row.policy.slug }}</a>
```

with:

```html
          <a href="{% url 'policy_detail' slug=row.policy.slug %}">{{ row.policy.frontmatter.title|default:row.policy.slug }}</a>
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `ai/venv/bin/python -m pytest core/tests/test_catalog.py::test_catalog_row_links_to_detail_view -q`
Expected: PASS.

- [ ] **Step 5: Run the full catalog module to confirm no regression**

Run: `ai/venv/bin/python -m pytest core/tests/test_catalog.py -q`
Expected: PASS (all pre-existing catalog tests still green — the anchor change does not touch any other assertion).

- [ ] **Step 6: Commit**

```bash
git add core/templates/catalog.html core/tests/test_catalog.py
git commit -m "feat(core): link catalog rows to the policy detail view (APP-23)"
```

---

## Task 5: Full-suite verification

**Files:** none (verification only)

- [ ] **Step 1: Run the core app tests**

Run: `ai/venv/bin/python -m pytest core -q`
Expected: PASS — including `test_policy_detail.py`, `test_catalog.py`, `test_policy_edit.py`, `test_foundational_edit.py`, `test_approve_pr.py`, `test_publish_policy.py`. The detail route is additive; nothing else changes behavior.

- [ ] **Step 2: Run the entire suite**

Run: `ai/venv/bin/python -m pytest -q`
Expected: green, count up by the 13 new tests (12 in `test_policy_detail.py` + 1 in `test_catalog.py`). Any failure outside this plan's files must be investigated, not papered over (superpowers:verification-before-completion).

- [ ] **Step 3: Manual smoke (record the result; do not claim success without it)**

Start the dev server (`ai/venv/bin/python manage.py runserver`), sign in, open `/catalog/`, click a policy title, and confirm: the detail page renders the title, metadata table, body, and a gate badge; a non-foundational policy shows an "Edit" link to `/policies/<slug>/edit/`; the `document-retention` row shows "Edit (typed table)" and the foundational banner and NO flat-edit link. If you cannot run the server in this environment, say so explicitly rather than implying the smoke passed.

---

## Self-Review (completed during planning)

**1. Spec coverage** (ticket APP-23: "Add a `/policies/<slug>/` view rendering a single policy (title, frontmatter, `provides:`, body, gate state) and replace the dead `#slug` catalog-row anchor with a real link to it. Apply the same L1 foundational gate as the catalog…"):
- `/policies/<slug>/` view → Task 1 (route + view).
- title, frontmatter, `provides:`, body, gate state → Task 2.
- Replace dead `#slug` anchor with a real link → Task 4.
- Same L1 foundational gate (typed-table banner + no edit/delete for foundational; Edit link for non-foundational) → Task 3.
- 404 on unknown slug (implied by "rendering a single policy") → Task 1.
- Future homes for AI-07 confidence badges and the typed-table editor link are explicitly OUT of scope (the editor link IS wired via the foundational gate; confidence badges defer to AI-07).

**2. Placeholder scan:** every code step contains complete, runnable content — full view function, full template (rewritten wholesale in Task 2 so no fragment ambiguity), full test bodies, exact `git add` paths. No TBD/TODO/"handle edge cases".

**3. Type consistency:** `_find_policy(slug)`, `_build_gate_lookup(working_dir)`, `load_working_copy_config()` signatures and the `LogicalPolicy` field names (`slug`, `kind`, `frontmatter`, `body`, `foundational`, `provides`) all match `core/views.py` and `ingest/policy_reader.py` exactly. URL names (`policy_detail`, `policy_edit`, `foundational_edit`, `catalog`) match `core/urls.py`. Gate strings (`drafted`/`reviewed`/`published`) and CSS classes (`gate-*`, `kind-*`, `foundational-badge`, `action-edit`, `action-edit-foundational`) match `catalog.html`. Test stubbing pattern (`patch("core.views.Path.exists")`, `patch("core.views.BundleAwarePolicyReader")`, `patch("core.views.GitHubProvider")` with `list_open_prs`) matches `test_catalog.py`.
