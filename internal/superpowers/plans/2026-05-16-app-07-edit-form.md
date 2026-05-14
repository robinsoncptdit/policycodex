# APP-07 Edit Form Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Django edit form at `/policies/<slug>/edit/` that lets a signed-in user modify a non-foundational policy's title and body, then composes APP-04's `GitHubProvider` + APP-05's working copy + APP-06's `BundleAwarePolicyReader` to write the file, create a branch, commit (authored by the user via `get_git_author`), push, and open a PR back to the diocese's policy repo.

**Architecture:** Function-based view (matches the established `core/views.py` `health` and `catalog` patterns; no CBV, no model layer). GET reads the policy via `BundleAwarePolicyReader`, locates the requested slug, and renders a Django `forms.Form` (title + body) pre-populated from the policy's parsed frontmatter and body. POST validates the form, re-renders the policy file with `_render_policy_md(frontmatter, body)` (a small helper that round-trips `_split_frontmatter`'s output via `yaml.safe_dump`), then sequences `GitHubProvider.branch → commit → push → open_pr`. The commit author is derived from `request.user` via `core.git_identity.get_git_author`; the PR body labels the PR as "Opened by PolicyCodex on behalf of `<username>`" so the human-author attribution lives in the commit (not the PR opener identity, which is the GitHub App). Foundational-policy editing is rejected with HTTP 403 + a banner pointing at APP-20's typed-table UI — APP-07 is explicitly NOT the foundational-bundle editor.

**Tech Stack:** Django 5+/6+ function-based views, Django `forms.Form`, Django messages framework (already wired in `policycodex_site/settings.py`), pytest-django, `unittest.mock.patch`.

**Ticket reference:** `PolicyWonk-v0.1-Tickets.md` APP-07 line 89 ("Edit form for a single policy: opens a branch, commits, opens PR", M, 2-3 days, depends APP-04 + APP-06).

