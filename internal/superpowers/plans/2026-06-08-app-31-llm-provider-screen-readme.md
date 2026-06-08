# APP-31 — Minimal LLM-provider wizard screen + README API-key clarity — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a minimal step-6 provider picker that persists the diocese's LLM-provider choice and explains that PolicyCodex needs an API key (not a consumer chat subscription), and add a matching "Before you begin" note to the README.

**Architecture:** Mirror the existing onboarding form-registry pattern: a single-field `LLMProviderForm` registered under the `llm-provider` slug persists the choice through the generic `onboarding_step` view (no view changes). A dedicated template partial carries the per-provider API-key prose, documentation links, and an illustrative cost table that `form.as_p` cannot express. The README gains a "Before you begin" subsection that heads off the consumer-subscription confusion before install.

**Tech Stack:** Django 6 forms + templates, pytest-django, DaisyUI/Tailwind template vocabulary, HTMX-free (plain form POST through the existing wizard shell).

**Spec:** `internal/superpowers/specs/2026-06-08-app-31-llm-provider-screen-readme-design.md`

**Test interpreter:** Run pytest as the controller with `ai/venv/bin/python -m pytest` (no root venv exists; system python lacks pytest).

---

## File Structure

- `app/onboarding/forms.py` (modify) — add `LLMProviderForm`; register it in `_FORMS`.
- `app/onboarding/templates/onboarding/_llm_provider_body.html` (create) — per-provider radio + prose + links + cost table. Mirrors the `_screen7_body.html` dedicated-partial precedent.
- `app/onboarding/templates/onboarding/step.html` (modify) — include the partial when `step.slug == "llm-provider"`, taking precedence over the generic `{{ form.as_p }}` branch.
- `app/onboarding/tests/test_onboarding_forms.py` (modify) — `LLMProviderForm` validation + registry tests.
- `app/onboarding/tests/test_onboarding_views.py` (modify) — refactor the advance helper; add step-6 GET/continue/persist/prose/cost tests.
- `README.md` (modify) — add `### Before you begin`; enrich the step-6 wizard line.

No new dependencies. No migrations (WizardState is session-backed). The view layer (`app/onboarding/views.py`) is **not** modified — registry wiring is the whole persistence mechanism.

---

### Task 1: `LLMProviderForm` (form class only, not yet registered)

Adding the class without registering it keeps the suite green: nothing references it as a wizard form yet, so the existing `_advance_to_retention_policy` helper (which posts a bare `continue` to `llm-provider`) still advances.

**Files:**
- Modify: `app/onboarding/forms.py`
- Test: `app/onboarding/tests/test_onboarding_forms.py`

- [ ] **Step 1: Write the failing form tests**

Add to the top imports of `app/onboarding/tests/test_onboarding_forms.py` (the existing import line is `from app.onboarding.forms import GitHubRepoForm, RetentionPolicyUploadForm, form_class_for`). Replace it with:

```python
import pytest

from app.onboarding.forms import (
    GitHubRepoForm,
    LLMProviderForm,
    RetentionPolicyUploadForm,
    form_class_for,
)
```

Append these tests to the end of the file:

