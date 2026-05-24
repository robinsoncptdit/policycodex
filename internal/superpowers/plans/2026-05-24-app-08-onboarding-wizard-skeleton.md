# APP-08 Onboarding Wizard Skeleton Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the routing, session-backed state, and navigation shell of a seven-screen onboarding wizard, with placeholder steps, so APP-09 through APP-16 can add per-screen content without touching navigation.

**Architecture:** A new Django app `app/onboarding/` (sibling to `app/working_copy/`). A pure `wizard.py` step registry is the single source of step identity/order. `state.py` wraps one Django session key (no DB). Two `@login_required` views (`onboarding_root` resumes; `onboarding_step` gates ahead-jumps, renders, and on POST navigates Continue/Back/Save-and-exit). Templates extend the existing core `base.html`.

**Tech Stack:** Django 5/6 function-based views, Django sessions, Django templates, pytest-django.

**Spec:** `internal/superpowers/specs/2026-05-24-app-08-onboarding-wizard-skeleton-design.md` (approved 2026-05-24).

**BASE:** `main` at SHA `4b1c847`.

**Correction to the spec (intentional):** the spec's view section said a valid GET sets `current_step` to the viewed step. That is wrong: it would let a backward review reset `furthest_step` and trap the user. This plan implements the correct rule: **GET never mutates `current_step`; only a `continue` POST advances it.** `current_step` therefore means "the resume point / furthest step reached," and `furthest_step()` stays monotonic. The spec line is corrected to match.

**Discipline reminders:**
- TDD: every test observed failing first.
- No em dashes anywhere (code, comments, templates, commit messages). Use periods or hyphens.
- Ship-generic: no `pt`, `PT`, `pensacola`, `tallahassee` tokens. The wizard is diocese-agnostic.
- Use `/Users/chuck/PolicyWonk/ai/venv/bin/python` for every test run (no root venv; system python lacks pytest).
- Function-based views, matching `core/views.py`. No DB model (session-backed per the spec).
- Do not flip `POLICYCODEX_ONBOARDING_COMPLETE` or commit wizard config; those are APP-15/APP-16. Leave the commented hook only.
- Do not build real per-screen content; the seven steps render one shared placeholder.

---

## File Structure

- Create: `app/onboarding/__init__.py` - empty package marker.
- Create: `app/onboarding/apps.py` - `OnboardingAppConfig`.
- Create: `app/onboarding/wizard.py` - `Step` dataclass, `STEPS` registry, nav helpers.
- Create: `app/onboarding/state.py` - `WizardState` (session wrapper).
- Create: `app/onboarding/views.py` - `onboarding_root`, `onboarding_step`, `_nav_context`.
- Create: `app/onboarding/urls.py` - two routes.
- Create: `app/onboarding/templates/onboarding/base_wizard.html`, `app/onboarding/templates/onboarding/step.html`.
- Create: `app/onboarding/tests/__init__.py`, `test_wizard.py`, `test_wizard_state.py`, `test_onboarding_views.py`.
- Modify: `policycodex_site/settings.py` - add the app to `INSTALLED_APPS`.
- Modify: `policycodex_site/urls.py` - include the onboarding URLs under `onboarding/`.

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
Expected: BASE SHA `4b1c847` or a descendant; branch is your auto-worktree branch; status clean.

- [ ] **Step 2: Merge `main` into your worktree branch**

Run:
```bash
git fetch
git merge main --no-edit
```
Expected: "Already up to date." or a clean fast-forward.

- [ ] **Step 3: Confirm baseline suite**

Run:
```bash
/Users/chuck/PolicyWonk/ai/venv/bin/python -m pytest -q
```
Expected: full suite passes (297 on BASE). Use this interpreter for every test run. If anything fails before you change a thing, STOP and report.

---

## Task 2: Step registry (`wizard.py`)

