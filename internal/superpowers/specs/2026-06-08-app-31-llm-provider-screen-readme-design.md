# APP-31 — Minimal LLM-provider wizard screen + README API-key clarity

Date: 2026-06-08
Ticket: APP-31 (S, Week 5 polish). Depends on APP-08 (wizard skeleton), APP-09 (per-screen form pattern). Companion to AI-16 (audit-sidecar usage capture, already resolved).

## Problem

Diocesan IT directors arrive at DISC having used claude.ai through a Pro / Pro Max / Teams subscription and assume that subscription works with PolicyCodex. It does not: the consumer chat products have no programmatic access. PolicyCodex needs Anthropic API access (a separate product, separate pricing, separate signup). The same distinction holds for OpenAI (not ChatGPT Plus), Gemini (not Google One), and Azure OpenAI. This confusion must be headed off in two places: the wizard at the moment of provider choice, and the README before install.

## Scope finding that shaped this design

APP-31 was filed as "update the wizard's LLM provider screen (APP-14 surface) prose." But **APP-14 is not built**. The `llm-provider` step (`app/onboarding/wizard.py:24`) has no registered form and renders the bare placeholder `step.html:7`. Only screen 1 (`github-repo`) and screen 7 (`retention-policy`) carry real content; screens 2–6 are placeholders.

Decision (Chuck, 2026-06-08): **Approach A** — build a minimal step-6 surface inside APP-31 rather than building full APP-14 first or shipping README-only. The screen captures the provider choice (the per-diocese config value APP-16 will commit) but defers the security-sensitive API-key field. This absorbs a slice of APP-14's scope deliberately; the remainder of APP-14 (key capture/validation, test-connection) stays open and is partly v0.2 P2.11.

## In scope

1. A persisting provider picker on wizard step 6.
2. Per-provider API-key-vs-subscription prose and a documentation link.
3. An illustrative cost table (explicitly labeled placeholder/TBD).
4. A "Before you begin" subsection in the public `README.md` install section.

## Out of scope (deferred)

- API-key capture, storage, or validation (security-sensitive; future APP-14 proper).
- "Test connection" one-token round-trip (v0.2 P2.11).
- Spend-ceiling collection (v0.2 P2.11).
- Real per-provider cost computation (the table is illustrative only).

## Design

### 1. Form — `LLMProviderForm`

Add to `app/onboarding/forms.py` and register in `_FORMS` under `"llm-provider"`, mirroring `GitHubRepoForm`.

- One `provider` `ChoiceField` rendered as `forms.RadioSelect`.
- Choices and labels:
  - `claude` → "Anthropic Claude (default)"
  - `openai` → "OpenAI"
  - `gemini` → "Google Gemini"
  - `azure-openai` → "Azure OpenAI"
  - `local-llama` → "Local Llama (self-hosted, no API key)"
- `initial="claude"`.
- No API-key field. Validation is only "a valid choice was made" (Django `ChoiceField` default). No custom `clean()` needed.
- Persistence is automatic via the existing generic view path: on `continue`, `onboarding_step` binds the registered form, validates, and calls `state.set_data(step, form.cleaned_data)` (`views.py:71`). **No view changes required** — registry wiring is the whole mechanism.

### 2. Template — dedicated partial

`step.html` renders `{{ form.as_p }}` for any registered form, which cannot carry the per-provider prose, links, and cost table. Add a dedicated partial `app/onboarding/templates/onboarding/_llm_provider_body.html`, included from `step.html` when `step.slug == "llm-provider"` (mirrors the screen-7 precedent of `_screen7_body.html`). The partial renders the radio choices itself (so prose can sit beside each option) and the cost table below.

Per-provider prose (the API-key-vs-consumer-subscription distinction):

- **Anthropic Claude** — needs an Anthropic **API key** (not Claude Pro / Pro Max / Teams). API is pre-paid, pay-per-token via console.anthropic.com.
- **OpenAI** — needs an OpenAI **API key** (not ChatGPT Plus). Pay-per-token at platform.openai.com.
- **Gemini** — needs a Gemini **API key** or Vertex AI credentials (not Google One).
- **Azure OpenAI** — needs Azure OpenAI **deployment credentials** (an Azure subscription with the OpenAI service deployed).
- **Local Llama** — no third-party key; runs on the diocese's own VM. Zero per-call cost, quality varies by model size.

Documentation links (confirmed by Chuck 2026-06-08):

- Anthropic — `https://docs.anthropic.com/en/api/overview`
- OpenAI — `https://platform.openai.com/docs/api-reference/authentication`
- Gemini — `https://ai.google.dev/gemini-api/docs/api-key`
- Azure OpenAI — `https://learn.microsoft.com/azure/ai-services/openai/`
- Local Llama — no link (no key required)

### 3. Cost table + caveat (in the same partial)

| Diocese size | One-time inventory | Steady-state monthly |
|---|---|---|
| Small (~50 policies) | $1–5 | $2–15 |
| Mid (~200 policies) | $5–20 | $5–50 |
| Large (~500+ policies) | $15–50 | $15–100 |

Caveat rendered above and/or below the table:

> Illustrative example only. These figures are a placeholder and will be refined later. Rough estimates assuming a mid-tier model; validate against your actual usage after first ingest.

The numbers are extrapolated linearly from the single anchor in `internal/PolicyCodex-v0.2-Brainstorm.md` section 5 (~200 policies = $5–20 one-time, $5–50/month). Not provider- or tier-accurate by design.

### 4. README — "Before you begin"

Add `### Before you begin` at the top of the install section (before the numbered steps near `README.md:111`). Content:

- PolicyCodex needs **API access, not a consumer chat subscription.**
- One line per provider naming the distinction (Anthropic API key not Claude Pro/Max/Teams; OpenAI API key not ChatGPT Plus; Gemini API key/Vertex not Google One; Azure OpenAI deployment credentials).
- Note that the Anthropic API is pre-paid pay-per-token via console.anthropic.com, so IT directors arrive at wizard step 6 already provisioned.
- No cost table in the README (it lives in the wizard); a one-line pointer suffices.

## Testing

- `app/onboarding/tests/test_onboarding_forms.py`:
  - `LLMProviderForm` is valid for each of the five provider values.
  - Invalid/empty `provider` is rejected.
  - Registry `form_class_for("llm-provider")` returns `LLMProviderForm`.
  - Valid `cleaned_data` carries `provider`.
- `app/onboarding/tests/test_onboarding_views.py`:
  - GET step 6 renders the picker, a prose sentinel (e.g. `not Claude Pro`), and a cost-table sentinel (e.g. `Illustrative example`).
  - `continue` on step 6 persists the choice to `WizardState` and advances to step 7 (`retention-policy`).
- README is prose; covered by the existing generic-ship leak scan (`tests/test_static_assets_ship.py` / generic-ship audit). No new test.

## Ship-generic compliance

All five providers and copy are diocese-agnostic. No PT-specific values. "The diocese" phrasing throughout. The cost table is generic and explicitly illustrative.

## Files touched

- `app/onboarding/forms.py` (add form + registry entry)
- `app/onboarding/templates/onboarding/_llm_provider_body.html` (new partial)
- `app/onboarding/templates/onboarding/step.html` (include partial on slug match)
- `README.md` (Before you begin subsection)
- `app/onboarding/tests/test_onboarding_forms.py`, `app/onboarding/tests/test_onboarding_views.py` (tests)

No new dependencies. No migrations (WizardState is session-backed).