```python
@pytest.mark.parametrize(
    "value", ["claude", "openai", "gemini", "azure-openai", "local-llama"]
)
def test_llm_provider_accepts_each_choice(value):
    form = LLMProviderForm(data={"provider": value})
    assert form.is_valid(), form.errors
    assert form.cleaned_data["provider"] == value


def test_llm_provider_rejects_unknown_choice():
    form = LLMProviderForm(data={"provider": "deepseek"})
    assert not form.is_valid()
    assert "provider" in form.errors


def test_llm_provider_requires_a_choice():
    form = LLMProviderForm(data={})
    assert not form.is_valid()
    assert "provider" in form.errors


def test_llm_provider_defaults_to_claude():
    form = LLMProviderForm()
    assert form.fields["provider"].initial == "claude"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `ai/venv/bin/python -m pytest app/onboarding/tests/test_onboarding_forms.py -k llm_provider -v`
Expected: collection error / FAIL — `ImportError: cannot import name 'LLMProviderForm'`.

- [ ] **Step 3: Implement `LLMProviderForm`**

In `app/onboarding/forms.py`, add the class after `GitHubRepoForm` (before `RetentionPolicyUploadForm`):

```python
class LLMProviderForm(forms.Form):
    PROVIDER_CHOICES = [
        ("claude", "Anthropic Claude (default)"),
        ("openai", "OpenAI"),
        ("gemini", "Google Gemini"),
        ("azure-openai", "Azure OpenAI"),
        ("local-llama", "Local Llama (self-hosted, no API key)"),
    ]

    provider = forms.ChoiceField(
        choices=PROVIDER_CHOICES,
        widget=forms.RadioSelect,
        initial="claude",
        label="LLM provider",
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `ai/venv/bin/python -m pytest app/onboarding/tests/test_onboarding_forms.py -k llm_provider -v`
Expected: PASS (the parametrized choice test runs 5 times; all green).

- [ ] **Step 5: Commit**

```bash
git add app/onboarding/forms.py app/onboarding/tests/test_onboarding_forms.py
git commit -m "$(cat <<'EOF'
feat(app-31): add LLMProviderForm provider picker (unwired)

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Register the form, fix the advance helper, basic view behavior

Registering the form makes `llm-provider` a required-field step. The existing `_advance_to_retention_policy` helper posts a bare `continue` there, which would now be rejected and break every screen-7 test. Registration and the helper fix MUST land in the same commit to keep the suite green. The dedicated partial (prose/cost) comes in Task 3; here `step.html` still renders `form.as_p`, which is enough to satisfy the basic picker tests.

**Files:**
- Modify: `app/onboarding/forms.py` (registry only)
- Modify: `app/onboarding/tests/test_onboarding_views.py`
- Test: `app/onboarding/tests/test_onboarding_views.py`

- [ ] **Step 1: Refactor the advance helper to pass a provider**

In `app/onboarding/tests/test_onboarding_views.py`, find the existing helper:

```python
# Steps 1-6 payloads to reach screen 7. Only github-repo has a real form.
def _advance_to_retention_policy(client):
    client.post("/onboarding/github-repo/", GITHUB_REPO_CONTINUE)
    for slug in ["address-scheme", "versioning", "reviewer-roles", "retention", "llm-provider"]:
        client.post(f"/onboarding/{slug}/", {"action": "continue"})
```

Replace it with a stop-at-step-6 helper plus a thin wrapper that supplies the now-required provider:

```python
# Steps 1-5 payloads to land ON llm-provider (step 6). Only github-repo has a
# real form before step 6.
def _advance_to_llm_provider(client):
    client.post("/onboarding/github-repo/", GITHUB_REPO_CONTINUE)
    for slug in ["address-scheme", "versioning", "reviewer-roles", "retention"]:
        client.post(f"/onboarding/{slug}/", {"action": "continue"})


# Steps 1-6 payloads to reach screen 7. llm-provider now requires a provider.
def _advance_to_retention_policy(client):
    _advance_to_llm_provider(client)
    client.post("/onboarding/llm-provider/", {"action": "continue", "provider": "claude"})
```

- [ ] **Step 2: Write the failing step-6 view tests**

Append to `app/onboarding/tests/test_onboarding_views.py`:

```python
def test_llm_provider_get_renders_picker(client, user):
    client.force_login(user)
    _advance_to_llm_provider(client)
    resp = client.get("/onboarding/llm-provider/")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "Step 6 of 7" in body
    assert 'name="provider"' in body


def test_llm_provider_valid_continue_persists_and_advances(client, user):
    client.force_login(user)
    _advance_to_llm_provider(client)
    resp = client.post(
        "/onboarding/llm-provider/", {"action": "continue", "provider": "openai"}
    )
    assert resp.status_code == 302
    assert resp.url == "/onboarding/retention-policy/"
    # The choice persists: a return visit restores the selection (one radio checked).
    back = client.get("/onboarding/llm-provider/")
    back_body = back.content.decode()
    assert 'value="openai"' in back_body
    assert "checked" in back_body


def test_llm_provider_invalid_continue_does_not_advance(client, user):
    client.force_login(user)
    _advance_to_llm_provider(client)
    resp = client.post("/onboarding/llm-provider/", {"action": "continue"})
    assert resp.status_code == 200  # re-rendered, not redirected
    assert client.get("/onboarding/").url == "/onboarding/llm-provider/"
```

- [ ] **Step 3: Run the new tests to verify they fail**

Run: `ai/venv/bin/python -m pytest app/onboarding/tests/test_onboarding_views.py -k llm_provider -v`
Expected: FAIL — `test_llm_provider_get_renders_picker` and the persist test fail because `name="provider"` is absent (no form registered; the step renders the placeholder text). `test_llm_provider_invalid_continue_does_not_advance` also fails: with no form, a bare continue advances (302) instead of staying (200).

- [ ] **Step 4: Register the form**

In `app/onboarding/forms.py`, change the registry from:

```python
_FORMS = {
    "github-repo": GitHubRepoForm,
}
```

to:

```python
_FORMS = {
    "github-repo": GitHubRepoForm,
    "llm-provider": LLMProviderForm,
}
```

- [ ] **Step 5: Add the registry assertion**

In `app/onboarding/tests/test_onboarding_forms.py`, the existing `test_registry_maps_github_repo` asserts `form_class_for("address-scheme") is None`. `address-scheme` is still formless, so that line stays valid. Add a dedicated registry test next to it:

```python
def test_registry_maps_llm_provider():
    assert form_class_for("llm-provider") is LLMProviderForm
```

- [ ] **Step 6: Run the affected suites to verify green**

Run: `ai/venv/bin/python -m pytest app/onboarding/tests/test_onboarding_views.py app/onboarding/tests/test_onboarding_forms.py -v`
Expected: PASS — the new step-6 tests pass (radio renders via `form.as_p`; invalid continue stays on step 6), the registry test passes, and the screen-7 tests still pass because `_advance_to_retention_policy` now supplies the provider.

- [ ] **Step 7: Commit**

```bash
git add app/onboarding/forms.py app/onboarding/tests/test_onboarding_views.py app/onboarding/tests/test_onboarding_forms.py
git commit -m "$(cat <<'EOF'
feat(app-31): register LLMProviderForm on wizard step 6

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Dedicated partial — per-provider prose, doc links, cost table

`form.as_p` renders only the bare radio group. Add a dedicated partial (mirroring `_screen7_body.html`) that renders the radios itself so the API-key-vs-subscription prose and a doc link can sit beside each option, with the illustrative cost table below.

**Files:**
- Create: `app/onboarding/templates/onboarding/_llm_provider_body.html`
- Modify: `app/onboarding/templates/onboarding/step.html`
- Test: `app/onboarding/tests/test_onboarding_views.py`

- [ ] **Step 1: Write the failing prose + cost-table view tests**

Append to `app/onboarding/tests/test_onboarding_views.py`:

```python
def test_llm_provider_screen_shows_api_key_prose(client, user):
    client.force_login(user)
    _advance_to_llm_provider(client)
    body = client.get("/onboarding/llm-provider/").content.decode()
    # The core consumer-subscription distinction is spelled out.
    assert "not Claude Pro" in body
    assert "ChatGPT Plus" in body
    # Each provider's API-key documentation link is present.
    assert "https://docs.anthropic.com/en/api/overview" in body
    assert "https://platform.openai.com/docs/api-reference/authentication" in body
    assert "https://ai.google.dev/gemini-api/docs/api-key" in body
    assert "https://learn.microsoft.com/azure/ai-services/openai/" in body


def test_llm_provider_screen_shows_cost_table_with_caveat(client, user):
    client.force_login(user)
    _advance_to_llm_provider(client)
    body = client.get("/onboarding/llm-provider/").content.decode()
    assert "Illustrative example" in body          # placeholder caveat
    assert "mid-tier model" in body                 # assumption note
    assert "Mid (~200 policies)" in body            # a table row renders
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `ai/venv/bin/python -m pytest app/onboarding/tests/test_onboarding_views.py -k "api_key_prose or cost_table" -v`
Expected: FAIL — the prose, links, and `Illustrative example` strings are absent (`step.html` still renders `form.as_p`).

- [ ] **Step 3: Create the dedicated partial**

Create `app/onboarding/templates/onboarding/_llm_provider_body.html`:

```html
<p class="text-sm text-slate-600">
  PolicyCodex calls a large language model to run the inventory pass. Pick your provider.
  Each option needs <strong>API access</strong>, which is a separate product from the
  consumer chat plans (Claude Pro / Pro Max / Teams, ChatGPT Plus, Google One). The
  consumer plans cannot be used here.
</p>

<div class="space-y-2">
  {% for radio in form.provider %}
    <label class="flex items-start gap-3 p-3 rounded-lg border border-base-300 cursor-pointer hover:bg-base-200">
      <span class="pt-0.5">{{ radio.tag }}</span>
      <span class="space-y-1">
        <span class="font-medium block">{{ radio.choice_label }}</span>
        {% if radio.data.value == "claude" %}
          <span class="block text-sm text-slate-600">Needs an Anthropic API key (not Claude Pro / Pro Max / Teams). The API is pre-paid and billed per token via console.anthropic.com.</span>
          <a class="link link-primary text-sm" href="https://docs.anthropic.com/en/api/overview" target="_blank" rel="noopener">Get an Anthropic API key &rarr;</a>
        {% elif radio.data.value == "openai" %}
          <span class="block text-sm text-slate-600">Needs an OpenAI API key (not ChatGPT Plus). Billed per token at platform.openai.com.</span>
          <a class="link link-primary text-sm" href="https://platform.openai.com/docs/api-reference/authentication" target="_blank" rel="noopener">Get an OpenAI API key &rarr;</a>
        {% elif radio.data.value == "gemini" %}
          <span class="block text-sm text-slate-600">Needs a Gemini API key or Vertex AI credentials (not Google One).</span>
          <a class="link link-primary text-sm" href="https://ai.google.dev/gemini-api/docs/api-key" target="_blank" rel="noopener">Get a Gemini API key &rarr;</a>
        {% elif radio.data.value == "azure-openai" %}
          <span class="block text-sm text-slate-600">Needs Azure OpenAI deployment credentials: an Azure subscription with the OpenAI service deployed.</span>
          <a class="link link-primary text-sm" href="https://learn.microsoft.com/azure/ai-services/openai/" target="_blank" rel="noopener">Azure OpenAI documentation &rarr;</a>
        {% elif radio.data.value == "local-llama" %}
          <span class="block text-sm text-slate-600">No third-party key. Runs on the diocese's own VM with zero per-call cost; quality varies by model size.</span>
        {% endif %}
      </span>
    </label>
  {% endfor %}
</div>

<div class="card bg-base-100 border border-base-300 overflow-hidden">
  <div class="px-4 pt-3">
    <h3 class="text-sm font-semibold uppercase tracking-wider text-slate-500">Rough monthly cost</h3>
  </div>
  <table class="table table-sm">
    <thead><tr><th>Diocese size</th><th>One-time inventory</th><th>Steady-state monthly</th></tr></thead>
    <tbody>
      <tr><td>Small (~50 policies)</td><td>$1&ndash;5</td><td>$2&ndash;15</td></tr>
      <tr><td>Mid (~200 policies)</td><td>$5&ndash;20</td><td>$5&ndash;50</td></tr>
      <tr><td>Large (~500+ policies)</td><td>$15&ndash;50</td><td>$15&ndash;100</td></tr>
    </tbody>
  </table>
</div>
<p class="text-xs text-slate-500">
  Illustrative example only. These figures are a placeholder and will be refined later.
  Rough estimates assuming a mid-tier model; validate against your actual usage after first ingest.
</p>
```

- [ ] **Step 4: Wire the partial into `step.html`**

Replace the `step_content` block in `app/onboarding/templates/onboarding/step.html`:

```html
{% block step_content %}
  {% if form %}
    {{ form.as_p }}
  {% else %}
    <p class="text-sm text-slate-500">This screen's content lands in APP-09 through APP-16.</p>
  {% endif %}
{% endblock %}
```

with a slug branch that takes precedence over the generic `form.as_p` render:

```html
{% block step_content %}
  {% if step.slug == "llm-provider" %}
    {% include "onboarding/_llm_provider_body.html" %}
  {% elif form %}
    {{ form.as_p }}
  {% else %}
    <p class="text-sm text-slate-500">This screen's content lands in APP-09 through APP-16.</p>
  {% endif %}
{% endblock %}
```

- [ ] **Step 5: Run the new tests to verify they pass**

Run: `ai/venv/bin/python -m pytest app/onboarding/tests/test_onboarding_views.py -k "api_key_prose or cost_table or llm_provider" -v`
Expected: PASS — prose, all four doc links, and the cost-table caveat render; the Task-2 picker/persist/invalid tests still pass (the partial renders `name="provider"` radios and restores the checked selection from `form` initial).

- [ ] **Step 6: Commit**

```bash
git add app/onboarding/templates/onboarding/_llm_provider_body.html app/onboarding/templates/onboarding/step.html app/onboarding/tests/test_onboarding_views.py
git commit -m "$(cat <<'EOF'
feat(app-31): LLM-provider screen prose, doc links, cost table

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: README "Before you begin"

Head off the consumer-subscription confusion before install. No cost table in the README (it lives in the wizard); a one-line pointer suffices.

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add the "Before you begin" subsection**

In `README.md`, find the `## Quick Start` heading followed by the Python-version line:

```markdown
## Quick Start

PolicyCodex runs on Python 3.12+ (the floor set by Django 6.0).
```

Insert a `### Before you begin` subsection between them so it reads:

```markdown
## Quick Start

### Before you begin

PolicyCodex needs **API access to a language model, not a consumer chat subscription.** The consumer plans (Claude Pro / Pro Max / Teams, ChatGPT Plus, Google One) have no programmatic access and will not work. Provision an API key before you reach wizard step 6:

- **Anthropic Claude** (default) — an Anthropic API key, not Claude Pro / Pro Max / Teams. The API is pre-paid and billed per token via console.anthropic.com, so you arrive at the wizard already provisioned.
- **OpenAI** — an OpenAI API key, not ChatGPT Plus.
- **Google Gemini** — a Gemini API key or Vertex AI credentials, not Google One.
- **Azure OpenAI** — Azure OpenAI deployment credentials (an Azure subscription with the OpenAI service deployed).
- **Local Llama** — no third-party key; runs on your own VM.

The wizard's LLM-provider screen links each provider's API-key docs and shows rough monthly cost ranges.

PolicyCodex runs on Python 3.12+ (the floor set by Django 6.0).
```

- [ ] **Step 2: Enrich the step-6 wizard line**

In the numbered wizard list, change:

```markdown
6. Pick an LLM provider (Claude default)
```

to:

```markdown
6. Pick an LLM provider (Claude default; the screen links API-key docs and shows rough cost ranges)
```

- [ ] **Step 3: Run the generic-ship leak scan**

The README is prose, covered by the existing generic-ship audit. Verify it still passes (no PT-flavored strings introduced):

Run: `ai/venv/bin/python -m pytest tests/test_static_assets_ship.py -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "$(cat <<'EOF'
docs(app-31): README 'Before you begin' API-key-not-subscription note

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Full-suite verification

**Files:** none (verification only).

- [ ] **Step 1: Run the whole suite**

Run: `ai/venv/bin/python -m pytest -q`
Expected: PASS, suite count up by the APP-31 additions (5 corpus-gated tests skip in CI/locally without `POLICYCODEX_CORPUS_DIR`). No failures, no errors.

- [ ] **Step 2: Manual confirmation note**

The DoD's 1280x720 browser visual sweep is blocked on the Claude Chrome extension being disconnected (same blocker noted for APP-28). If the extension is reconnected, GET `/onboarding/llm-provider/` after advancing the wizard and confirm: five radio options with prose, four working doc links, the cost table, and the caveat. If still blocked, report that the visual sweep could not be performed rather than claiming it passed.

- [ ] **Step 3: Update the ticket board**

Mark APP-31 resolved in `PolicyWonk-v0.1-Tickets.md` and add a Daily-Log entry per project convention (separate from the code commits).

---

## Self-Review

**1. Spec coverage:**
- Spec "In scope" 1 (persisting provider picker) → Task 1 (form) + Task 2 (registration, persistence test).
- Spec "In scope" 2 (per-provider API-key prose + doc link) → Task 3 partial + `test_llm_provider_screen_shows_api_key_prose`.
- Spec "In scope" 3 (illustrative cost table, labeled placeholder) → Task 3 partial + `test_llm_provider_screen_shows_cost_table_with_caveat`.
- Spec "In scope" 4 (README "Before you begin") → Task 4.
- Spec "Out of scope" (key capture/validation, test-connection, spend ceilings, real cost computation) → not implemented; form has no key field; table is static. Correct.
- Spec testing plan (form valid per choice, invalid rejected, registry maps, cleaned_data carries provider; view GET renders picker+prose+cost, continue persists+advances to retention-policy) → all present across Tasks 1-3.

**2. Placeholder scan:** No "TBD/TODO/handle appropriately" in plan steps. The only "placeholder" wording is the deliberate product-level cost-table caveat copy, which is spec-required, not a plan gap.

**3. Type consistency:** `LLMProviderForm` field name `provider`, choice values `claude/openai/gemini/azure-openai/local-llama`, and `initial="claude"` are identical across the form definition, the registry test, the view tests (`provider`/`openai`/`claude`), the partial (`radio.data.value == "..."`), and `_advance_to_retention_policy` (`provider: claude`). Helper names `_advance_to_llm_provider` / `_advance_to_retention_policy` used consistently.

**4. Green-at-every-commit:** Task 1 adds an unwired class (no integration impact). Task 2 registers the form AND fixes the advance helper in one commit, so screen-7 tests never see a red window. Task 3 swaps `form.as_p` for the partial without changing form behavior. Task 4 touches only the README. Verified ordering avoids a broken `_advance_to_retention_policy`.