**Files:**
- Create: `app/onboarding/__init__.py` (empty)
- Create: `app/onboarding/tests/__init__.py` (empty)
- Create: `app/onboarding/wizard.py`
- Create: `app/onboarding/tests/test_wizard.py`

- [ ] **Step 1: Create the package markers**

Create empty files `app/onboarding/__init__.py` and `app/onboarding/tests/__init__.py`:
```bash
mkdir -p app/onboarding/tests
: > app/onboarding/__init__.py
: > app/onboarding/tests/__init__.py
```

- [ ] **Step 2: Write the failing tests**

Create `app/onboarding/tests/test_wizard.py`:

```python
"""Tests for the onboarding step registry (APP-08)."""
from app.onboarding.wizard import (
    STEPS,
    first_step,
    get_step,
    index_of,
    is_last,
    next_step,
    prev_step,
)


def test_registry_has_seven_steps_in_order():
    assert [s.slug for s in STEPS] == [
        "github-repo",
        "address-scheme",
        "versioning",
        "reviewer-roles",
        "retention",
        "llm-provider",
        "retention-policy",
    ]


def test_first_step():
    assert first_step().slug == "github-repo"


def test_get_step_known_and_unknown():
    assert get_step("versioning").title == "Versioning convention"
    assert get_step("nope") is None


def test_index_of():
    assert index_of("github-repo") == 0
    assert index_of("retention-policy") == 6
    assert index_of("nope") is None


def test_next_step():
    assert next_step("github-repo").slug == "address-scheme"
    assert next_step("retention-policy") is None
    assert next_step("nope") is None


def test_prev_step():
    assert prev_step("address-scheme").slug == "github-repo"
    assert prev_step("github-repo") is None
    assert prev_step("nope") is None


def test_is_last():
    assert is_last("retention-policy") is True
    assert is_last("github-repo") is False
```

- [ ] **Step 3: Run to verify failure**

Run:
```bash
/Users/chuck/PolicyWonk/ai/venv/bin/python -m pytest app/onboarding/tests/test_wizard.py -q
```
Expected: FAIL at import (`app.onboarding.wizard` does not exist).

- [ ] **Step 4: Create `app/onboarding/wizard.py`**

```python
"""Step registry and navigation helpers for the onboarding wizard (APP-08).

This is the single source of step identity and order. Views and templates
read it; APP-09 through APP-16 add per-screen content keyed by slug without
touching navigation.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Step:
    slug: str
    title: str


STEPS: tuple[Step, ...] = (
    Step("github-repo", "GitHub repository"),
    Step("address-scheme", "Address scheme"),
    Step("versioning", "Versioning convention"),
    Step("reviewer-roles", "Reviewer roles"),
    Step("retention", "Retention defaults"),
    Step("llm-provider", "LLM provider"),
    Step("retention-policy", "Retention policy"),
)

_BY_SLUG = {s.slug: s for s in STEPS}


def first_step() -> Step:
    return STEPS[0]


def get_step(slug: str) -> Step | None:
    return _BY_SLUG.get(slug)


def index_of(slug: str) -> int | None:
    step = _BY_SLUG.get(slug)
    return None if step is None else STEPS.index(step)


def next_step(slug: str) -> Step | None:
    idx = index_of(slug)
    if idx is None or idx + 1 >= len(STEPS):
        return None
    return STEPS[idx + 1]


def prev_step(slug: str) -> Step | None:
    idx = index_of(slug)
    if idx is None or idx == 0:
        return None
    return STEPS[idx - 1]


def is_last(slug: str) -> bool:
    return index_of(slug) == len(STEPS) - 1
```

- [ ] **Step 5: Run to verify pass**

Run:
```bash
/Users/chuck/PolicyWonk/ai/venv/bin/python -m pytest app/onboarding/tests/test_wizard.py -q
```
Expected: 7 passed.

- [ ] **Step 6: Commit**

