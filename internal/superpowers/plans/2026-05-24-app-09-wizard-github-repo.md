# APP-09 Wizard Screen 1 (GitHub Repository) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the onboarding wizard's `github-repo` step a real form (connect-existing or create-new), validated and persisted to the wizard session state, via a reusable slug->form registry that APP-10..16 will follow.

**Architecture:** A new `app/onboarding/forms.py` holds `GitHubRepoForm` and a `form_class_for(slug)` registry. The generic `onboarding_step` view binds the step's form (when registered) on GET, validates on `continue`, and persists `cleaned_data` to `WizardState`. The generic `step.html` renders the form when present. No clone/create side effects: this screen captures config only; provisioning is deferred to wizard completion (APP-15/16).

**Tech Stack:** Django forms + views + templates, pytest-django. Test interpreter: `/Users/chuck/PolicyWonk/ai/venv/bin/python` (run from the worktree root).

**Design doc:** `internal/superpowers/specs/2026-05-24-app-09-wizard-github-repo-design.md`

---

## Scope notes (read before starting)

- **Capture-only (decided):** do NOT call `GitHubProvider.clone` or create a repo. Persist the captured config to `WizardState`; provisioning is APP-15/16's job.
- **Form-registry pattern (decided):** add the registry + generic-view wiring so APP-10..16 register a form and get binding/validation/persistence for free.
- Existing tests that POST a bare `{"action": "continue"}` to `github-repo` MUST be updated to include valid form data (Task 4); the step now has a real form.
- Baseline suite after AI-13: 360 tests.

## File Structure

- Create: `app/onboarding/forms.py` - `GitHubRepoForm`, `form_class_for`.
- Create: `app/onboarding/tests/test_onboarding_forms.py` - form unit tests.
- Modify: `app/onboarding/views.py` - `_step_context` helper + form binding/validation in `onboarding_step`.
- Modify: `app/onboarding/templates/onboarding/step.html` - render the form when present.
- Modify: `app/onboarding/tests/test_onboarding_views.py` - update 3 existing tests + add new ones.

---

### Task 1: `GitHubRepoForm` + registry

**Files:**
- Create: `app/onboarding/forms.py`
- Test: `app/onboarding/tests/test_onboarding_forms.py`

- [ ] **Step 1: Write the failing tests**

```python
"""Tests for onboarding forms (APP-09)."""
from app.onboarding.forms import GitHubRepoForm, form_class_for


def test_registry_maps_github_repo():
    assert form_class_for("github-repo") is GitHubRepoForm
    assert form_class_for("address-scheme") is None


def test_valid_connect():
    form = GitHubRepoForm(data={
        "mode": "connect",
        "repo_url": "https://github.com/acme/policies",
        "branch": "main",
    })
    assert form.is_valid(), form.errors
    assert form.cleaned_data["mode"] == "connect"
    assert form.cleaned_data["repo_url"] == "https://github.com/acme/policies"


def test_valid_create():
    form = GitHubRepoForm(data={
        "mode": "create",
        "org": "acme",
        "repo_name": "policies",
        "branch": "main",
    })
    assert form.is_valid(), form.errors
    assert form.cleaned_data["org"] == "acme"
    assert form.cleaned_data["repo_name"] == "policies"


def test_connect_requires_repo_url():
    form = GitHubRepoForm(data={"mode": "connect", "branch": "main"})
    assert not form.is_valid()
    assert "repo_url" in form.errors


def test_connect_rejects_non_github_url():
    form = GitHubRepoForm(data={
        "mode": "connect",
        "repo_url": "https://gitlab.com/acme/policies",
        "branch": "main",
    })
    assert not form.is_valid()
    assert "repo_url" in form.errors


def test_create_requires_org_and_repo_name():
    form = GitHubRepoForm(data={"mode": "create", "branch": "main"})
    assert not form.is_valid()
    assert "org" in form.errors
    assert "repo_name" in form.errors


def test_branch_defaults_to_main():
    # branch omitted -> field initial is "main"; an unbound form exposes it.
    form = GitHubRepoForm()
    assert form.fields["branch"].initial == "main"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/Users/chuck/PolicyWonk/ai/venv/bin/python -m pytest app/onboarding/tests/test_onboarding_forms.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.onboarding.forms'`

