# APP-28 Design: Tailwind + DaisyUI Build Chain, Retemplate, Live HTMX, REPO-10 Harness

*Brainstormed and approved 2026-06-08. Implements ticket APP-28 (size L, Week 5). Hard dependency on APP-27 (the `/htmx/` prefix, landed). All four parts (a/b/c/d) are committed must-ship scope; implement in order a -> b -> c -> d.*

## Context

The Django admin app ships today as unstyled HTML against `core/templates/base.html`. OQ-13 (resolved 2026-06-05) chose Tailwind CSS + DaisyUI + HTMX, Inter typeface, brand color via DaisyUI CSS variables, production build via the Tailwind standalone CLI (single static binary, no Node). Rationale: `internal/PolicyWonk-UI-Framework-Decision.md`. The DISC bar Chuck named is Linear / Notion / Stripe Dashboard / modern Microsoft 365. The visual target is the locked mockup `internal/mockups/disc-demo-tailwind.html`.

This spec resolves the open design forks the ticket left and locks the implementation shape.

## Decisions locked in brainstorming (2026-06-08)

1. **Build chain**: commit the compiled `policycodex.css`; keep the toolchain (Tailwind binary + DaisyUI bundle) gitignored and downloaded on demand. Docker/install path unchanged. A drift-guard test catches stale CSS.
2. **Screen 7 HTMX scope**: full HTMX conversion (upload/extract/accept/reupload/back all become fragment swaps), not just the extract step.
3. **Row-add mechanism**: HTMX fragment endpoint (server returns a fresh `<tr>`), not a client-side DOM clone.
4. **Freeze cut-line**: all four parts are must-ship. No graceful-degradation fallback budgeted.

## (a) Build chain — committed CSS, gitignored toolchain

- `scripts/build-css.sh`: detects platform, downloads the Tailwind standalone CLI binary **and** the DaisyUI standalone bundle (`daisyui.js` + `daisyui-theme.js`) into a gitignored `.tools/` directory, then compiles `static/css/policycodex.css` from `static/css/input.css`.
- `static/css/input.css` carries: `@import "tailwindcss"`, `@plugin "../../.tools/daisyui.js"`, the `@font-face` Inter declarations, and the brand-color / slate-palette theme CSS variables.
- **Committed to the repo** (cross-platform, small): compiled `static/css/policycodex.css`, `static/js/htmx.min.js` (~14KB), `static/fonts/inter-*.woff2` (SIL OFL, offline-safe).
- **Not committed** (platform-specific, heavy): the Tailwind binary and DaisyUI bundle in `.tools/` (gitignored). `build-css.sh` fetches them on demand.
- **Docker/install path unchanged**: `collectstatic` picks up the committed `policycodex.css`; WhiteNoise serves it. Nothing new runs at install, so REPO-10's clean-VM premise survives.
- **Drift guard**: an env-gated pytest (mirrors the INGEST-06 `POLICYCODEX_CORPUS_DIR` pattern). When `POLICYCODEX_BUILD_CSS=1` is set, it runs `build-css.sh` and `git diff --exit-code static/css/policycodex.css`; otherwise it skips. Keeps the offline suite green by default; runs locally and where the binary is wired in CI.
- **Key risk, de-risked first**: prove the Tailwind-standalone + DaisyUI toolchain on a 2-template vertical slice (`base.html` + `catalog.html`), browser-verified, before fanning out. If the standalone CLI cannot load the DaisyUI plugin, fall back to plain Tailwind utilities for the ~6 component patterns actually used (`btn`, `card`, `badge`, `alert`, `navbar`, `table`). Decide at the slice, not after retemplating 12 files.

## (b) Retemplate — 12 templates

Templates (8 core + 4 onboarding):
- core: `base.html`, `catalog.html`, `policy_detail.html`, `policy_edit.html`, `policy_edit_success.html`, `foundational_edit.html`, `foundational_edit_forbidden.html`, `registration/login.html`
- onboarding: `base_wizard.html`, `step.html`, `retention_policy_upload.html`, `retention_policy_review.html`