```bash
git add app/onboarding/__init__.py app/onboarding/tests/__init__.py app/onboarding/wizard.py app/onboarding/tests/test_wizard.py
git commit -m "feat(APP-08): onboarding step registry + nav helpers"
```

---

## Task 3: Session-backed state (`state.py`)

**Files:**
- Create: `app/onboarding/state.py`
- Create: `app/onboarding/tests/test_wizard_state.py`

- [ ] **Step 1: Write the failing tests**

Create `app/onboarding/tests/test_wizard_state.py`:

```python
"""Tests for the session-backed wizard state (APP-08)."""
from app.onboarding.state import SESSION_KEY, WizardState


class FakeSession(dict):
    """Minimal stand-in for a Django session: a dict that also tracks `modified`."""
    modified = False


def test_initializes_with_first_step_and_flags_modified():
    s = FakeSession()
    state = WizardState(s)
    assert state.current_step == "github-repo"
    assert SESSION_KEY in s
    assert s.modified is True


def test_set_and_get_data_round_trip():
    s = FakeSession()
    state = WizardState(s)
    state.set_data("github-repo", {"repo": "x"})
    assert state.get_data("github-repo") == {"repo": "x"}
    assert state.get_data("versioning") == {}


def test_mark_complete_is_idempotent():
    s = FakeSession()
    state = WizardState(s)
    state.mark_complete("github-repo")
    state.mark_complete("github-repo")
    assert state.is_complete("github-repo") is True
    assert s[SESSION_KEY]["completed"] == ["github-repo"]


def test_furthest_step_tracks_highest_index():
    s = FakeSession()
    state = WizardState(s)
    state.mark_complete("github-repo")   # index 0
    state.mark_complete("versioning")    # index 2
    state.set_current("address-scheme")  # index 1
    assert state.furthest_step() == "versioning"


def test_persists_across_fresh_state_over_same_session():
    s = FakeSession()
    WizardState(s).set_data("retention", {"years": 7})
    # A new WizardState over the SAME session must see the data, proving the
    # mutators flagged the session modified and did not lose the nested write.
    assert WizardState(s).get_data("retention") == {"years": 7}


def test_reset_clears_state():
    s = FakeSession()
    state = WizardState(s)
    state.set_data("github-repo", {"a": 1})
    state.reset()
    assert SESSION_KEY not in s
```

- [ ] **Step 2: Run to verify failure**

Run:
```bash
/Users/chuck/PolicyWonk/ai/venv/bin/python -m pytest app/onboarding/tests/test_wizard_state.py -q
```
Expected: FAIL at import (`app.onboarding.state` does not exist).

- [ ] **Step 3: Create `app/onboarding/state.py`**

```python
"""Session-backed wizard state for onboarding (APP-08).

Wraps a single Django session key. Mutating a nested dict inside a Django
session does NOT auto-flag it dirty, so every mutator sets
session.modified = True.
"""
from __future__ import annotations

from app.onboarding.wizard import first_step, index_of

SESSION_KEY = "onboarding"


class WizardState:
    def __init__(self, session):
        self._session = session
        if SESSION_KEY not in session:
            session[SESSION_KEY] = {
                "current_step": first_step().slug,
                "completed": [],
                "data": {},
            }
            session.modified = True

    @property
    def _store(self) -> dict:
        return self._session[SESSION_KEY]

    @property
    def current_step(self) -> str:
        return self._store.get("current_step", first_step().slug)

    def set_current(self, slug: str) -> None:
        self._store["current_step"] = slug
        self._session.modified = True

    def get_data(self, slug: str) -> dict:
        return self._store["data"].get(slug, {})

    def set_data(self, slug: str, data: dict) -> None:
        self._store["data"][slug] = data
        self._session.modified = True

    def mark_complete(self, slug: str) -> None:
        if slug not in self._store["completed"]:
            self._store["completed"].append(slug)
            self._session.modified = True

    def is_complete(self, slug: str) -> bool:
        return slug in self._store["completed"]

    def furthest_step(self) -> str:
        best_slug = first_step().slug
        best_idx = 0
        for slug in (self.current_step, *self._store["completed"]):
            idx = index_of(slug)
            if idx is not None and idx > best_idx:
                best_idx = idx
                best_slug = slug
        return best_slug

    def all_data(self) -> dict:
        return dict(self._store["data"])

    def reset(self) -> None:
        self._session.pop(SESSION_KEY, None)
        self._session.modified = True
```