- [ ] **Step 3: Write the implementation**

```python
"""Onboarding wizard forms + a slug->form registry (APP-09).

Each wizard step may register a Django Form here. The generic
`onboarding_step` view binds the registered form, validates it on
`continue`, and persists `cleaned_data` into WizardState. Steps without a
registered form keep the skeleton's no-op save behavior.

APP-09 ships the first step's form (github-repo). It captures the repo
choice only; cloning/creating the repo is deferred to wizard-completion
provisioning (APP-15/16).
"""
from __future__ import annotations

import re

from django import forms

# Mirrors app/git_provider/github_provider.py's owner/repo URL shape.
_GITHUB_URL_RE = re.compile(r"^https://github\.com/[^/]+/.+?(?:\.git)?/?$")


class GitHubRepoForm(forms.Form):
    MODE_CHOICES = [
        ("connect", "Connect an existing repository"),
        ("create", "Create a new repository"),
    ]

    mode = forms.ChoiceField(
        choices=MODE_CHOICES,
        widget=forms.RadioSelect,
        initial="connect",
        label="Repository",
    )
    repo_url = forms.URLField(
        required=False,
        label="Existing repository URL",
        help_text="For Connect: https://github.com/<org>/<repo>",
    )
    org = forms.CharField(
        required=False,
        label="GitHub organization or owner",
        help_text="For Create",
    )
    repo_name = forms.CharField(
        required=False,
        label="New repository name",
        help_text="For Create",
    )
    branch = forms.CharField(initial="main", label="Default branch")

    def clean(self):
        cleaned = super().clean()
        mode = cleaned.get("mode")
        if mode == "connect":
            url = cleaned.get("repo_url")
            if not url:
                self.add_error("repo_url", "Provide the existing repository URL.")
            elif not _GITHUB_URL_RE.match(url):
                self.add_error(
                    "repo_url",
                    "Must be an https://github.com/<org>/<repo> URL.",
                )
        elif mode == "create":
            if not cleaned.get("org"):
                self.add_error("org", "Provide the organization or owner.")
            if not cleaned.get("repo_name"):
                self.add_error("repo_name", "Provide the new repository name.")
        return cleaned


_FORMS = {
    "github-repo": GitHubRepoForm,
}


def form_class_for(slug):
    """Return the Form class registered for a wizard step slug, or None."""
    return _FORMS.get(slug)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/Users/chuck/PolicyWonk/ai/venv/bin/python -m pytest app/onboarding/tests/test_onboarding_forms.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add app/onboarding/forms.py app/onboarding/tests/test_onboarding_forms.py
git commit -m "feat(APP-09): GitHubRepoForm + onboarding form registry"
```

---

### Task 2: Wire the form into the generic step view

**Files:**
- Modify: `app/onboarding/views.py`

- [ ] **Step 1: Add the import and a context helper**

At the top of `app/onboarding/views.py`, add to the imports:

```python
from app.onboarding import forms as onboarding_forms
```

After `_nav_context`, add:

```python
def _step_context(target, state, form=None):
    ctx = _nav_context(target, state)
    if form is not None:
        ctx["form"] = form
    return ctx
```

- [ ] **Step 2: Replace the `continue` branch and the GET render in `onboarding_step`**

Replace the existing `if action == "continue":` block with:

```python
        if action == "continue":
            form_cls = onboarding_forms.form_class_for(step)
            if form_cls is not None:
                form = form_cls(request.POST)
                if not form.is_valid():
                    # Invalid input: re-render with errors; do NOT advance.
                    return render(
                        request,
                        "onboarding/step.html",
                        _step_context(target, state, form),
                    )
                state.set_data(step, form.cleaned_data)
            state.mark_complete(step)
            if wizard.is_last(step):
                # APP-15/APP-16 hook: commit wizard config to the policy repo
                # and flip POLICYCODEX_ONBOARDING_COMPLETE. Not done here.
                messages.success(request, "Onboarding steps complete.")
                return redirect("catalog")
            nxt = wizard.next_step(step)
            state.set_current(nxt.slug)
            return redirect("onboarding_step", step=nxt.slug)
```

Replace the unknown-action fall-through render:

```python
        # Unknown or missing action: fall through to a defensive re-render.
        return render(request, "onboarding/step.html", _nav_context(target, state))
```

with:

```python
        # Unknown or missing action: fall through to a defensive re-render.
        form_cls = onboarding_forms.form_class_for(step)
        form = form_cls(request.POST) if form_cls is not None else None
        return render(request, "onboarding/step.html", _step_context(target, state, form))
```

Replace the final GET render:

```python
    return render(request, "onboarding/step.html", _nav_context(target, state))
```

with:

```python
    form_cls = onboarding_forms.form_class_for(step)
    form = form_cls(initial=state.get_data(step)) if form_cls is not None else None
    return render(request, "onboarding/step.html", _step_context(target, state, form))
```

(The GET ahead-jump gate above this stays unchanged.)

- [ ] **Step 3: Run the onboarding view tests (3 will now fail - expected)**

Run: `/Users/chuck/PolicyWonk/ai/venv/bin/python -m pytest app/onboarding/tests/test_onboarding_views.py -q`
Expected: 3 FAILURES in `test_continue_advances_and_marks_complete`, `test_back_goes_to_previous_step`, `test_can_revisit_completed_step_without_trapping` (they POST bare `continue` to github-repo, which now needs valid form data). Task 4 fixes them. Everything else passes.

- [ ] **Step 4: Commit**

```bash
git add app/onboarding/views.py
git commit -m "feat(APP-09): bind+validate+persist per-step forms in onboarding_step"
```

---

### Task 3: Render the form in the step template

**Files:**
- Modify: `app/onboarding/templates/onboarding/step.html`

- [ ] **Step 1: Replace the template body**

```html
{% extends "onboarding/base_wizard.html" %}

{% block step_content %}
  {% if form %}
    {{ form.as_p }}
  {% else %}
    <p class="wizard-placeholder">
      This screen's content lands in APP-09 through APP-16.
    </p>
  {% endif %}
{% endblock %}
```

- [ ] **Step 2: Commit**

```bash
git add app/onboarding/templates/onboarding/step.html
git commit -m "feat(APP-09): render registered step form in step.html"
```

---

### Task 4: Update existing tests + add APP-09 view tests

**Files:**
- Modify: `app/onboarding/tests/test_onboarding_views.py`

- [ ] **Step 1: Add a valid-payload helper near the top of the test module**

After the existing fixtures, add:

```python
# A valid github-repo form payload, for tests that POST `continue` past step 1.
GITHUB_REPO_CONTINUE = {
    "action": "continue",
    "mode": "connect",
    "repo_url": "https://github.com/acme/policies",
    "branch": "main",
}
```

- [ ] **Step 2: Update the three existing tests that POST bare continue to github-repo**

In `test_continue_advances_and_marks_complete`, change:
```python
    resp = client.post("/onboarding/github-repo/", {"action": "continue"})
```
to:
```python
    resp = client.post("/onboarding/github-repo/", GITHUB_REPO_CONTINUE)
```

In `test_back_goes_to_previous_step`, change the first line's POST:
```python
    client.post("/onboarding/github-repo/", {"action": "continue"})
```
to:
```python
    client.post("/onboarding/github-repo/", GITHUB_REPO_CONTINUE)
```

In `test_can_revisit_completed_step_without_trapping`, change:
```python
    client.post("/onboarding/github-repo/", {"action": "continue"})
```
to:
```python
    client.post("/onboarding/github-repo/", GITHUB_REPO_CONTINUE)
```