**BASE:** `main` at SHA `5017488` (current `origin/main` per yesterday's session close; Wave-2 merged + OQ-05 owner docs).

**Discipline reminders:**
- TDD: every test observed-failing first, then passing. Don't skip RED.
- No em dashes anywhere in new content (code, docstrings, comments, commit messages, templates).
- Ship-generic: no `pt`, `PT`, `pensacola`, `tallahassee`, `pt-policy` tokens in code/tests/templates. Test fixtures use synthetic slugs like `onboarding`, `code-of-conduct`, `retention`.
- `>=` floor pins in any requirements file (none expected for this ticket; no new deps).
- Implementer dispatch uses Agent tool `isolation: "worktree"`. The harness auto-creates a worktree at `.claude/worktrees/agent-<id>/` branched from the harness's session-start commit. **First step in Task 1 merges current `main` into the worktree branch** because the harness branch may lag.

---

## Key design decisions (locked before tasks)

These are the decisions called out in the dispatch prompt. They lock here so every task downstream is consistent.

### Branch naming convention

`policycodex/edit-<slug>-<short-uuid>` where `<short-uuid>` is `uuid.uuid4().hex[:8]`.

Justification:
- `policycodex/` prefix matches the only existing in-repo example (the APP-04 test uses `policycodex/draft-foo`).
- `edit-` distinguishes user-driven single-policy edits from `draft-` (which AI-10's bulk inventory pass will use) and from future bot-driven branches.
- `<slug>` makes the branch self-describing in the GitHub UI without needing to open the PR.
- `<short-uuid>` (not username, not timestamp) avoids two collision modes: (a) the same user editing the same policy twice in one session — a username suffix would collide on the second branch; (b) leaking that an edit happened at a specific clock time. UUID is opaque and unique.
- 8 hex chars is enough collision-resistance for "two open edits of the same policy"; not trying to be globally unique.

### PR title + body

- **Title:** `Edit policies/<slug>: <truncated-commit-message>` where the commit message comes from the form (Task 4 adds an optional one-line "summary of change" field; defaults to `Update <slug>` if empty).
- **Body:** Includes a fixed preamble naming the editing user and a one-line "machine-opened" attribution so reviewers know the human is the commit author, not the PR opener:

  ```
  Opened by PolicyCodex on behalf of <username>.

  Policy: policies/<slug>
  Author: <name> <<email>>

  <optional summary from form>
  ```

  Newlines, no em dashes.

### Foundational-policy gate

If `policy.foundational is True`, the edit form returns **HTTP 403 with a custom template** (`core/templates/foundational_edit_forbidden.html`) that explains why and links back to `/catalog/`. Justification:
- The foundational-policy design (`internal/PolicyWonk-Foundational-Policy-Design.md`) is explicit: foundational bundles edit through a typed-table UI (APP-20's job, not APP-07's). Letting APP-07 silently scope to "narrative-only" would create two ways to edit the same file and break the L1 protection layer.
- 403 over redirect because the user explicitly asked to edit a foundational policy; a silent redirect would hide why the action failed and is harder to test.
- A flash-message + redirect-to-catalog is the wrong UX: the user is now on `/catalog/` with no context for the rejection.
- Not 404, because the policy DOES exist; the operation is the problem.

### Form fields

Editable in v0.1:
- `title` (text input, max 200 chars, required)
- `body` (textarea, required, no max length)
- `summary` (text input, max 200 chars, optional; becomes the commit message + PR title suffix)

Read-only / not exposed:
- `slug` (URL-bound; renaming a policy is APP-XX-revised work, not v0.1 edit)
- `foundational` (foundational policies don't reach this form at all)
- `provides:` (same)
- `kind` (derived from filesystem layout, not the form)
- Other frontmatter keys (`owner`, `effective_date`, `last_review`, `next_review`, `retention`, etc.) are preserved round-trip but not editable in v0.1. The AI extraction sets these; user edits of those fields land in v0.2 once the typed-table UI exists. Carrying them as-is keeps `_render_policy_md` lossless.

This is a deliberately spartan v0.1 form. The PRD requires "an editor can change a policy's narrative and propose it through a PR"; v0.1 covers that with title + body. Frontmatter-field editing is a v0.2 typed-table UI task.

### GitHubProvider failure handling

All four operations (`branch`, `commit`, `push`, `open_pr`) raise `RuntimeError` (or `ValueError` for bad URLs) on failure. The view wraps each call in a try/except and on any failure:
1. Renders the edit form again (preserving the user's input).
2. Adds a Django `messages.error` with a short user-facing label (e.g., "Couldn't create branch — try again or contact your administrator.").
3. Logs the underlying exception message at `logging.ERROR` so the admin can see what failed in `manage.py runserver` logs.

The view never 500s on a provider failure. (Unexpected exceptions outside the providers — e.g. disk-full during file write — let Django's default 500 handler take over; that's still preferable to swallowing.)

### CSRF + login_required

Both. `@login_required` decorator (same pattern as `catalog`). The form is POST-only for state-changing operations and inherits Django's default CSRF middleware (already in `policycodex_site/settings.py`).

---

## File Structure

- Create: `core/forms.py` — `PolicyEditForm(forms.Form)` with three `CharField`s (`title`, `body`, `summary`). First forms module in the project; lives in `core/` because the form is bound to a `core/` view.
- Create: `core/policy_writer.py` — `_render_policy_md(frontmatter: Mapping, body: str) -> str` helper that round-trips through `yaml.safe_dump`. Tiny module so the writer is unit-testable without spinning up Django.
- Modify: `core/views.py` — add `policy_edit(request, slug)` view function. Imports `PolicyEditForm`, `_render_policy_md`, `get_git_author`, `GitHubProvider`, `load_working_copy_config`, `BundleAwarePolicyReader`.
- Modify: `core/urls.py` — add `path("policies/<slug:slug>/edit/", views.policy_edit, name="policy_edit")`.
- Create: `core/templates/policy_edit.html` — extends `base.html`; renders the form via `{{ form.as_p }}` plus a Submit button. No JS.
- Create: `core/templates/foundational_edit_forbidden.html` — extends `base.html`; explains the foundational-policy gate and links to `/catalog/`. Rendered with HTTP 403.
- Create: `core/templates/policy_edit_success.html` — extends `base.html`; shows "PR #N opened" + link to the GitHub PR URL + "Back to catalog" link.
- Create: `core/tests/test_policy_edit.py` — pytest tests (~16 tests) covering URL resolution, login required, slug-not-found, foundational gate, form pre-population, valid POST happy path, GitHubProvider failures at each stage, form-validation errors.
- Create: `core/tests/test_policy_writer.py` — pytest tests (~4 tests) for the `_render_policy_md` helper (round-trip, body-only, empty-frontmatter, ordering stability).

No other files touched. `app/git_provider/`, `app/working_copy/`, `ingest/policy_reader.py`, `core/git_identity.py`, `policycodex_site/settings.py` — all read-only for this ticket.

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

Expected: BASE SHA is `5017488` or a descendant; branch is the auto-worktree branch the harness gave you (something like `worktree-agent-<id>`); status clean.

If anything is unexpected, STOP and report.

- [ ] **Step 2: Merge `main` into your worktree branch**

The harness's auto-worktree may have branched from a session-start commit older than current `main`. Run:

```bash
git fetch
git merge main --no-edit
```

Expected: "Already up to date." or a clean fast-forward to `5017488` (or descendant). If a merge conflict surfaces, STOP and report.

- [ ] **Step 3: Confirm baseline test suite green**

```bash
cd /Users/chuck/PolicyWonk && /Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest -q 2>&1 | tail -3
```

Expected: `180 passed` (the count after APP-21 + APP-06 merged on 2026-05-15).

**Capture the baseline number** for the final self-report.

- [ ] **Step 4: Read the existing patterns this ticket composes**

Read each of these briefly to confirm signatures match what this plan uses:

- `/Users/chuck/PolicyWonk/core/views.py` — `catalog` is the closest view analog (login_required + working-copy + reader composition).
- `/Users/chuck/PolicyWonk/core/urls.py` — URL routing style.
- `/Users/chuck/PolicyWonk/core/tests/test_catalog.py:39-54` — `_stub_policy` helper (this plan reuses the same pattern).
- `/Users/chuck/PolicyWonk/core/tests/test_auth.py:8-17` — user fixture with `first_name`/`last_name`/`email` set.
- `/Users/chuck/PolicyWonk/core/git_identity.py` — `get_git_author(user) -> tuple[str, str]` signature.
- `/Users/chuck/PolicyWonk/app/git_provider/github_provider.py` — `branch`/`commit`/`push`/`open_pr` signatures and the `RuntimeError` failure mode.
- `/Users/chuck/PolicyWonk/app/git_provider/tests/test_github_provider.py:112-141` — the canonical `commit` mocking pattern.
- `/Users/chuck/PolicyWonk/ingest/policy_reader.py:36-45` — `_split_frontmatter` (the writer in Task 2 round-trips this).
- `/Users/chuck/PolicyWonk/app/working_copy/config.py` — `WorkingCopyConfig.working_dir` returns a `Path`.

- [ ] **Step 5: No commit yet.**

---

## Task 2: `_render_policy_md` writer helper (TDD)

**Files:**
- Create: `core/policy_writer.py`
- Create: `core/tests/test_policy_writer.py`

The writer must round-trip a `(frontmatter, body)` tuple back to the same on-disk shape that `_split_frontmatter` produces. Preserving frontmatter keys we don't expose in the form (owner, effective_date, etc.) is the explicit goal.

- [ ] **Step 1: Write the failing tests**

Create `core/tests/test_policy_writer.py`:

```python
"""Tests for core.policy_writer._render_policy_md."""
from ingest.policy_reader import _split_frontmatter

from core.policy_writer import _render_policy_md


def test_render_with_frontmatter_and_body():
    """Frontmatter + body should serialize as `---\\n<yaml>\\n---\\n<body>`."""
    fm = {"title": "Onboarding", "owner": "HR Director"}
    body = "## Purpose\nWelcome new hires.\n"
    out = _render_policy_md(fm, body)
    assert out.startswith("---\n")
    assert "title: Onboarding" in out
    assert "owner: HR Director" in out
    assert out.endswith("## Purpose\nWelcome new hires.\n")
    # The fence-line separator must end with a newline.
    assert "\n---\n" in out


def test_round_trip_preserves_unexposed_keys():
    """Reading then re-rendering must NOT lose frontmatter keys the form does not expose."""
    original = (
        "---\n"
        "title: Code of Conduct\n"
        "owner: Chancellor\n"
        "effective_date: 2026-01-01\n"
        "retention: 7y\n"
        "---\n"
        "## Scope\nAll staff.\n"
    )
    fm, body = _split_frontmatter(original)
    # Simulate the form changing only title + body.
    fm = dict(fm)
    fm["title"] = "Code of Conduct (Revised)"
    new_body = "## Scope\nAll staff and volunteers.\n"
    out = _render_policy_md(fm, new_body)
    # All four original frontmatter keys still present.
    assert "title: Code of Conduct (Revised)" in out
    assert "owner: Chancellor" in out
    assert "effective_date: 2026-01-01" in out
    assert "retention: 7y" in out
    # Body updated.
    assert "All staff and volunteers." in out
    # And re-parsing yields the same shape.
    fm2, body2 = _split_frontmatter(out)
    assert fm2["title"] == "Code of Conduct (Revised)"
    assert fm2["owner"] == "Chancellor"
    assert body2 == new_body


def test_empty_frontmatter_emits_empty_fenced_block():
    """A policy with no frontmatter keys still emits the fence so the body shape is consistent."""
    out = _render_policy_md({}, "Just a body.\n")
    assert out.startswith("---\n")
    assert "\n---\n" in out
    assert out.endswith("Just a body.\n")


def test_no_em_dashes_in_output():
    """Discipline guard: the rendered output must contain no em dashes
    (project-wide style rule). yaml.safe_dump uses '-' for list items but
    must not emit U+2014. This test catches any future regression where
    a library/setting introduces a fancy-dash transform."""
    fm = {"title": "Policy", "tags": ["alpha", "beta"]}
    body = "Body text - with a hyphen.\n"
    out = _render_policy_md(fm, body)
    assert "—" not in out  # em dash
    assert "–" not in out  # en dash
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd /Users/chuck/PolicyWonk && /Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest core/tests/test_policy_writer.py -v 2>&1 | tail -10
```

Expected: `ModuleNotFoundError: No module named 'core.policy_writer'`.

- [ ] **Step 3: Implement `core/policy_writer.py`**

Write:

```python
"""Render (frontmatter, body) back to a policy.md file payload.

Inverse of ingest.policy_reader._split_frontmatter. Used by APP-07 (the
edit form view) to write the user's changes back to the local working
copy before committing.

Lossless: any frontmatter key that was present on read is preserved on
write, even if the form does not expose it. This is what lets v0.1 ship
with a narrow editable surface (title + body) without dropping
AI-extracted metadata (owner, effective_date, retention, ...) the next
time the file is re-rendered.
"""
from __future__ import annotations

from typing import Mapping

import yaml


def _render_policy_md(frontmatter: Mapping[str, object], body: str) -> str:
    """Return a string in the form `---\\n<yaml>\\n---\\n<body>`.

    `yaml.safe_dump` is used with `sort_keys=False` and
    `default_flow_style=False` to produce a stable, human-readable
    block-style block. Empty frontmatter still emits the fences so the
    file shape is consistent across all policies.
    """
    if frontmatter:
        # Coerce to a plain dict so safe_dump handles Mapping types
        # (the reader returns a dict already, but being defensive is cheap).
        fm_text = yaml.safe_dump(
            dict(frontmatter),
            sort_keys=False,
            default_flow_style=False,
            allow_unicode=True,
        )
    else:
        fm_text = ""
    # `safe_dump` always terminates with a newline; concat the fences around it.
    return f"---\n{fm_text}---\n{body}"
```

- [ ] **Step 4: Run to confirm pass**

```bash
/Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest core/tests/test_policy_writer.py -v 2>&1 | tail -8
```

Expected: 4 passing.

- [ ] **Step 5: Commit**

```bash
git add core/policy_writer.py core/tests/test_policy_writer.py
git commit -m "feat(APP-07): lossless policy.md writer helper (_render_policy_md)"
```

---

## Task 3: URL + login_required + slug-not-found (TDD)

**Files:**
- Modify: `core/views.py`
- Modify: `core/urls.py`
- Create: `core/templates/policy_edit.html` (minimal scaffold; expanded in Task 4)
- Create: `core/tests/test_policy_edit.py`

- [ ] **Step 1: Write the failing tests**

Create `core/tests/test_policy_edit.py`:

```python
"""Tests for the policy_edit view (APP-07)."""
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
    return User.objects.create_user(
        username="editor",
        password="hunter2hunter2",
        email="editor@example.com",
        first_name="Pat",
        last_name="Editor",
    )


def _stub_policy(*, slug, kind="flat", title=None, body="", foundational=False, provides=()):
    """Build a stand-in for an ingest.policy_reader.LogicalPolicy.

    Mirrors core/tests/test_catalog.py:_stub_policy so behavior stays consistent.
    """
    pp = Path(f"/tmp/policies/{slug}.md") if kind == "flat" else Path(f"/tmp/policies/{slug}/policy.md")
    return LogicalPolicy(
        slug=slug,
        kind=kind,
        policy_path=pp,
        data_path=None if kind == "flat" else pp.parent / "data.yaml",
        frontmatter={"title": title or slug.replace("-", " ").title()},
        body=body,
        foundational=foundational,
        provides=provides,
    )


# --- URL + auth ---

def test_policy_edit_url_resolves():
    assert reverse("policy_edit", kwargs={"slug": "onboarding"}) == "/policies/onboarding/edit/"


def test_policy_edit_requires_login(client):
    response = client.get("/policies/onboarding/edit/")
    assert response.status_code == 302
    assert response.url.startswith("/login/")
    assert "next=/policies/onboarding/edit/" in response.url


def test_policy_edit_404_when_slug_not_found(client, user):
    """An authenticated request for a non-existent slug returns 404."""
    client.force_login(user)
    policies = [_stub_policy(slug="exists")]
    with override_settings(
        POLICYCODEX_POLICY_REPO_URL="https://example.com/x.git",
        POLICYCODEX_WORKING_COPY_ROOT="/tmp",
    ):
        with patch("core.views.Path.exists", return_value=True):
            with patch("core.views.BundleAwarePolicyReader") as MockReader:
                MockReader.return_value.read.return_value = iter(policies)
                response = client.get("/policies/missing/edit/")
    assert response.status_code == 404
```

- [ ] **Step 2: Run to confirm failure**

```bash
/Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest core/tests/test_policy_edit.py -v 2>&1 | tail -10
```

Expected: `NoReverseMatch: Reverse for 'policy_edit' not found.` for `test_policy_edit_url_resolves`; the other two tests fail at URL resolution too.

- [ ] **Step 3: Create the minimal template scaffold**

Create `core/templates/policy_edit.html`:

```html
{% extends "base.html" %}

{% block title %}Edit {{ policy.slug }} | PolicyCodex{% endblock %}

{% block content %}
  <h2>Edit policies/{{ policy.slug }}</h2>
  <form method="post">
    {% csrf_token %}
    {{ form.as_p }}
    <button type="submit">Open PR</button>
    <a href="{% url 'catalog' %}">Cancel</a>
  </form>
{% endblock %}
```

Task 4 expands this; Task 3 only needs it to exist so the view can render something.

- [ ] **Step 4: Add the view (slug-lookup + 404 only; form rendering lands in Task 4)**

Open `core/views.py`. Add to the bottom:

```python
from django.http import Http404


def _find_policy(slug: str):
    """Return the LogicalPolicy for `slug`, or None if not found.

    Composes load_working_copy_config + BundleAwarePolicyReader the same
    way `catalog` does. Returns None on any infrastructure issue so the
    caller can choose how to handle it (typically 404).
    """
    try:
        config = load_working_copy_config()
    except RuntimeError:
        return None
    policies_dir: Path = config.working_dir / "policies"
    if not policies_dir.exists():
        return None
    for policy in BundleAwarePolicyReader(policies_dir).read():
        if policy.slug == slug:
            return policy
    return None


@login_required
def policy_edit(request, slug):
    """Edit a single non-foundational policy and open a PR.

    Task 3 lands the slug lookup + 404 path. Task 4 adds form rendering,
    Task 5 the foundational gate, Task 6 the POST happy path, Task 7 the
    GitHubProvider failure handling.
    """
    policy = _find_policy(slug)
    if policy is None:
        raise Http404(f"Policy not found: {slug}")
    # Temporary placeholder context until Task 4 wires the form. Returns a 200
    # with the scaffold template so the URL-routing tests are not blocked by
    # form code that does not exist yet.
    from core.forms import PolicyEditForm  # local import; Task 4 creates the module
    form = PolicyEditForm(initial={
        "title": policy.frontmatter.get("title", policy.slug),
        "body": policy.body,
        "summary": "",
    })
    return render(request, "policy_edit.html", {"policy": policy, "form": form})
```

Note: the local `from core.forms import PolicyEditForm` is intentional. Task 4 creates `core/forms.py`. Until then this view does NOT import successfully under any code path that calls it — which is fine for Task 3 because the only test that hits the view (the 404 test) returns BEFORE reaching the form import.

If you prefer NOT to stage the broken-import behavior, you may instead split this task: only land the `_find_policy` helper + the bare 404 path in Task 3 (return an `HttpResponse("placeholder", status=200)` for the happy path), and move the `render(... policy_edit.html ...)` call into Task 4. Either ordering is acceptable; the rest of the plan assumes the version above. If you take the alternative split, adjust the test assertions in Task 3 accordingly (no template name checks).

- [ ] **Step 5: Wire the URL**

Open `core/urls.py`. Add the new route. The file should end up:

```python
"""URL routes for the core app."""
from django.urls import path

from . import views


urlpatterns = [
    path("", views.root_redirect, name="root"),
    path("health/", views.health, name="health"),
    path("catalog/", views.catalog, name="catalog"),
    path("policies/<slug:slug>/edit/", views.policy_edit, name="policy_edit"),
]
```

- [ ] **Step 6: Run to confirm pass**

```bash
/Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest core/tests/test_policy_edit.py -v 2>&1 | tail -10
```

Expected: 2 passing (`test_policy_edit_url_resolves`, `test_policy_edit_requires_login`); 1 failing (`test_policy_edit_404_when_slug_not_found` raises `ModuleNotFoundError: No module named 'core.forms'` because the placeholder view still tries to import it once `_find_policy` returns a hit, BUT the 404 path returns BEFORE the import, so this test should ALSO pass).

Actually all 3 should pass — confirm. If `test_policy_edit_404_when_slug_not_found` is the only failure, it's the import path; resolve in Task 4 (the test passes once `core/forms.py` exists). If it passes here, great.

If 3 pass: continue.
If 2 pass and the 404 test fails on ModuleNotFoundError: that means the view loaded `core.forms` at module import time despite the local import; double-check the import is INSIDE `policy_edit`, not at top of file. Fix and re-run.

- [ ] **Step 7: Commit**

```bash
git add core/views.py core/urls.py core/templates/policy_edit.html core/tests/test_policy_edit.py
git commit -m "feat(APP-07): policy_edit URL + login_required + 404 on unknown slug"
```

---

## Task 4: Form class + GET pre-population (TDD)

**Files:**
- Create: `core/forms.py`
- Modify: `core/templates/policy_edit.html`
- Modify: `core/tests/test_policy_edit.py`

- [ ] **Step 1: Write the failing tests**

Append to `core/tests/test_policy_edit.py`:

```python
# --- Form class ---

def test_form_has_three_fields():
    """v0.1 editable surface: title, body, summary."""
    from core.forms import PolicyEditForm
    form = PolicyEditForm()
    assert set(form.fields.keys()) == {"title", "body", "summary"}


def test_form_required_fields():
    from core.forms import PolicyEditForm
    form = PolicyEditForm(data={"title": "", "body": "", "summary": ""})
    assert not form.is_valid()
    assert "title" in form.errors
    assert "body" in form.errors
    # summary is optional.
    assert "summary" not in form.errors


def test_form_title_max_length():
    """Title is capped at 200 chars to keep PR titles bounded."""
    from core.forms import PolicyEditForm
    long_title = "x" * 201
    form = PolicyEditForm(data={"title": long_title, "body": "ok"})
    assert not form.is_valid()
    assert "title" in form.errors


# --- GET pre-population ---

def test_get_renders_form_prepopulated_with_title_and_body(client, user):
    """A GET on /policies/<slug>/edit/ pre-populates title from frontmatter and body verbatim."""
    client.force_login(user)
    policies = [
        _stub_policy(
            slug="onboarding",
            kind="flat",
            title="New Employee Onboarding",
            body="## Purpose\nWelcome new hires.\n",
        ),
    ]
    with override_settings(
        POLICYCODEX_POLICY_REPO_URL="https://example.com/x.git",
        POLICYCODEX_WORKING_COPY_ROOT="/tmp",
    ):
        with patch("core.views.Path.exists", return_value=True):
            with patch("core.views.BundleAwarePolicyReader") as MockReader:
                MockReader.return_value.read.return_value = iter(policies)
                response = client.get("/policies/onboarding/edit/")
    assert response.status_code == 200
    body = response.content.decode()
    # Title field pre-populated.
    assert 'value="New Employee Onboarding"' in body
    # Body textarea pre-populated. Django escapes content, so check the unescaped string.
    assert "## Purpose" in body
    assert "Welcome new hires." in body
    # Form structure visible.
    assert "<form" in body
    assert 'method="post"' in body
    assert "csrfmiddlewaretoken" in body
```

- [ ] **Step 2: Run to confirm failure**

```bash
/Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest core/tests/test_policy_edit.py -v 2>&1 | tail -10
```

Expected: 4 failing (`ModuleNotFoundError: No module named 'core.forms'`).

- [ ] **Step 3: Create `core/forms.py`**

Write:

```python
"""Django forms for the core app."""
from django import forms


class PolicyEditForm(forms.Form):
    """Edit form for a single non-foundational policy (APP-07).

    Editable surface in v0.1: title (frontmatter), body (markdown), and an
    optional one-line summary that becomes the commit message + PR title
    suffix.

    Other frontmatter keys (owner, effective_date, retention, ...) are
    preserved round-trip by the view but NOT exposed here. The typed-table
    UI (future ticket) will expose them.
    """

    title = forms.CharField(
        max_length=200,
        required=True,
        widget=forms.TextInput(attrs={"autocomplete": "off"}),
    )
    body = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={"rows": 20, "cols": 80}),
    )
    summary = forms.CharField(
        max_length=200,
        required=False,
        help_text="Optional one-line description of your change. Becomes the commit message.",
        widget=forms.TextInput(attrs={"autocomplete": "off"}),
    )
```

- [ ] **Step 4: Refine the template to render the form cleanly**

Replace `core/templates/policy_edit.html`:

```html
{% extends "base.html" %}

{% block title %}Edit {{ policy.slug }} | PolicyCodex{% endblock %}

{% block content %}
  <h2>Edit policies/{{ policy.slug }}</h2>

  {% if messages %}
    <ul class="messages">
      {% for message in messages %}
        <li class="{{ message.tags }}">{{ message }}</li>
      {% endfor %}
    </ul>
  {% endif %}

  <form method="post">
    {% csrf_token %}
    <p>
      <label for="{{ form.title.id_for_label }}">Title</label>
      {{ form.title }}
      {% if form.title.errors %}<span class="error">{{ form.title.errors|join:", " }}</span>{% endif %}
    </p>
    <p>
      <label for="{{ form.body.id_for_label }}">Body</label>
      {{ form.body }}
      {% if form.body.errors %}<span class="error">{{ form.body.errors|join:", " }}</span>{% endif %}
    </p>
    <p>
      <label for="{{ form.summary.id_for_label }}">Summary (optional)</label>
      {{ form.summary }}
      <small>{{ form.summary.help_text }}</small>
      {% if form.summary.errors %}<span class="error">{{ form.summary.errors|join:", " }}</span>{% endif %}
    </p>
    <p>
      <button type="submit">Open PR</button>
      <a href="{% url 'catalog' %}">Cancel</a>
    </p>
  </form>
{% endblock %}
```

- [ ] **Step 5: Run to confirm pass**

```bash
/Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest core/tests/test_policy_edit.py -v 2>&1 | tail -10
```

Expected: 7 passing (the 3 from Task 3 plus 4 new).

- [ ] **Step 6: Commit**

```bash
git add core/forms.py core/templates/policy_edit.html core/tests/test_policy_edit.py
git commit -m "feat(APP-07): PolicyEditForm + GET pre-population from working copy"
```

---

## Task 5: Foundational-policy gate (TDD)

**Files:**
- Modify: `core/views.py`
- Create: `core/templates/foundational_edit_forbidden.html`
- Modify: `core/tests/test_policy_edit.py`

- [ ] **Step 1: Write the failing tests**

Append to `core/tests/test_policy_edit.py`:

```python
# --- Foundational-policy gate ---

def test_get_foundational_policy_returns_403_with_explanation(client, user):
    """Foundational bundles edit through the typed-table UI (APP-20), not this form.

    GET on a foundational policy returns 403 with a custom template that
    names the typed-table UI as the right path. Per the foundational-policy
    design (L1 protection layer)."""
    client.force_login(user)
    policies = [
        _stub_policy(
            slug="document-retention",
            kind="bundle",
            title="Document Retention Policy",
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
                response = client.get("/policies/document-retention/edit/")
    assert response.status_code == 403
    body = response.content.decode()
    assert "foundational" in body.lower()
    # The error page must mention the slug so the user knows what was rejected.
    assert "document-retention" in body
    # And link back to the catalog.
    assert "/catalog/" in body


def test_post_foundational_policy_also_returns_403(client, user):
    """The gate applies to POST as well — never let a foundational policy be edited via this form."""
    client.force_login(user)
    policies = [
        _stub_policy(
            slug="document-retention",
            kind="bundle",
            foundational=True,
            provides=("classifications",),
        ),
    ]
    with override_settings(
        POLICYCODEX_POLICY_REPO_URL="https://example.com/x.git",
        POLICYCODEX_WORKING_COPY_ROOT="/tmp",
    ):
        with patch("core.views.Path.exists", return_value=True):
            with patch("core.views.BundleAwarePolicyReader") as MockReader:
                MockReader.return_value.read.return_value = iter(policies)
                response = client.post(
                    "/policies/document-retention/edit/",
                    data={"title": "Hijack", "body": "Bad", "summary": ""},
                )
    assert response.status_code == 403
```

- [ ] **Step 2: Run to confirm failure**

```bash
/Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest core/tests/test_policy_edit.py::test_get_foundational_policy_returns_403_with_explanation -v 2>&1 | tail -10
```

Expected: AssertionError — current view returns 200 for the foundational policy because the gate is not yet wired.

- [ ] **Step 3: Create `core/templates/foundational_edit_forbidden.html`**

Write:

```html
{% extends "base.html" %}

{% block title %}Cannot edit foundational policy | PolicyCodex{% endblock %}

{% block content %}
  <h2>Cannot edit a foundational policy here</h2>
  <p>
    The policy <code>policies/{{ policy.slug }}</code> is marked
    <strong>foundational</strong>: it supplies configuration values that
    other policies and the app itself depend on (for example the document
    classification list and retention schedule).
  </p>
  <p>
    To change a foundational policy, use the typed-table editor in the
    onboarding wizard or the foundational-policy admin screen. The edit
    form on this page is only for ordinary policy documents.
  </p>
  <p>
    <a href="{% url 'catalog' %}">Back to catalog</a>
  </p>
{% endblock %}
```

- [ ] **Step 4: Wire the gate in the view**

Edit `core/views.py`. In `policy_edit`, insert the gate immediately after `_find_policy` returns:

```python
@login_required
def policy_edit(request, slug):
    """Edit a single non-foundational policy and open a PR."""
    policy = _find_policy(slug)
    if policy is None:
        raise Http404(f"Policy not found: {slug}")
    if policy.foundational:
        return render(
            request,
            "foundational_edit_forbidden.html",
            {"policy": policy},
            status=403,
        )
    # ... rest of view (Task 4's GET path remains here unchanged) ...
    from core.forms import PolicyEditForm
    form = PolicyEditForm(initial={
        "title": policy.frontmatter.get("title", policy.slug),
        "body": policy.body,
        "summary": "",
    })
    return render(request, "policy_edit.html", {"policy": policy, "form": form})
```

- [ ] **Step 5: Run to confirm pass**

```bash
/Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest core/tests/test_policy_edit.py -v 2>&1 | tail -12
```

Expected: 9 passing (7 from Tasks 3-4 plus 2 new).

- [ ] **Step 6: Commit**

```bash
git add core/views.py core/templates/foundational_edit_forbidden.html core/tests/test_policy_edit.py
git commit -m "feat(APP-07): foundational-policy gate returns 403 with explanation"
```

---

## Task 6: POST happy path — branch + commit + push + open_pr (TDD)

**Files:**
- Modify: `core/views.py`
- Create: `core/templates/policy_edit_success.html`
- Modify: `core/tests/test_policy_edit.py`

- [ ] **Step 1: Write the failing tests**

Append to `core/tests/test_policy_edit.py`:

```python
# --- POST happy path ---

def test_post_valid_calls_branch_commit_push_open_pr_in_order(client, user, tmp_path):
    """The happy path sequences all four GitHubProvider operations and writes the file."""
    client.force_login(user)

    # Build a real on-disk policies/onboarding.md so the view can write to it.
    repo_dir = tmp_path / "diocese-policies"
    policies_dir = repo_dir / "policies"
    policies_dir.mkdir(parents=True)
    policy_file = policies_dir / "onboarding.md"
    policy_file.write_text(
        "---\ntitle: Old Title\nowner: HR Director\n---\nOld body.\n",
        encoding="utf-8",
    )

    # Real LogicalPolicy so the view can read it back from the reader mock.
    real_policy = LogicalPolicy(
        slug="onboarding",
        kind="flat",
        policy_path=policy_file,
        data_path=None,
        frontmatter={"title": "Old Title", "owner": "HR Director"},
        body="Old body.\n",
        foundational=False,
        provides=(),
    )

    fake_pr = {
        "pr_number": 17,
        "url": "https://github.com/example/diocese-policies/pull/17",
        "state": "open",
    }
    with override_settings(
        POLICYCODEX_POLICY_REPO_URL="https://github.com/example/diocese-policies.git",
        POLICYCODEX_POLICY_BRANCH="main",
        POLICYCODEX_WORKING_COPY_ROOT=str(tmp_path),
    ):
        with patch("core.views.Path.exists", return_value=True):
            with patch("core.views.BundleAwarePolicyReader") as MockReader:
                MockReader.return_value.read.return_value = iter([real_policy])
                with patch("core.views.GitHubProvider") as MockProvider:
                    instance = MockProvider.return_value
                    instance.open_pr.return_value = fake_pr
                    response = client.post(
                        "/policies/onboarding/edit/",
                        data={
                            "title": "Onboarding Revised",
                            "body": "New body text.\n",
                            "summary": "Tighten the welcome section",
                        },
                    )

    # Successful POST redirects to the success page.
    assert response.status_code in (302, 200)  # 302 if redirect-to-success; 200 if render-success-directly
    # File on disk reflects the new title + body (round-tripped through _render_policy_md).
    new_text = policy_file.read_text(encoding="utf-8")
    assert "title: Onboarding Revised" in new_text
    assert "owner: HR Director" in new_text  # unexposed key preserved
    assert "New body text." in new_text
    # GitHubProvider call sequence.
    instance.branch.assert_called_once()
    branch_args = instance.branch.call_args[0]
    branch_name = branch_args[0]
    assert branch_name.startswith("policycodex/edit-onboarding-")
    instance.commit.assert_called_once()
    commit_kwargs = instance.commit.call_args.kwargs or {}
    commit_args = instance.commit.call_args.args
    # commit(message, files, author_name, author_email, working_dir)
    # The view may use kwargs or positional; assert by name when possible.
    # Pull either way:
    def _pick(name, idx):
        if name in commit_kwargs:
            return commit_kwargs[name]
        return commit_args[idx]
    msg = _pick("message", 0)
    files = _pick("files", 1)
    author_name = _pick("author_name", 2)
    author_email = _pick("author_email", 3)
    assert msg == "Tighten the welcome section"
    assert files == [policy_file]
    assert author_name == "Pat Editor"
    assert author_email == "editor@example.com"
    instance.push.assert_called_once()
    push_args = instance.push.call_args[0]
    assert push_args[0] == branch_name
    instance.open_pr.assert_called_once()
    open_pr_kwargs = instance.open_pr.call_args.kwargs or {}
    open_pr_args = instance.open_pr.call_args.args
    def _pick2(name, idx):
        if name in open_pr_kwargs:
            return open_pr_kwargs[name]
        return open_pr_args[idx]
    title = _pick2("title", 0)
    body_text = _pick2("body", 1)
    head_branch = _pick2("head_branch", 2)
    base_branch = _pick2("base_branch", 3)
    assert "onboarding" in title
    assert "Tighten the welcome section" in title or "Tighten the welcome section" in body_text
    assert head_branch == branch_name
    assert base_branch == "main"
    assert "Opened by PolicyCodex on behalf of editor" in body_text
    # Call order: branch < commit < push < open_pr.
    branch_n = instance.branch.call_args_list[0]
    commit_n = instance.commit.call_args_list[0]
    push_n = instance.push.call_args_list[0]
    open_pr_n = instance.open_pr.call_args_list[0]
    # Use the mock's mock_calls index ordering on the parent.
    parent_calls = MockProvider.return_value.mock_calls
    method_names = [c[0] for c in parent_calls]
    assert method_names.index("branch") < method_names.index("commit") < method_names.index("push") < method_names.index("open_pr")


def test_post_default_commit_message_when_summary_empty(client, user, tmp_path):
    """If the form's summary is blank, the commit message defaults to `Update <slug>`."""
    client.force_login(user)
    repo_dir = tmp_path / "diocese-policies"
    policies_dir = repo_dir / "policies"
    policies_dir.mkdir(parents=True)
    policy_file = policies_dir / "onboarding.md"
    policy_file.write_text("---\ntitle: T\n---\nbody\n", encoding="utf-8")
    real_policy = LogicalPolicy(
        slug="onboarding", kind="flat", policy_path=policy_file, data_path=None,
        frontmatter={"title": "T"}, body="body\n", foundational=False, provides=(),
    )
    with override_settings(
        POLICYCODEX_POLICY_REPO_URL="https://github.com/example/diocese-policies.git",
        POLICYCODEX_WORKING_COPY_ROOT=str(tmp_path),
    ):
        with patch("core.views.Path.exists", return_value=True):
            with patch("core.views.BundleAwarePolicyReader") as MockReader:
                MockReader.return_value.read.return_value = iter([real_policy])
                with patch("core.views.GitHubProvider") as MockProvider:
                    instance = MockProvider.return_value
                    instance.open_pr.return_value = {"pr_number": 1, "url": "u", "state": "open"}
                    client.post(
                        "/policies/onboarding/edit/",
                        data={"title": "T2", "body": "b2\n", "summary": ""},
                    )
    commit_call = instance.commit.call_args
    msg = commit_call.kwargs.get("message", commit_call.args[0] if commit_call.args else None)
    assert msg == "Update onboarding"


def test_post_renders_success_page_with_pr_url(client, user, tmp_path):
    """After a successful PR is opened, the user sees a success page containing the PR URL."""
    client.force_login(user)
    repo_dir = tmp_path / "diocese-policies"
    policies_dir = repo_dir / "policies"
    policies_dir.mkdir(parents=True)
    policy_file = policies_dir / "onboarding.md"
    policy_file.write_text("---\ntitle: T\n---\nb\n", encoding="utf-8")
    real_policy = LogicalPolicy(
        slug="onboarding", kind="flat", policy_path=policy_file, data_path=None,
        frontmatter={"title": "T"}, body="b\n", foundational=False, provides=(),
    )
    with override_settings(
        POLICYCODEX_POLICY_REPO_URL="https://github.com/example/diocese-policies.git",
        POLICYCODEX_WORKING_COPY_ROOT=str(tmp_path),
    ):
        with patch("core.views.Path.exists", return_value=True):
            with patch("core.views.BundleAwarePolicyReader") as MockReader:
                MockReader.return_value.read.return_value = iter([real_policy])
                with patch("core.views.GitHubProvider") as MockProvider:
                    instance = MockProvider.return_value
                    instance.open_pr.return_value = {
                        "pr_number": 42,
                        "url": "https://github.com/example/diocese-policies/pull/42",
                        "state": "open",
                    }
                    response = client.post(
                        "/policies/onboarding/edit/",
                        data={"title": "T2", "body": "b2\n", "summary": "msg"},
                        follow=True,  # follow a redirect-to-success-page if used
                    )
    assert response.status_code == 200
    body = response.content.decode()
    assert "https://github.com/example/diocese-policies/pull/42" in body
    assert "42" in body  # PR number visible somewhere
```

- [ ] **Step 2: Run to confirm failure**

```bash
/Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest core/tests/test_policy_edit.py -v 2>&1 | tail -15
```

Expected: 9 passing (Tasks 3-5) + 3 failing (the new POST tests; current view does not handle POST yet).

- [ ] **Step 3: Create the success template**

Create `core/templates/policy_edit_success.html`:

```html
{% extends "base.html" %}

{% block title %}PR opened | PolicyCodex{% endblock %}

{% block content %}
  <h2>Pull request opened</h2>
  <p>
    Your edit to <code>policies/{{ policy.slug }}</code> is now PR
    <a href="{{ pr.url }}">#{{ pr.pr_number }}</a> on the diocese's policy
    repo. A reviewer with merge permission will approve and publish from
    there.
  </p>
  <p>
    <a href="{% url 'catalog' %}">Back to catalog</a>
  </p>
{% endblock %}
```

- [ ] **Step 4: Implement the POST happy path in the view**

Replace the body of `policy_edit` in `core/views.py` (keep the existing imports at the top of the file; add what's missing). The full file's tail should look like:

```python
import logging
import uuid

from django.contrib import messages
from django.http import Http404

from app.git_provider.github_provider import GitHubProvider
from core.forms import PolicyEditForm
from core.git_identity import get_git_author
from core.policy_writer import _render_policy_md


logger = logging.getLogger(__name__)


def _find_policy(slug: str):
    """Return the LogicalPolicy for `slug`, or None if not found."""
    try:
        config = load_working_copy_config()
    except RuntimeError:
        return None
    policies_dir: Path = config.working_dir / "policies"
    if not policies_dir.exists():
        return None
    for policy in BundleAwarePolicyReader(policies_dir).read():
        if policy.slug == slug:
            return policy
    return None


def _make_branch_name(slug: str) -> str:
    """policycodex/edit-<slug>-<short-uuid>. See plan rationale."""
    return f"policycodex/edit-{slug}-{uuid.uuid4().hex[:8]}"


@login_required
def policy_edit(request, slug):
    """GET pre-populates an edit form; POST writes the file, branches,
    commits authored by the user, pushes, and opens a PR back to the
    diocese's policy repo.

    Foundational policies edit through the typed-table UI (APP-20),
    never this form: GET and POST both return 403.
    """
    policy = _find_policy(slug)
    if policy is None:
        raise Http404(f"Policy not found: {slug}")
    if policy.foundational:
        return render(
            request,
            "foundational_edit_forbidden.html",
            {"policy": policy},
            status=403,
        )

    if request.method == "POST":
        form = PolicyEditForm(request.POST)
        if not form.is_valid():
            return render(request, "policy_edit.html", {"policy": policy, "form": form})

        # 1. Merge form values into the policy's existing frontmatter
        #    (preserves all keys the form does not expose).
        new_fm = dict(policy.frontmatter)
        new_fm["title"] = form.cleaned_data["title"]
        new_body = form.cleaned_data["body"]
        new_text = _render_policy_md(new_fm, new_body)

        # 2. Write the file in the local working copy.
        policy.policy_path.write_text(new_text, encoding="utf-8")

        # 3. Sequence the four GitHub operations.
        config = load_working_copy_config()
        working_dir = config.working_dir
        provider = GitHubProvider()
        author_name, author_email = get_git_author(request.user)
        branch_name = _make_branch_name(slug)
        summary = (form.cleaned_data.get("summary") or "").strip()
        commit_message = summary or f"Update {slug}"

        provider.branch(branch_name, working_dir)
        provider.commit(
            message=commit_message,
            files=[policy.policy_path],
            author_name=author_name,
            author_email=author_email,
            working_dir=working_dir,
        )
        provider.push(branch_name, working_dir)
        pr_title = f"Edit policies/{slug}: {commit_message}"
        pr_body = (
            f"Opened by PolicyCodex on behalf of {request.user.username}.\n"
            f"\n"
            f"Policy: policies/{slug}\n"
            f"Author: {author_name} <{author_email}>\n"
        )
        if summary:
            pr_body += f"\n{summary}\n"
        pr = provider.open_pr(
            title=pr_title,
            body=pr_body,
            head_branch=branch_name,
            base_branch=config.branch,
            working_dir=working_dir,
        )
        return render(
            request,
            "policy_edit_success.html",
            {"policy": policy, "pr": pr},
        )

    form = PolicyEditForm(initial={
        "title": policy.frontmatter.get("title", policy.slug),
        "body": policy.body,
        "summary": "",
    })
    return render(request, "policy_edit.html", {"policy": policy, "form": form})
```

Notes for the implementer:
- The local import of `PolicyEditForm` from Task 3's placeholder view goes away here (replaced by the top-of-file import). Make sure the old local import is removed.
- The view renders the success page directly (no redirect-after-POST) because the success page carries one-shot context (the PR URL + number) and the user is not expected to refresh. This trades the textbook PRG pattern for simpler state handling. The `follow=True` test in Step 1 accepts either pattern (`status=200` after follow); the simpler render-direct version is what this code does.

- [ ] **Step 5: Run to confirm pass**

```bash
/Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest core/tests/test_policy_edit.py -v 2>&1 | tail -15
```

Expected: 12 passing (9 from Tasks 3-5 plus 3 new).

If `test_post_valid_calls_branch_commit_push_open_pr_in_order` fails on the call-order check, double-check the four calls are sequenced in the exact order `branch → commit → push → open_pr` and that there are no other calls to the mock between them.

- [ ] **Step 6: Commit**

```bash
git add core/views.py core/templates/policy_edit_success.html core/tests/test_policy_edit.py
git commit -m "feat(APP-07): POST writes file + sequences branch/commit/push/open_pr"
```

---

## Task 7: GitHubProvider failure paths + form validation errors (TDD)

**Files:**
- Modify: `core/views.py`
- Modify: `core/tests/test_policy_edit.py`

The view as it stands will 500 if any `provider.*` call raises. This task wraps them in a single try/except, surfaces a Django message, and re-renders the form preserving the user's input.

- [ ] **Step 1: Write the failing tests**

Append to `core/tests/test_policy_edit.py`:

```python
# --- Provider failure paths ---

@pytest.mark.parametrize("failing_method,error_message_fragment", [
    ("branch", "branch"),
    ("commit", "commit"),
    ("push", "push"),
    ("open_pr", "open"),
])
def test_post_renders_form_with_error_on_provider_failure(
    client, user, tmp_path, failing_method, error_message_fragment,
):
    """When any of branch/commit/push/open_pr raises, the form re-renders
    with a user-visible error and HTTP 200 (not 500)."""
    client.force_login(user)
    repo_dir = tmp_path / "diocese-policies"
    policies_dir = repo_dir / "policies"
    policies_dir.mkdir(parents=True)
    policy_file = policies_dir / "onboarding.md"
    policy_file.write_text("---\ntitle: T\n---\nb\n", encoding="utf-8")
    real_policy = LogicalPolicy(
        slug="onboarding", kind="flat", policy_path=policy_file, data_path=None,
        frontmatter={"title": "T"}, body="b\n", foundational=False, provides=(),
    )
    with override_settings(
        POLICYCODEX_POLICY_REPO_URL="https://github.com/example/diocese-policies.git",
        POLICYCODEX_WORKING_COPY_ROOT=str(tmp_path),
    ):
        with patch("core.views.Path.exists", return_value=True):
            with patch("core.views.BundleAwarePolicyReader") as MockReader:
                MockReader.return_value.read.return_value = iter([real_policy])
                with patch("core.views.GitHubProvider") as MockProvider:
                    instance = MockProvider.return_value
                    # Default to success then make ONE method raise.
                    instance.open_pr.return_value = {"pr_number": 1, "url": "u", "state": "open"}
                    getattr(instance, failing_method).side_effect = RuntimeError(
                        f"git {failing_method} failed (exit 1): nope"
                    )
                    response = client.post(
                        "/policies/onboarding/edit/",
                        data={"title": "T2", "body": "b2\n", "summary": "msg"},
                    )
    # No 500.
    assert response.status_code == 200
    body = response.content.decode()
    # The edit form is re-rendered (not the success page).
    assert "Open PR" in body  # the submit button label
    # User input is preserved.
    assert 'value="T2"' in body
    assert "b2" in body
    # A user-facing error message is present.
    assert "couldn't" in body.lower() or "failed" in body.lower() or "error" in body.lower()


def test_post_invalid_form_rerenders_with_errors(client, user, tmp_path):
    """Missing required fields re-renders the form with field errors and HTTP 200."""
    client.force_login(user)
    repo_dir = tmp_path / "diocese-policies"
    policies_dir = repo_dir / "policies"
    policies_dir.mkdir(parents=True)
    policy_file = policies_dir / "onboarding.md"
    policy_file.write_text("---\ntitle: T\n---\nb\n", encoding="utf-8")
    real_policy = LogicalPolicy(
        slug="onboarding", kind="flat", policy_path=policy_file, data_path=None,
        frontmatter={"title": "T"}, body="b\n", foundational=False, provides=(),
    )
    with override_settings(
        POLICYCODEX_POLICY_REPO_URL="https://github.com/example/diocese-policies.git",
        POLICYCODEX_WORKING_COPY_ROOT=str(tmp_path),
    ):
        with patch("core.views.Path.exists", return_value=True):
            with patch("core.views.BundleAwarePolicyReader") as MockReader:
                MockReader.return_value.read.return_value = iter([real_policy])
                with patch("core.views.GitHubProvider") as MockProvider:
                    response = client.post(
                        "/policies/onboarding/edit/",
                        data={"title": "", "body": "", "summary": ""},
                    )
                    # Provider was NEVER called because form was invalid.
                    MockProvider.return_value.branch.assert_not_called()
    assert response.status_code == 200
    body = response.content.decode()
    # Form re-rendered with errors (Django's default error label or the field error UL).
    assert "required" in body.lower() or "errorlist" in body.lower() or "This field" in body
```

- [ ] **Step 2: Run to confirm failure**

```bash
/Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest core/tests/test_policy_edit.py -v 2>&1 | tail -15
```

Expected: 12 passing (Tasks 3-6) + 5 failing (4 parametrized provider-failure cases + the invalid-form case). The provider-failure cases fail because the current view raises an unhandled `RuntimeError` (500); the invalid-form case actually already passes because Django re-renders on `form.is_valid() is False` (Task 6 handles it). If the invalid-form case passes, only 4 fail. Either way, continue.

- [ ] **Step 3: Wrap the provider sequence in try/except**

Edit `core/views.py`. Replace the POST branch's provider-call sequence with a try/except. The relevant section becomes:

```python
        # 3. Sequence the four GitHub operations.
        config = load_working_copy_config()
        working_dir = config.working_dir
        provider = GitHubProvider()
        author_name, author_email = get_git_author(request.user)
        branch_name = _make_branch_name(slug)
        summary = (form.cleaned_data.get("summary") or "").strip()
        commit_message = summary or f"Update {slug}"

        try:
            provider.branch(branch_name, working_dir)
            provider.commit(
                message=commit_message,
                files=[policy.policy_path],
                author_name=author_name,
                author_email=author_email,
                working_dir=working_dir,
            )
            provider.push(branch_name, working_dir)
            pr_title = f"Edit policies/{slug}: {commit_message}"
            pr_body = (
                f"Opened by PolicyCodex on behalf of {request.user.username}.\n"
                f"\n"
                f"Policy: policies/{slug}\n"
                f"Author: {author_name} <{author_email}>\n"
            )
            if summary:
                pr_body += f"\n{summary}\n"
            pr = provider.open_pr(
                title=pr_title,
                body=pr_body,
                head_branch=branch_name,
                base_branch=config.branch,
                working_dir=working_dir,
            )
        except (RuntimeError, ValueError) as exc:
            logger.error("APP-07 provider failure on slug=%s: %s", slug, exc)
            messages.error(
                request,
                "Couldn't open the pull request. The change is saved locally; "
                "ask your administrator to retry from the server logs.",
            )
            return render(
                request,
                "policy_edit.html",
                {"policy": policy, "form": form},
            )

        return render(
            request,
            "policy_edit_success.html",
            {"policy": policy, "pr": pr},
        )
```

The `return render(..., "policy_edit_success.html", ...)` at the end is the success path (was the last line of the POST branch before). Make sure it stays OUTSIDE the try/except, reached only when all four provider calls succeeded.

- [ ] **Step 4: Run to confirm pass**

```bash
/Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest core/tests/test_policy_edit.py -v 2>&1 | tail -20
```

Expected: 17 passing (12 from Tasks 3-6 plus 5 new — 4 parametrized + 1 invalid-form).

- [ ] **Step 5: Full repo test suite still green**

```bash
cd /Users/chuck/PolicyWonk && /Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest -q 2>&1 | tail -3
```

Expected: `201 passed` (180 baseline + 4 from Task 2 writer + 17 from Tasks 3-7 view tests). If the count is off, capture the actual number for the self-report and investigate.

- [ ] **Step 6: Commit**

```bash
git add core/views.py core/tests/test_policy_edit.py
git commit -m "feat(APP-07): provider failure → re-render form with error message"
```

---

## Task 8: Final verification + handoff

**Files:**
- None modified.

- [ ] **Step 1: Confirm `manage.py check` still clean**

```bash
cd /Users/chuck/PolicyWonk && /Users/chuck/PolicyWonk/spike/venv/bin/python manage.py check 2>&1 | tail -3
```

Expected: `System check identified no issues (0 silenced).` (If `POLICYCODEX_POLICY_REPO_URL` is unset in the worktree env, expect ONE Warning from APP-21; that is still exit 0.)

- [ ] **Step 2: Grep for ship-generic violations in new code**

```bash
grep -RInE "pt[-_]|pensacola|tallahassee|PT_|PT-" \
  core/views.py core/forms.py core/policy_writer.py \
  core/templates/policy_edit.html \
  core/templates/policy_edit_success.html \
  core/templates/foundational_edit_forbidden.html \
  core/tests/test_policy_edit.py core/tests/test_policy_writer.py
```

Expected: no output (clean). If any hits, surface and fix before commit.

- [ ] **Step 3: Grep for em dashes in new content**

```bash
grep -RIn $'\xe2\x80\x94\|\xe2\x80\x93' \
  core/views.py core/forms.py core/policy_writer.py \
  core/templates/policy_edit.html \
  core/templates/policy_edit_success.html \
  core/templates/foundational_edit_forbidden.html \
  core/tests/test_policy_edit.py core/tests/test_policy_writer.py
```

Expected: no output. If any hits, surface and fix before commit.

- [ ] **Step 4: Optional manual smoke (only if credentials available)**

If you have the PolicyCodex GitHub App credentials in `~/.config/policycodex/config.env` and a working copy already cloned, you can manually smoke the full edit-form flow against a real (test) PR:

```bash
cd /Users/chuck/PolicyWonk
# Use a SCRATCH branch on a TEST repo (NEVER pt-policy main).
export POLICYCODEX_POLICY_REPO_URL="https://github.com/<your-test-org>/<test-repo>.git"
export POLICYCODEX_POLICY_BRANCH=main
export POLICYCODEX_WORKING_COPY_ROOT=/tmp/app07-smoke
/Users/chuck/PolicyWonk/spike/venv/bin/python manage.py pull_working_copy
# Create a superuser if one does not exist:
echo "from django.contrib.auth.models import User; User.objects.filter(username='admin').exists() or User.objects.create_user('admin', 'admin@example.com', 'admin')" | /Users/chuck/PolicyWonk/spike/venv/bin/python manage.py shell
/Users/chuck/PolicyWonk/spike/venv/bin/python manage.py runserver &
SERVER_PID=$!
sleep 2
# In a browser: navigate to http://127.0.0.1:8000/, sign in as admin/admin,
# click into a non-foundational policy's edit link (you'll wire this in APP-06 follow-up;
# for the smoke, just go to /policies/<known-slug>/edit/), change the title, submit,
# verify a PR appears at the remote.
echo "Smoke server running at http://127.0.0.1:8000/ — PID $SERVER_PID. Kill when done."
```

If you do not have credentials, SKIP this step and note the skip in the self-report. The unit tests are authoritative.

- [ ] **Step 5: Confirm clean branch + commit history**

```bash
git status
git log --oneline main..HEAD
```

Expected: clean working tree; 6 commits since BASE `5017488`:

1. `feat(APP-07): lossless policy.md writer helper (_render_policy_md)`
2. `feat(APP-07): policy_edit URL + login_required + 404 on unknown slug`
3. `feat(APP-07): PolicyEditForm + GET pre-population from working copy`
4. `feat(APP-07): foundational-policy gate returns 403 with explanation`
5. `feat(APP-07): POST writes file + sequences branch/commit/push/open_pr`
6. `feat(APP-07): provider failure → re-render form with error message`

If counts differ, surface in the self-report.

- [ ] **Step 6: Compose self-report**

Cover:
- Goal in one sentence.
- Branch name (`worktree-agent-<id>`) and final commit SHA.
- Files created / modified.
- Commit list with messages.
- Test count before / after (expect 180 → 201).
- `manage.py check` result.
- Smoke result (Step 4): PASS / SKIPPED / FAIL.
- Any deviations from the plan + rationale.
- Status: DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT.

- [ ] **Step 7: Handoff**

Do not merge to main. Do not push. The dispatching session (Scarlet) will route the branch through spec-compliance review and code-quality review per `superpowers:subagent-driven-development`.

---

## Definition of Done

- `core/policy_writer.py` exists with `_render_policy_md(frontmatter, body) -> str` that is lossless against `_split_frontmatter`.
- `core/forms.py` exists with `PolicyEditForm(forms.Form)` exposing exactly `title`, `body`, `summary` (and no other fields).
- `core/views.py` has `policy_edit(request, slug)` decorated with `@login_required`, plus the `_find_policy` and `_make_branch_name` helpers.
- `core/urls.py` has `path("policies/<slug:slug>/edit/", views.policy_edit, name="policy_edit")`.
- `core/templates/policy_edit.html` renders the form, CSRF token, error display, and a Cancel link back to `/catalog/`.
- `core/templates/policy_edit_success.html` shows the PR number + URL + a Back to catalog link.
- `core/templates/foundational_edit_forbidden.html` is rendered with HTTP 403 when the slug is foundational, mentions the slug, mentions "foundational", and links to `/catalog/`.
- `core/tests/test_policy_writer.py` has 4 tests passing (round-trip, unexposed-key preservation, empty-frontmatter, no-em-dashes).
- `core/tests/test_policy_edit.py` has 17 tests passing covering: URL resolves, login required, 404 on unknown slug, form has expected fields, form required-field validation, form title max length, GET pre-population, foundational gate GET 403, foundational gate POST 403, POST happy path (call sequence + file write + author identity + branch name pattern), default commit message, success page renders PR URL, 4 parametrized provider-failure paths (branch/commit/push/open_pr each), invalid form re-renders with errors.
- POST happy path:
  - Writes the policy file via `_render_policy_md`, preserving unexposed frontmatter keys (owner, effective_date, etc.).
  - Calls `GitHubProvider.branch → commit → push → open_pr` in that order.
  - Commit author = `get_git_author(request.user)` (NOT the GitHub App's own identity).
  - Branch name matches the pattern `policycodex/edit-<slug>-<8-hex-chars>`.
  - PR body contains the literal phrase "Opened by PolicyCodex on behalf of `<username>`".
- Provider-failure handling: any `RuntimeError` or `ValueError` from `branch`/`commit`/`push`/`open_pr` re-renders `policy_edit.html` with the user's input preserved, a `messages.error` flash, and HTTP 200 (never 500). The view also logs the failure at `logging.ERROR`.
- Foundational-policy gate applies to BOTH GET and POST.
- Full repo test suite: 180 → 201 passing.
- 6 commits on the branch since BASE `5017488`, all with `APP-07` in the message.
- No edits outside the 8 files in **File Structure**.
- No em dashes anywhere in new content.
- No PT-specific tokens (`pt`, `PT`, `pensacola`, `tallahassee`, `pt-policy`, `PT_`) anywhere in code, templates, or test files. The optional smoke env exports in Task 8 Step 4 use placeholder `<your-test-org>/<test-repo>` and do NOT name PT.

---

## Self-Review

**Spec coverage:**
- Ticket says "Edit form for a single policy: opens a branch, commits, opens PR" → Tasks 3 (URL + 404), 4 (form + GET), 6 (POST happy path) ✓
- Ticket depends on APP-04 and APP-06 → composes `GitHubProvider` from APP-04 (`branch`/`commit`/`push`/`open_pr`) and the `BundleAwarePolicyReader` + working-copy plumbing from APP-06 ✓
- Foundational-policy design "L1 protection: hide or disable edit for foundational policies" → Task 5 returns 403 with explanation (stronger than hide; APP-20 will also hide the link in the catalog UI, but defense in depth is correct here) ✓
- Author attribution: commits ARE authored by the user via `get_git_author`; the PR opener is the GitHub App but the body names the user → Task 6 ✓
- Branch naming: pattern locked at top of plan, used consistently in Task 6's implementation and Task 6's call-order test ✓
- Failure modes: each of the 4 provider calls is covered by a parametrized test that asserts no-500 and form re-render → Task 7 ✓

**Placeholder scan:** No "TBD", no "TODO", no "implement later", no "Similar to Task N" (the `_stub_policy` helper is copied verbatim because the engineer may read tasks out of order). Every test has assertions. Every template has actual HTML. Every error path has a `messages.error` AND a `logger.error`.

**Type consistency:**
- `LogicalPolicy` field access — `policy.slug`, `policy.kind`, `policy.policy_path`, `policy.frontmatter`, `policy.body`, `policy.foundational` — used identically across `_stub_policy`, `_find_policy`, the view's POST branch, and the templates. Matches `ingest/policy_reader.py:22-33`.
- `get_git_author(user) -> tuple[str, str]` — returned as `(author_name, author_email)`, passed to `provider.commit(author_name=..., author_email=...)` consistent with `app/git_provider/base.py:39-53` and the test in `app/git_provider/tests/test_github_provider.py:112-141`.
- `GitHubProvider.open_pr` returns `dict` with keys `pr_number`, `url`, `state` — used in the success template (`{{ pr.url }}`, `{{ pr.pr_number }}`) and in the test mock return values, matches `app/git_provider/github_provider.py:228-233`.
- Branch-name pattern `policycodex/edit-<slug>-<hex8>` — used in `_make_branch_name`, the call-order test assertion, the PR title constructor, and the success-page link target (indirectly via `pr.url`). All match.
- `_render_policy_md(frontmatter, body) -> str` — Task 2 signature; Task 6 calls it with `(new_fm, new_body)`. Consistent.
- Form field names (`title`, `body`, `summary`) — used in `PolicyEditForm`, the template's `{{ form.title }}` etc., the test POST payloads, and the view's `cleaned_data["title"]` etc. All match.

**Edge cases worth flagging (not blockers):**
- If the user submits the same edit twice in a row (re-loads the success page and re-clicks back, then re-submits with the same body), the second submission creates a fresh branch (UUID is fresh) and the commit succeeds because `policy_writer` rewrites the file even when content is unchanged — git's `git commit` will fail with "nothing to commit" UNLESS the file was modified, but the form ALWAYS modifies the title at minimum because the form's title round-trips through `safe_dump`. In the literal "no real change" case, `provider.commit` raises `RuntimeError` and Task 7's failure handler catches it — the user sees the form re-rendered with the error message. Not ideal UX (the message is misleading) but it does not crash. Refinement is a v0.2 polish task.
- The view does NOT pull or rebase the working copy before branching. If the local working copy is stale relative to remote `main`, the PR will still open against the current remote `main` (GitHub handles the merge-base automatically). For v0.1 this is acceptable; APP-05's cron-driven `pull_working_copy` keeps the working copy current enough.
- The view does NOT check that the branch name is not already taken on the remote. `provider.branch` will fail locally on duplicate-branch-name (since the local checkout would error), but a remote collision (extremely rare with 8 hex chars + slug + edit prefix) is not pre-checked. If it ever happens, the user gets the standard failure-path UX.

No issues found that block the plan.