- [ ] **Step 4: Run to verify pass**

Run:
```bash
/Users/chuck/PolicyWonk/ai/venv/bin/python -m pytest app/onboarding/tests/test_wizard_state.py -q
```
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add app/onboarding/state.py app/onboarding/tests/test_wizard_state.py
git commit -m "feat(APP-08): session-backed wizard state"
```

---

## Task 4: App registration, URLs, templates, and GET views

**Files:**
- Create: `app/onboarding/apps.py`
- Modify: `policycodex_site/settings.py`
- Create: `app/onboarding/urls.py`
- Modify: `policycodex_site/urls.py`
- Create: `app/onboarding/templates/onboarding/base_wizard.html`, `step.html`
- Create: `app/onboarding/views.py`
- Create: `app/onboarding/tests/test_onboarding_views.py`

- [ ] **Step 1: Write the failing tests (GET-only)**

Create `app/onboarding/tests/test_onboarding_views.py`:

```python
"""Tests for the onboarding wizard views (APP-08)."""
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(username="admin", password="secret")


def test_urls_resolve():
    assert reverse("onboarding") == "/onboarding/"
    assert reverse("onboarding_step", kwargs={"step": "github-repo"}) == "/onboarding/github-repo/"


def test_onboarding_requires_login(client):
    resp = client.get("/onboarding/")
    assert resp.status_code == 302
    assert resp.url.startswith("/login/")


def test_root_redirects_to_first_step_when_fresh(client, user):
    client.force_login(user)
    resp = client.get("/onboarding/")
    assert resp.status_code == 302
    assert resp.url == "/onboarding/github-repo/"


def test_get_step_renders_title_and_indicator(client, user):
    client.force_login(user)
    resp = client.get("/onboarding/github-repo/")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "GitHub repository" in body
    assert "Step 1 of 7" in body


def test_unknown_step_returns_404(client, user):
    client.force_login(user)
    resp = client.get("/onboarding/not-a-step/")
    assert resp.status_code == 404


def test_ahead_jump_is_gated(client, user):
    client.force_login(user)
    # Fresh user: furthest is github-repo. Jumping to versioning redirects back.
    resp = client.get("/onboarding/versioning/")
    assert resp.status_code == 302
    assert resp.url == "/onboarding/github-repo/"
```

- [ ] **Step 2: Run to verify failure**

Run:
```bash
/Users/chuck/PolicyWonk/ai/venv/bin/python -m pytest app/onboarding/tests/test_onboarding_views.py -q
```
Expected: FAIL (no `onboarding` URL / app not installed).

- [ ] **Step 3: Create `app/onboarding/apps.py`**

```python
from django.apps import AppConfig


class OnboardingAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "app.onboarding"
    label = "onboarding"
```

- [ ] **Step 4: Register the app in `policycodex_site/settings.py`**

Find the `INSTALLED_APPS` list and add the onboarding app immediately after the working-copy line:

```python
    'core',
    'app.working_copy.apps.WorkingCopyAppConfig',
    'app.onboarding.apps.OnboardingAppConfig',
]
```

- [ ] **Step 5: Create `app/onboarding/urls.py`**

```python
"""URL routes for the onboarding wizard (APP-08)."""
from django.urls import path

from . import views

