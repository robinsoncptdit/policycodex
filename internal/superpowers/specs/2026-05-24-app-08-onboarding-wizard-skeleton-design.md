# APP-08: Onboarding Wizard Skeleton Design

**Status:** approved 2026-05-24. Ready for writing-plans.

**Ticket:** APP-08 (Onboarding wizard skeleton, seven-screen flow). M, depends on APP-01. Sets the routing/state/navigation conventions for APP-09 through APP-16.

## Goal

Ship the frame of the seven-screen onboarding wizard: routes, session-backed state, step navigation, and save-and-resume. Per-screen content (forms, provider calls, AI extraction) is APP-09 through APP-16. This ticket delivers placeholder steps wired into a working navigation shell.

## Decisions (resolved 2026-05-24 with Chuck)

1. **Custom session-based multi-step**, not django-formtools. No new dependency (sessions already enabled). The wizard's later steps are side-effectful (APP-09 creates/connects a GitHub repo, APP-12 writes branch protection, APP-15 uploads a PDF then runs AI extraction then a typed-table review), which fit explicit per-step views better than formtools' "collect forms, then done()" model.
2. **Session-backed state**, not a DB model. State lives in `request.session`. Resume works while the admin's session persists (Django default about two weeks, configurable). Sufficient for a one-time, single-admin onboarding on a single server. Known limitation: progress is lost on session expiry, cookie clear, or device switch. Revisit with a DB model only if real installs need cross-device or post-expiry durability.
3. **New app `app/onboarding/`**, sibling to `app/working_copy/`. Mounted at `onboarding/`.

## App Layout

```
app/onboarding/
  __init__.py
  apps.py        OnboardingAppConfig (name = "app.onboarding")
  wizard.py      Step dataclass + STEPS registry + navigation helpers
  state.py       WizardState (wraps request.session)
  views.py       onboarding_root, onboarding_step
  urls.py        "" -> onboarding_root, "<slug:step>/" -> onboarding_step
  templates/onboarding/
    base_wizard.html
    step.html
  tests/
    __init__.py
    test_wizard.py        (registry + nav helpers)
    test_wizard_state.py  (state container)
    test_onboarding_views.py
```

Integration:
- Add `'app.onboarding.apps.OnboardingAppConfig'` to `INSTALLED_APPS` in `policycodex_site/settings.py` (after `app.working_copy`).
- Add `path("onboarding/", include("app.onboarding.urls"))` to `policycodex_site/urls.py`.

## Components

### Step registry (`wizard.py`)

The single source of truth for step identity and order. Views and templates read it; APP-09 through APP-16 add real content keyed by slug without touching navigation.

```python
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
```

Helpers (all pure, slug-based; raise/`None` consistently for unknown slugs):
- `first_step() -> Step`
- `get_step(slug) -> Step | None`
- `index_of(slug) -> int | None`
- `next_step(slug) -> Step | None` (None when slug is the last step)
- `prev_step(slug) -> Step | None` (None when slug is the first step)
- `is_last(slug) -> bool`

The seven slugs map to APP-09 (github-repo), APP-10 (address-scheme), APP-11 (versioning), APP-12 (reviewer-roles), APP-13 (retention), APP-14 (llm-provider), APP-15 (retention-policy).

### State (`state.py`)

`WizardState` wraps a single session key:

```python
SESSION_KEY = "onboarding"
# request.session["onboarding"] = {
#   "current_step": "<slug>",         # resume point
#   "completed": ["<slug>", ...],     # steps the user finished at least once
#   "data": {"<slug>": {...}, ...},   # per-step saved form data (APP-09..16 fill)
# }
```

API:
- `__init__(session)` - binds to a Django session; lazily initializes the key.
- `current_step -> str` - defaults to `first_step().slug` when unset.
- `set_current(slug)`
- `get_data(slug) -> dict` - `{}` when absent.
- `set_data(slug, data: dict)`
- `mark_complete(slug)` - appends to `completed` (idempotent, dedup).
- `is_complete(slug) -> bool`
- `furthest_step() -> str` - the highest-index slug among `current_step` and `completed`; drives ahead-jump gating.
- `all_data() -> dict` - the full `data` map (APP-16 reads this to commit config).
- `reset()` - clears the key.

Implementation note: mutating a nested dict inside `request.session` does NOT auto-flag the session as modified. Every mutating method must set `session.modified = True` (or re-assign `session[SESSION_KEY]`). Tests must assert persistence across a fresh `WizardState` over the same session.

### Views (`views.py`)

Both `@login_required` (onboarding is admin-only; matches `LOGIN_URL = "/login/"`).

- `onboarding_root(request)`: redirect to `onboarding_step` for `WizardState(request.session).current_step`. This is save-and-resume: a returning admin lands on their resume point (first step when fresh).

