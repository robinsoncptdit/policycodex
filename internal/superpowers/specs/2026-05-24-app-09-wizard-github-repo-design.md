# APP-09: Wizard Screen 1 (GitHub Repository) Design

**Date:** 2026-05-24
**Ticket:** APP-09 (S) - "Wizard screen 1: GitHub repository (create new or connect existing)"
**Depends on:** APP-08 (wizard skeleton, done), APP-04 (GitHubProvider, done)
**Status:** Designed autonomously 2026-05-24 (Chuck in auto mode); two decisions flagged for review.

## Goal

Give the onboarding wizard's first step (`github-repo`) real content: a form to either connect an existing GitHub policy repo or create a new one, validated and persisted into the wizard session state. Establish the reusable per-screen pattern that APP-10..16 follow.

## Decisions (flagged for review)

**1. Per-screen pattern = a form registry, not a special-cased view.**
APP-08's `onboarding_step` view handles every step generically (no-op save then navigate). APP-09 adds a slug->Django Form registry (`app/onboarding/forms.py`). The generic view, when a step has a registered form, binds it, validates on `continue`, and persists `cleaned_data` to `WizardState`. Steps with no registered form keep the existing no-op behavior. This is the extensible pattern APP-10..16 reuse by just registering a form (and optionally fields in the template).

**2. Capture-only; defer the actual clone/create to provisioning.**
The screen captures and validates the repo choice and writes it to `WizardState`. It does NOT call `GitHubProvider.clone` or create a repo. This deviates from the sprint-plan note ("Calls into GitHubProvider.clone + setup"). Rationale: cloning or creating a repo is a destructive, non-idempotent side effect, and this screen is one the user can navigate back from, abandon, or re-run. The wizard skeleton already defers config commit and `POLICYCODEX_ONBOARDING_COMPLETE` to the final step (APP-15/16). Provisioning (clone for connect, API-create for create, then working-copy setup) belongs in that completion step, acting on the config this screen captured. APP-09 keeps the wizard side-effect-free and re-runnable.

If Chuck wants a side-effecting "Test connection" or an actual clone on this screen, that is an additive change to the provisioning timing; the capture/validate/persist core is unaffected.

## Architecture

`app/onboarding/forms.py` (new) holds `GitHubRepoForm` and a `form_class_for(slug)` lookup. `app/onboarding/views.py:onboarding_step` (modify) gains: on GET, bind the step's form (if any) to `WizardState.get_data(slug)` as initial; on POST `continue`, validate, re-render with errors if invalid (do not advance), else `WizardState.set_data(slug, cleaned_data)` before the existing mark-complete/advance. The generic `step.html` (modify) renders `{{ form.as_p }}` when a form is present, else the existing placeholder. `back`/`save_exit` keep navigating without validation.

## Components

### 1. `app/onboarding/forms.py` (new)

`GitHubRepoForm(forms.Form)`:
- `mode`: ChoiceField (`connect` | `create`), RadioSelect, default `connect`.
- `repo_url`: URLField, optional (required when `mode == connect`); must be an `https://github.com/<org>/<repo>` URL.
- `org`: CharField, optional (required when `mode == create`).
- `repo_name`: CharField, optional (required when `mode == create`).
- `branch`: CharField, default `main`.
- `clean()`: enforce per-mode required fields and the GitHub URL shape.

`form_class_for(slug)` returns the registered form class or `None`. Registry: `{"github-repo": GitHubRepoForm}`.

### 2. `app/onboarding/views.py` (modify `onboarding_step`)

- Add a `_step_context(target, state, form=None)` helper (wraps `_nav_context`, adds `form` when present).
- GET: build the step's form (initial from `state.get_data(step)`) when registered; render via `_step_context`.
- POST `continue`: if the step has a form, validate `form_cls(request.POST)`; on invalid, re-render with the bound form (errors) and DO NOT advance; on valid, `state.set_data(step, form.cleaned_data)` then proceed to the existing mark-complete + advance/finish logic. Steps with no form keep the no-op continue.
- POST `back`/`save_exit`: unchanged (no validation; navigation only).
- The defensive unknown-action fall-through also renders via `_step_context` (form included when present).

### 3. `app/onboarding/templates/onboarding/step.html` (modify)

Render `{{ form.as_p }}` inside `step_content` when `form` is in context; otherwise keep the existing placeholder paragraph. One generic template still serves all steps; APP-10..16 can add custom layouts later if needed.

## Data flow

GET github-repo -> view binds GitHubRepoForm(initial=state.get_data("github-repo")) -> template renders fields -> admin submits continue -> view validates -> on valid, state.set_data("github-repo", cleaned_data), mark complete, advance to address-scheme -> on invalid, re-render with errors, stay on github-repo.

## Error handling

- Invalid/missing per-mode fields: form errors render inline; the step does not advance; `current_step` stays put.
- No network calls, so no provider/network error paths in this ticket.
- `cleaned_data` is plain strings (ChoiceField/CharField/URLField), so it serializes cleanly into the Django session via `WizardState.set_data`.

## Testing

- `app/onboarding/tests/test_onboarding_forms.py` (new): valid connect (good URL), valid create (org + name), invalid connect (missing URL; non-github URL), invalid create (missing org/name), branch default `main`.
- `app/onboarding/tests/test_onboarding_views.py` (extend): GET github-repo renders the form (mode radio + repo_url); POST continue with invalid data re-renders with errors and does NOT advance (still `github-repo`, not marked complete); POST continue with valid connect data persists to WizardState and advances to `address-scheme`; GET github-repo after save pre-populates the saved value; a no-form step (e.g., `address-scheme`) still advances on bare continue (regression guard).
- Update existing tests that POST a bare `{"action": "continue"}` to `github-repo` (they now need valid form data): `test_continue_advances_and_marks_complete`, `test_back_goes_to_previous_step`, `test_can_revisit_completed_step_without_trapping`.

## Out of scope

- Any `GitHubProvider.clone` / repo creation / working-copy setup (deferred to APP-15/16 provisioning).
- Live GitHub reachability/auth checks (no network calls).
- Per-step custom templates / JS show-hide for the mode fields (v0.1 shows all fields; `clean()` enforces the right ones).
- The other wizard screens (APP-10..16).

## Affected files

- Create: `app/onboarding/forms.py`, `app/onboarding/tests/test_onboarding_forms.py`.
- Modify: `app/onboarding/views.py`, `app/onboarding/templates/onboarding/step.html`, `app/onboarding/tests/test_onboarding_views.py`.