urlpatterns = [
    path("", views.onboarding_root, name="onboarding"),
    path("<slug:step>/", views.onboarding_step, name="onboarding_step"),
]
```

- [ ] **Step 6: Include the onboarding URLs in `policycodex_site/urls.py`**

`include` is already imported. Add the onboarding include before the root `core.urls` include:

```python
    path('onboarding/', include('app.onboarding.urls')),
    path('', include('core.urls')),
]
```

- [ ] **Step 7: Create the templates**

Create `app/onboarding/templates/onboarding/base_wizard.html`:

```html
{% extends "base.html" %}

{% block title %}Onboarding | PolicyCodex{% endblock %}

{% block content %}
  <h2>Onboarding</h2>
  <p class="wizard-progress">Step {{ index }} of {{ total }}: {{ step.title }}</p>

  <form method="post">
    {% csrf_token %}
    {% block step_content %}{% endblock %}
    <div class="wizard-nav">
      {% if prev_step %}
        <button type="submit" name="action" value="back">Back</button>
      {% endif %}
      {% if is_last %}
        <button type="submit" name="action" value="continue">Finish</button>
      {% else %}
        <button type="submit" name="action" value="continue">Continue</button>
      {% endif %}
      <button type="submit" name="action" value="save_exit">Save and exit</button>
    </div>
  </form>
{% endblock %}
```

Create `app/onboarding/templates/onboarding/step.html`:

```html
{% extends "onboarding/base_wizard.html" %}