- `onboarding_step(request, step)`:
  - Unknown `step` slug -> `Http404`.
  - **GET gating:** if `index_of(step) > index_of(furthest_step())`, redirect to the furthest step (no skipping ahead). Visiting the current step or any earlier/completed step is allowed (review and edit). On a valid GET, set `current` to `step` and render `step.html` with nav context: `step`, `index` (1-based), `total`, `prev_step`, `next_step`, `is_last`, `is_complete`.
  - **POST actions** (read `request.POST.get("action")`):
    - `continue`: (skeleton) mark the step complete, then if `is_last(step)` redirect to completion, else redirect to `next_step`. Per-step form validation/processing is a no-op placeholder here; APP-09..16 add it before the mark-complete/advance.
    - `back`: redirect to `prev_step` (no-op redirect to self when already first).
    - `save_exit`: persist (state already saved) and redirect to `catalog` with a flash message ("Your progress is saved. Resume onboarding any time.").
    - Unknown/missing action: re-render the step (defensive).
  - **Completion:** on `continue` at the last step, `mark_complete` it and redirect to `catalog` with a flash message ("Onboarding steps complete."). The real config commit and the `POLICYCODEX_ONBOARDING_COMPLETE` flip are APP-15/APP-16; leave a clearly-commented hook at this point, do not flip the setting here.

### Templates

- `base_wizard.html` extends core `base.html`. Renders a "Step {{ index }} of {{ total }}: {{ step.title }}" indicator and a POST `<form>` containing a `{% block step_content %}` plus three submit buttons: Back (`name="action" value="back"`, omitted/disabled on the first step), Continue (`value="continue"`), and Save and exit (`value="save_exit"`). CSRF token included.
- `step.html` extends `base_wizard.html` and fills `step_content` with a placeholder line ("This screen's content lands in APP-09 through APP-16."). Per-screen tickets either fill `step_content` here by slug or add their own templates; the skeleton ships the one generic placeholder.

## Navigation Semantics (summary)

- **Resume:** `/onboarding/` -> current (furthest incomplete) step.
- **Forward gating:** cannot GET a step beyond the furthest reached; redirect back to it.
- **Backward review:** can revisit any completed/earlier step.
- **Save and exit:** session persists; returning to `/onboarding/` resumes.
- **Completion:** last-step Continue marks done and returns to the catalog (config commit deferred to APP-15/16).

## Out of Scope (skeleton only)

- Real per-screen forms, provider calls, and AI extraction (APP-09 through APP-16).
- The configuration commit to the policy repo and the `POLICYCODEX_ONBOARDING_COMPLETE` flip (APP-15/APP-16). A commented hook marks where they attach.
- DB-backed persistence (chose session per Decision 2).
- Any redirect that forces a user into the wizard when onboarding is incomplete, or blocks the wizard when complete. v0.1 leaves the wizard reachable; gating-by-completion is a later concern.

## Testing

`app/onboarding/tests/`, using pytest-django's `client` fixture and the `user` + `force_login` pattern from `core/tests/test_auth.py`.

- `test_wizard.py`: registry length/order; `first_step`, `get_step`, `index_of`, `next_step`/`prev_step` boundaries (None at ends), `is_last`; unknown slug handling.
- `test_wizard_state.py`: default `current_step` is first slug; `set_data`/`get_data` round-trip; `mark_complete` idempotent + `is_complete`; `furthest_step` reflects the highest reached index; persistence across a fresh `WizardState` over the same session (proves `session.modified` is set); `reset`.
- `test_onboarding_views.py`: URL names resolve (`onboarding`, `onboarding_step`); `@login_required` redirects anonymous to `/login/`; root redirects to first step when fresh; root resumes at current step after advancing; GET renders the step title and "Step N of 7" indicator; POST `continue` marks complete and advances; POST `back` goes to prev (no-op on first); POST `save_exit` redirects to `/catalog/` and state persists; ahead-jump GET redirects to the furthest step; unknown slug returns 404; last-step `continue` marks done and redirects to `/catalog/`.

## Self-Review

- **Placeholders:** none. Per-screen content is explicitly deferred and named (APP-09..16); that is scope, not a placeholder.
- **Consistency:** the seven slugs are identical in the registry, the APP-09..15 mapping, and the test list. `furthest_step` is defined once (highest index among current + completed) and used consistently for gating. The session shape in `state.py` matches the methods that read/write it.
- **Scope:** one app, one implementation plan. No decomposition needed.
- **Ambiguity:** "save and resume" is pinned to session-backed (Decision 2) with the durability limitation stated. "Completion" is pinned to "mark done + redirect to catalog, no setting flip" with the APP-15/16 hook called out, so it cannot be read as "do the config commit here."