- [ ] **Step 3: Run the view tests to confirm they pass again**

Run: `/Users/chuck/PolicyWonk/ai/venv/bin/python -m pytest app/onboarding/tests/test_onboarding_views.py -q`
Expected: PASS (all existing tests green again).

- [ ] **Step 4: Add new APP-09 view tests**

Append to `app/onboarding/tests/test_onboarding_views.py`:

```python
def test_github_repo_get_renders_form(client, user):
    client.force_login(user)
    resp = client.get("/onboarding/github-repo/")
    assert resp.status_code == 200
    body = resp.content.decode()
    # Mode radio + the connect URL field render.
    assert 'name="mode"' in body
    assert 'name="repo_url"' in body


def test_github_repo_invalid_continue_does_not_advance(client, user):
    client.force_login(user)
    # Missing repo_url for connect mode -> invalid.
    resp = client.post("/onboarding/github-repo/", {"action": "continue", "mode": "connect", "branch": "main"})
    assert resp.status_code == 200  # re-rendered, not redirected
    # Still on github-repo (not advanced); the step is not marked complete.
    assert client.get("/onboarding/").url == "/onboarding/github-repo/"


def test_github_repo_valid_continue_persists_and_advances(client, user):
    client.force_login(user)
    resp = client.post("/onboarding/github-repo/", GITHUB_REPO_CONTINUE)
    assert resp.status_code == 302
    assert resp.url == "/onboarding/address-scheme/"
    # The captured value is persisted and pre-populates a return visit.
    back = client.get("/onboarding/github-repo/")
    assert "https://github.com/acme/policies" in back.content.decode()


def test_no_form_step_still_advances_on_bare_continue(client, user):
    """Regression: a step with no registered form keeps the no-op continue."""
    client.force_login(user)
    # Advance past the form step first.
    client.post("/onboarding/github-repo/", GITHUB_REPO_CONTINUE)
    # address-scheme has no form; a bare continue advances.
    resp = client.post("/onboarding/address-scheme/", {"action": "continue"})
    assert resp.status_code == 302
    assert resp.url == "/onboarding/versioning/"
```

- [ ] **Step 5: Run the view tests**

Run: `/Users/chuck/PolicyWonk/ai/venv/bin/python -m pytest app/onboarding/tests/test_onboarding_views.py -v`
Expected: PASS (existing + 4 new).

- [ ] **Step 6: Commit**

```bash
git add app/onboarding/tests/test_onboarding_views.py
git commit -m "test(APP-09): github-repo form view tests + update bare-continue tests"
```

---

### Task 5: Full-suite verification

- [ ] **Step 1: Run the whole suite**

Run: `/Users/chuck/PolicyWonk/ai/venv/bin/python -m pytest -q`
Expected: `371 passed` (360 baseline + 7 form tests + 4 new view tests; the 3 updated view tests are modified, not added).

---

## Self-Review checklist (run before requesting review)

- Spec coverage: form (Task 1), registry (Task 1), generic-view binding/validation/persist (Task 2), template (Task 3), existing-test updates + new tests (Task 4). ✔
- Capture-only: no `GitHubProvider.clone`/create anywhere in the diff. ✔
- Per-screen pattern is reusable (registry + generic view), not special-cased. ✔
- `back`/`save_exit` still navigate without validation. ✔
- No placeholders; every step has runnable code/commands. ✔
- Names consistent: `GitHubRepoForm`, `form_class_for`, `_step_context`, payload `GITHUB_REPO_CONTINUE`. ✔

## Dispatch note

Implementer runs in `isolation: "worktree"`, Sonnet. First action: `git merge main` into the auto-branch (baseline 360). Critical Operational Note: never `cd /Users/chuck/PolicyWonk` for git ops. Run pytest via `/Users/chuck/PolicyWonk/ai/venv/bin/python` from the worktree root. Two-stage review (spec then quality) before merge.