{% block step_content %}
  <p class="wizard-placeholder">
    This screen's content lands in APP-09 through APP-16.
  </p>
{% endblock %}
```

- [ ] **Step 8: Create `app/onboarding/views.py` (root + step GET with gating)**

```python
"""Onboarding wizard views (APP-08): routing, gating, and navigation shell."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect, render

from app.onboarding import wizard
from app.onboarding.state import WizardState


def _nav_context(step, state):
    return {
        "step": step,
        "index": wizard.index_of(step.slug) + 1,
        "total": len(wizard.STEPS),
        "prev_step": wizard.prev_step(step.slug),
        "next_step": wizard.next_step(step.slug),
        "is_last": wizard.is_last(step.slug),
        "is_complete": state.is_complete(step.slug),
    }


@login_required
def onboarding_root(request):
    """Resume: send the admin to their current (furthest reached) step."""
    state = WizardState(request.session)
    return redirect("onboarding_step", step=state.current_step)


@login_required
def onboarding_step(request, step):
    target = wizard.get_step(step)
    if target is None:
        raise Http404(f"Unknown onboarding step: {step}")

    state = WizardState(request.session)

    # GET gating: cannot skip ahead of the furthest step reached. Revisiting
    # the current step or any earlier/completed step is allowed. GET never
    # mutates current_step; only a `continue` POST advances it (keeps
    # furthest_step monotonic so backward review does not trap the user).
    furthest = state.furthest_step()
    if wizard.index_of(step) > wizard.index_of(furthest):
        return redirect("onboarding_step", step=furthest)

    return render(request, "onboarding/step.html", _nav_context(target, state))
```

- [ ] **Step 9: Run to verify pass**

Run:
```bash
/Users/chuck/PolicyWonk/ai/venv/bin/python -m pytest app/onboarding/tests/test_onboarding_views.py -q
```
Expected: 6 passed.

- [ ] **Step 10: Commit**

```bash
git add app/onboarding/apps.py app/onboarding/urls.py app/onboarding/views.py \
        app/onboarding/templates/onboarding/base_wizard.html \
        app/onboarding/templates/onboarding/step.html \
        app/onboarding/tests/test_onboarding_views.py \
        policycodex_site/settings.py policycodex_site/urls.py
git commit -m "feat(APP-08): onboarding app registration, URLs, templates, GET views"
```

---

## Task 5: POST navigation (Continue / Back / Save-and-exit / completion)

**Files:**
- Modify: `app/onboarding/views.py`
- Modify: `app/onboarding/tests/test_onboarding_views.py`

- [ ] **Step 1: Write the failing tests**

Append to `app/onboarding/tests/test_onboarding_views.py`:

```python
def test_continue_advances_and_marks_complete(client, user):
    client.force_login(user)
    resp = client.post("/onboarding/github-repo/", {"action": "continue"})
    assert resp.status_code == 302
    assert resp.url == "/onboarding/address-scheme/"
    # Resume now points at the advanced step.
    assert client.get("/onboarding/").url == "/onboarding/address-scheme/"


def test_back_goes_to_previous_step(client, user):
    client.force_login(user)
    client.post("/onboarding/github-repo/", {"action": "continue"})
    resp = client.post("/onboarding/address-scheme/", {"action": "back"})
    assert resp.status_code == 302
    assert resp.url == "/onboarding/github-repo/"


def test_back_on_first_step_is_noop_redirect(client, user):
    client.force_login(user)
    resp = client.post("/onboarding/github-repo/", {"action": "back"})
    assert resp.status_code == 302
    assert resp.url == "/onboarding/github-repo/"


def test_save_exit_redirects_to_catalog(client, user):
    client.force_login(user)
    resp = client.post("/onboarding/github-repo/", {"action": "save_exit"})
    assert resp.status_code == 302
    assert resp.url == "/catalog/"


def test_can_revisit_completed_step_without_trapping(client, user):
    client.force_login(user)
    client.post("/onboarding/github-repo/", {"action": "continue"})  # on address-scheme
    # Revisit the completed first step: allowed (200), and we can still go forward.
    assert client.get("/onboarding/github-repo/").status_code == 200
    assert client.get("/onboarding/address-scheme/").status_code == 200


def test_last_step_continue_completes_and_redirects_to_catalog(client, user):
    client.force_login(user)
    slugs = [
        "github-repo", "address-scheme", "versioning", "reviewer-roles",
        "retention", "llm-provider", "retention-policy",
    ]
    for slug in slugs[:-1]:
        client.post(f"/onboarding/{slug}/", {"action": "continue"})
    resp = client.post("/onboarding/retention-policy/", {"action": "continue"})
    assert resp.status_code == 302
    assert resp.url == "/catalog/"
```

- [ ] **Step 2: Run to verify failure**

Run:
```bash
/Users/chuck/PolicyWonk/ai/venv/bin/python -m pytest app/onboarding/tests/test_onboarding_views.py -q
```
Expected: the new tests FAIL (POST currently falls through to the GET render, so `test_continue_advances_and_marks_complete` gets 200 not 302). The Task-4 GET tests still pass.

- [ ] **Step 3: Add the POST branch to `onboarding_step`**

In `app/onboarding/views.py`, insert the POST handling immediately after `state = WizardState(request.session)` and before the GET gating comment:

```python
    if request.method == "POST":
        # Per-step form validation/processing lands in APP-09..16; the
        # skeleton treats every step's submit as a no-op save then navigates.
        action = request.POST.get("action")
        if action == "back":
            prev = wizard.prev_step(step)
            return redirect("onboarding_step", step=prev.slug if prev else step)
        if action == "save_exit":
            messages.info(request, "Your progress is saved. Resume onboarding any time.")
            return redirect("catalog")
        if action == "continue":
            state.mark_complete(step)
            if wizard.is_last(step):
                # APP-15/APP-16 hook: commit wizard config to the policy repo
                # and flip POLICYCODEX_ONBOARDING_COMPLETE. Not done here.
                messages.success(request, "Onboarding steps complete.")
                return redirect("catalog")
            nxt = wizard.next_step(step)
            state.set_current(nxt.slug)
            return redirect("onboarding_step", step=nxt.slug)
        # Unknown or missing action: fall through to a defensive re-render.
        return render(request, "onboarding/step.html", _nav_context(target, state))
```

The function now reads, in order: 404 check, build `state`, the POST block above, then the existing GET gating + render.

- [ ] **Step 4: Run to verify pass**

Run:
```bash
/Users/chuck/PolicyWonk/ai/venv/bin/python -m pytest app/onboarding/tests/test_onboarding_views.py -q
```
Expected: 12 passed (6 from Task 4 + 6 new).

- [ ] **Step 5: Commit**

```bash
git add app/onboarding/views.py app/onboarding/tests/test_onboarding_views.py
git commit -m "feat(APP-08): wizard POST navigation (continue, back, save-exit, completion)"
```

---

## Task 6: Full-suite verification

**Files:** none modified.

- [ ] **Step 1: Run the onboarding tests verbosely**

Run:
```bash
/Users/chuck/PolicyWonk/ai/venv/bin/python -m pytest app/onboarding/tests/ -v
```
Expected: 25 passed (7 wizard + 6 state + 12 views).

- [ ] **Step 2: Run the entire suite**

Run:
```bash
/Users/chuck/PolicyWonk/ai/venv/bin/python -m pytest -q
```
Expected: full suite PASS. Baseline 297; this ticket adds 25 tests, so expect 322 and no other count changes. Report the exact observed number per superpowers:verification-before-completion. If any pre-existing test regresses, STOP and report.

- [ ] **Step 3: Smoke the Django config and confirm scope/tokens**

Run:
```bash
/Users/chuck/PolicyWonk/ai/venv/bin/python manage.py check
git diff main --stat
grep -rniE "pensacola|tallahassee" app/onboarding/ || echo "clean: no diocese tokens"
grep -rn "—" app/onboarding/ || echo "clean: no em dashes"
```
Expected: `manage.py check` reports no issues (the new app loads); `--stat` shows only `app/onboarding/**` plus `policycodex_site/settings.py` and `policycodex_site/urls.py`; both grep guards print their "clean" line.

---

## Out of Scope (skeleton only)

- Real per-screen forms, provider calls, and AI extraction (APP-09 through APP-16; they fill `step_content` / `set_data` by slug).
- The configuration commit and the `POLICYCODEX_ONBOARDING_COMPLETE` flip (APP-15/APP-16; the commented hook marks where they attach).
- DB-backed persistence (session per the spec's Decision 2).
- POST-time ahead-jump gating (only GET is gated; the sequential POST flow plus GET gating is sufficient for a single-admin v0.1 wizard).
- Forcing users into the wizard when onboarding is incomplete, or blocking it when complete.

---

## Self-Review

1. **Spec coverage.** App layout (Task 4), step registry (Task 2), `WizardState` session API (Task 3), `onboarding_root` resume + `onboarding_step` gating/render (Task 4), POST navigation + completion (Task 5), templates (Task 4), and the full test list (Tasks 2/3/4/5) all map to spec sections. The spec's "GET sets current_step" line is corrected (see header note) and implemented as "GET never mutates current_step."
2. **Placeholder scan.** Every code/template/test step is complete; every command has an expected result. The step.html "lands in APP-09..16" line is the spec-defined placeholder content, not a plan placeholder.
3. **Type/string consistency.** The seven slugs are identical across `wizard.py` (Task 2), `state.py` defaults (Task 3), the view walk and the test walk (Task 5). `WizardState` method names (`current_step`, `set_current`, `get_data`, `set_data`, `mark_complete`, `is_complete`, `furthest_step`, `all_data`, `reset`) match between `state.py`, the state tests, and the views. `_nav_context` keys (`step`, `index`, `total`, `prev_step`, `next_step`, `is_last`, `is_complete`) match the template's usage (`step.title`, `index`, `total`, `prev_step`, `is_last`). POST action values (`back`, `continue`, `save_exit`) match between the template buttons and the view's `request.POST.get("action")` checks. URL names (`onboarding`, `onboarding_step`, `catalog`) resolve against `app/onboarding/urls.py` and the existing `core/urls.py`.