- `base.html` becomes the shell: loads `policycodex.css` + `htmx.min.js`, DaisyUI navbar + footer (keep the AGPL **View Source** link), favicon, real per-page `<title>` via `{% block title %}`, Django messages rendered as DaisyUI `alert`s.
- All 12 retemplated to the same vocabulary (slate palette, brand color via DaisyUI CSS vars, Inter).
- DoD extras folded in:
  - empty-catalog state (restyle the existing `is_empty_onboarding` block)
  - a reusable AI-outage `alert` banner (surfaced on the screen-7 extraction-failure path)
  - a11y baseline: contrast, form labels, focus order
  - favicon + real per-page titles (`base.html` is generic today)
- All browser-verified at **1280x720** projector resolution.

## (c) Live HTMX — single top-level `/htmx/` tree

**Routing**: `core/htmx_urls.py` (namespace `htmx`) gains `path("onboarding/", include("app.onboarding.htmx_urls"))`. Onboarding fragment views stay in the onboarding app but are reachable under the single top-level `/htmx/` prefix. This honors the portability constraint (HTMX URL-segregated; no `/api/v1/` collision) without coupling core to onboarding view code. Namespacing of the included onboarding patterns is settled in the implementation plan.

**Interaction 1 — screen 7, full HTMX conversion** (`app/onboarding/retention_policy.py` + its two templates):
- upload / extract / accept / reupload / back all become fragment swaps of the wizard-step body.
- the upload form `hx-post`s (multipart) to `/htmx/onboarding/extract/` with an `hx-indicator` spinner during the seconds-long AI call.
- the extract response is one of: the review-table fragment, the APP-30 empty-PDF guard error fragment, or the AI-outage alert fragment.
- `accept` finalizes (opens the onboarding PR via the existing `finalize` service) and returns an `HX-Redirect` header to the completion screen / catalog.
- views return fragments only; business logic stays in the existing `retention_extract` and `finalize` services (thin-views constraint).

**Interaction 2 — foundational typed-table row-add** (`core/views.py` + `foundational_edit.html`):
- an "Add row" button `hx-post`s to `/htmx/foundational/<slug>/row/`.
- the view returns a single fresh `<tr>` with server-computed, name-indexed inputs (`classifications[N][...]`), appended via `hx-swap="beforeend"` on the `<tbody>`.
- first real endpoint in the `htmx` namespace.

## (d) REPO-10 harness

- Extend the clean-VM verification to assert the committed `policycodex.css` is present and served (200, correct content-type) and that a known sentinel is in the served stylesheet (the brand-color CSS var and a `.btn` rule).
- Document `build-css.sh` as the regeneration step in the install/dev notes.
- No binary enters the install path, so the harness change is an assertion, not a new build step.

## Error handling

- Screen-7 empty-PDF (scanned/image-only): the APP-30 guard stays authoritative; surfaced through the extract fragment as a scan-specific message; the AI is never called on empty text.
- Screen-7 AI provider outage: caught on the extract path, surfaced as the reusable DaisyUI AI-outage `alert` fragment; the wizard re-renders the upload state, no draft staged.
- DaisyUI plugin fails to load under the standalone CLI: fall back to plain Tailwind utilities for the handful of component patterns used (decided at the slice).

## Testing

- **Build chain**: env-gated drift-guard test (`POLICYCODEX_BUILD_CSS=1` regenerates and `git diff --exit-code`s; skips otherwise).
- **Routing**: extend `core/tests/test_htmx_urls.py` to assert the two new endpoints reverse and resolve under `/htmx/`.
- **Screen 7**: view tests for each HTMX action returning the right fragment + `HX-Redirect` on accept; preserve APP-30's "AI never called on empty PDF" spy test through the fragment path.
- **Row-add**: a view test asserting the returned `<tr>` carries correctly-indexed input names.
- **Acceptance gate** for (b) and (c): browser verification at 1280x720, per DoD.

## Sequencing

Implement **a -> b -> c -> d**, with the DaisyUI-standalone slice proven inside (a) before (b) fans out. Subagent-driven per project convention: sequential, TDD, two-stage review, controller-applies-fixes, dispatched directly on `main`.

## Out of scope

- OCR for scanned PDFs (INGEST-08, post-freeze).
- The wizard completion screen itself (APP-29; ships in the same Tailwind vocabulary so this retemplate pass does not revisit it).
- Wizard-managed handbook publishing / automatic CNAME (v0.2, PRD P2.7).
- Commercial component libraries (off the table while AGPL).
