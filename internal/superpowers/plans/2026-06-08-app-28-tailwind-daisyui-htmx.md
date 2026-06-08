# APP-28: Tailwind + DaisyUI Build Chain, Retemplate, and Live HTMX — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (chosen) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Dispatch one fresh subagent per Part (A→B→C→D), two-stage review between tasks, controller applies fixes.

**Goal:** Give PolicyCodex a real visual identity (Tailwind v4 + DaisyUI 5 + Inter, no Node) and two live HTMX demo interactions, without breaking the generic-ship Docker install.

**Architecture:** A committed source stylesheet (`assets/css/input.css`) is compiled to `static/css/policycodex.css` by a scripted-download build (`bin/build-css.sh`) that fetches the upstream Tailwind standalone binary and the daisyUI `.mjs` bundle at build time — no Node, no committed binaries. The Dockerfile runs the build before `collectstatic`. All 12 Django templates adopt a shared DaisyUI component vocabulary. Two HTMX fragment endpoints land under the existing `/htmx/` namespace (APP-27): live PDF-upload→extraction on onboarding screen 7, and client-side row-add in the foundational typed-table editor.

**Tech Stack:** Django 6.0, Tailwind CSS v4 (standalone CLI), daisyUI 5 (`.mjs` plugin bundle), HTMX (vendored), Inter (self-hosted woff2), WhiteNoise (`CompressedManifestStaticFilesStorage`), pytest-django. Test interpreter: `ai/venv/bin/python` (no root venv).

---

## Order of Execution (hard sequence)

Implement **A → B → C → D**. A proves the build chain on two templates before B fans out; C needs the `/htmx/` prefix (already laid by APP-27) and the retemplated templates from B to attach to; D locks the install premise once the build step exists.

## Design System Reference (shared by all Parts)

Apply this vocabulary consistently. These are the only DaisyUI/Tailwind classes the templates should reach for; do not invent ad-hoc utility soup.

- **Page frame:** `min-h-screen bg-base-200 text-base-content` on `<body>`; content in a centered `max-w-5xl mx-auto px-4 py-6`.
- **Top bar:** DaisyUI `navbar bg-base-100 shadow-sm`; brand as `btn btn-ghost text-xl`; sign-out as `btn btn-sm btn-ghost`.
- **Cards / sections:** `card bg-base-100 shadow-sm` with `card-body`. Each logical section (approve-PR, empty-state, tables) is one card.
- **Buttons:** primary action `btn btn-primary`; secondary `btn btn-ghost`/`btn btn-outline`; destructive (none yet) `btn btn-error`.
- **Tables (typed-table, review tables, policy list):** DaisyUI `table table-zebra` inside `overflow-x-auto`.
- **Badges:** kind/gate/foundational/gap → DaisyUI `badge` variants: gate `published`→`badge-success`, `reviewed`→`badge-warning`, `drafted`→`badge-ghost`; foundational→`badge-info`; gap→`badge-error`.
- **Messages / banners:** Django messages → DaisyUI `alert` (`alert-success`/`alert-warning`/`alert-error`/`alert-info` keyed off `{{ message.tags }}`). Gap banner → `alert alert-warning`. AI-outage banner → `alert alert-error`.
- **Forms:** inputs `input input-bordered w-full`; selects `select select-bordered`; textareas `textarea textarea-bordered`; checkboxes `checkbox`; every field has a `<label class="label">` with visible text (a11y).
- **Palette:** slate base via the daisyUI light theme; brand color via the custom `--color-primary` set in `input.css` (tune in the browser-verify step).
- **Typography:** Inter, loaded via self-hosted `@font-face` in `input.css`, applied as the default sans on `<body>`.
- **a11y baseline (verify at 1280×720):** visible focus rings (DaisyUI default), labelled inputs, logical heading order (one `<h1>` in the navbar/title, `<h2>` per page), color contrast AA on text and badges.

---

# PART A — Build chain + base.html + catalog.html vertical slice

**Dispatch one subagent for all of Part A.** This is the riskiest part; it must end with a browser-verified styled catalog before B fans out.

### Task A1: Scripted-download build script

**Files:**
- Create: `bin/build-css.sh`
- Create: `assets/css/input.css`
- Modify: `.gitignore`

- [ ] **Step 1: Write `assets/css/input.css`**

```css
@import "tailwindcss";

/* Exclude the downloaded toolchain + compiled output from Tailwind's source scan. */
@source not "../.toolchain";
@source "../../core/templates/**/*.html";
@source "../../app/onboarding/templates/**/*.html";

@plugin "./../.toolchain/daisyui.mjs" {
  themes: policycodex --default;
}

@plugin "./../.toolchain/daisyui-theme.mjs" {
  name: "policycodex";
  default: true;
  color-scheme: light;
  --color-base-100: oklch(100% 0 0);
  --color-base-200: oklch(97% 0.005 250);
  --color-base-300: oklch(92% 0.01 250);
  --color-base-content: oklch(25% 0.02 255);
  --color-primary: oklch(45% 0.15 255);
  --color-primary-content: oklch(98% 0 0);
  --radius-box: 0.5rem;
  --radius-field: 0.375rem;
}

/* Self-hosted Inter (vendored woff2 under static/fonts). */
@font-face {
  font-family: "Inter";
  font-style: normal;
  font-weight: 100 900;
  font-display: swap;
  src: url("/static/fonts/Inter-Variable.woff2") format("woff2");
}

:root { font-family: "Inter", ui-sans-serif, system-ui, sans-serif; }
```

> Note: the `@plugin` paths point into `assets/.toolchain/` where the build script drops the daisyUI bundles. Run the compiler from the repo root with `-i assets/css/input.css`. If Tailwind v4 rejects the relative `@plugin` path from the input file's location, the build script `cd`s into `assets/` before invoking the binary (see Step 2) so `./.toolchain/daisyui.mjs` resolves — adjust the `@plugin` lines to `"./.toolchain/daisyui.mjs"` if you take the `cd` route. Resolve this concretely in Step 3's browser check.

- [ ] **Step 2: Write `bin/build-css.sh`**

```bash
#!/usr/bin/env bash
# APP-28: compile Tailwind v4 + daisyUI 5 to static/css/policycodex.css with NO Node.
# Downloads the upstream Tailwind standalone binary and the daisyUI .mjs bundles
# into assets/.toolchain/ (gitignored), then compiles. Idempotent.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOOLCHAIN="${ROOT}/assets/.toolchain"
OUT_DIR="${ROOT}/static/css"
mkdir -p "${TOOLCHAIN}" "${OUT_DIR}"

# Detect platform for the Tailwind binary asset name.
case "$(uname -s)-$(uname -m)" in
  Linux-x86_64)  TW_ASSET="tailwindcss-linux-x64" ;;
  Linux-aarch64) TW_ASSET="tailwindcss-linux-arm64" ;;
  Darwin-x86_64) TW_ASSET="tailwindcss-macos-x64" ;;
  Darwin-arm64)  TW_ASSET="tailwindcss-macos-arm64" ;;
  *) echo "Unsupported platform for Tailwind standalone CLI: $(uname -s)-$(uname -m)" >&2; exit 1 ;;
esac

TW_BIN="${TOOLCHAIN}/tailwindcss"
if [ ! -x "${TW_BIN}" ]; then
  echo "Downloading Tailwind standalone CLI (${TW_ASSET})..."
  curl -sLo "${TW_BIN}" "https://github.com/tailwindlabs/tailwindcss/releases/latest/download/${TW_ASSET}"
  chmod +x "${TW_BIN}"
fi

for asset in daisyui.mjs daisyui-theme.mjs; do
  if [ ! -f "${TOOLCHAIN}/${asset}" ]; then
    echo "Downloading daisyUI bundle (${asset})..."
    curl -sLo "${TOOLCHAIN}/${asset}" "https://github.com/saadeghi/daisyui/releases/latest/download/${asset}"
  fi
done

echo "Compiling assets/css/input.css -> static/css/policycodex.css ..."
"${TW_BIN}" -i "${ROOT}/assets/css/input.css" -o "${OUT_DIR}/policycodex.css" --minify
echo "Done."
```

- [ ] **Step 3: Make it executable and run it once**

Run: `chmod +x bin/build-css.sh && ./bin/build-css.sh`
Expected: downloads the binary + two `.mjs` files into `assets/.toolchain/`, prints "Done.", and creates a non-empty `static/css/policycodex.css`. If the `@plugin` path errors, switch to the `cd assets` approach noted in Step 1 and re-run until the file compiles.

- [ ] **Step 4: Update `.gitignore`**

Append:
```
# APP-28 Tailwind toolchain + compiled output (regenerated by bin/build-css.sh)
assets/.toolchain/
static/css/policycodex.css
```

- [ ] **Step 5: Commit**

```bash
git add bin/build-css.sh assets/css/input.css .gitignore
git commit -m "feat(app-28): scripted-download Tailwind+daisyUI build (no Node)"
```

### Task A2: Wire static config + vendor HTMX, Inter, favicon

**Files:**
- Modify: `policycodex_site/settings.py:142-149`
- Create: `static/js/htmx.min.js` (vendored download)
- Create: `static/fonts/Inter-Variable.woff2` (vendored download)
- Create: `static/favicon.ico`

- [ ] **Step 1: Add `STATICFILES_DIRS` to settings**

In `policycodex_site/settings.py`, immediately below `STATIC_URL = 'static/'` (line 142), add:
```python
STATICFILES_DIRS = [BASE_DIR / 'static']
```

- [ ] **Step 2: Vendor HTMX, Inter, favicon**

Run:
```bash
mkdir -p static/js static/fonts
curl -sLo static/js/htmx.min.js https://unpkg.com/htmx.org/dist/htmx.min.js
curl -sLo static/fonts/Inter-Variable.woff2 https://github.com/rsms/inter/raw/master/docs/font-files/InterVariable.woff2
# Favicon: a small placeholder is fine for v0.1; replace with brand mark later.
curl -sLo static/favicon.ico https://raw.githubusercontent.com/twitter/twemoji/master/assets/72x72/1f4d8.png || true
```
Expected: `static/js/htmx.min.js` non-empty, `static/fonts/Inter-Variable.woff2` non-empty. If the favicon URL fails, create any 16×16/32×32 `.ico` — it only needs to exist and resolve.

- [ ] **Step 3: Verify collectstatic picks them up**

Run: `ai/venv/bin/python manage.py collectstatic --noinput`
Expected: reports copying `css/policycodex.css`, `js/htmx.min.js`, `fonts/Inter-Variable.woff2`, `favicon.ico` into `staticfiles/`. No manifest error (the compiled CSS exists from A1).

- [ ] **Step 4: Commit**

```bash
git add policycodex_site/settings.py static/js/htmx.min.js static/fonts/Inter-Variable.woff2 static/favicon.ico
git commit -m "feat(app-28): vendor HTMX + Inter + favicon, wire STATICFILES_DIRS"
```

### Task A3: Rewrite base.html (the design-system foundation)

**Files:**
- Modify: `core/templates/base.html` (full rewrite)
- Test: `core/tests/test_base_assets.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# core/tests/test_base_assets.py
import pytest
from django.contrib.auth import get_user_model


@pytest.fixture
def user(db):
    return get_user_model().objects.create_user(username="admin", password="secret")


def test_base_loads_compiled_css_and_htmx(client, user):
    client.force_login(user)
    html = client.get("/catalog/").content.decode()
    assert 'href="/static/css/policycodex.css"' in html
    assert 'src="/static/js/htmx.min.js"' in html
    assert '/static/favicon.ico' in html


def test_base_keeps_agpl_source_link(client, user):
    client.force_login(user)
    html = client.get("/catalog/").content.decode()
    assert "View Source" in html
    assert "AGPL" in html
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `ai/venv/bin/python -m pytest core/tests/test_base_assets.py -v`
Expected: FAIL (no `<link>`/`<script>` tags yet).

- [ ] **Step 3: Rewrite `core/templates/base.html`**

```html
{% load static %}
<!doctype html>
<html lang="en" data-theme="policycodex">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{% block title %}PolicyCodex{% endblock %}</title>
    <link rel="icon" href="{% static 'favicon.ico' %}" sizes="any">
    <link rel="stylesheet" href="{% static 'css/policycodex.css' %}">
    <script src="{% static 'js/htmx.min.js' %}" defer></script>
  </head>
  <body class="min-h-screen bg-base-200 text-base-content">
    <header class="navbar bg-base-100 shadow-sm">
      <div class="max-w-5xl mx-auto w-full flex items-center justify-between px-4">
        <a href="{% url 'catalog' %}" class="btn btn-ghost text-xl">PolicyCodex</a>
        {% if user.is_authenticated %}
          <nav class="flex items-center gap-3">
            <span class="text-sm opacity-70">Signed in as {{ user.username }}.</span>
            <form method="post" action="{% url 'logout' %}">
              {% csrf_token %}
              <button type="submit" class="btn btn-sm btn-ghost">Sign out</button>
            </form>
          </nav>
        {% endif %}
      </div>
    </header>

    <main class="max-w-5xl mx-auto px-4 py-6">
      {% if messages %}
        <div class="space-y-2 mb-4">
          {% for message in messages %}
            <div class="alert alert-{{ message.tags|default:'info' }}">{{ message }}</div>
          {% endfor %}
        </div>
      {% endif %}
      {% block content %}{% endblock %}
    </main>

    <footer class="max-w-5xl mx-auto px-4 py-6 text-sm opacity-70">
      PolicyCodex v0.1 &middot;
      <a class="link" href="{{ source_url }}">View Source</a> (AGPL-3.0)
    </footer>
  </body>
</html>
```

> Django message tags map to DaisyUI alert variants only when tags are `success/warning/error/info`. Django's default `error` tag is `error` and `debug`/`info`/`success`/`warning` pass through; the `|default:'info'` guards the empty-tag case. If any view uses a non-DaisyUI tag, normalize via `MESSAGE_TAGS` in settings (not required by current code).

- [ ] **Step 4: Run the test to confirm it passes**

Run: `ai/venv/bin/python -m pytest core/tests/test_base_assets.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/templates/base.html core/tests/test_base_assets.py
git commit -m "feat(app-28): retemplate base.html to DaisyUI navbar/footer + asset links"
```

### Task A4: Retemplate catalog.html + browser-verify the slice

**Files:**
- Modify: `core/templates/catalog.html` (full rewrite)
- Test: existing `core/tests/test_catalog.py` must still pass (no new test required; it asserts on data, not markup)

- [ ] **Step 1: Rewrite `core/templates/catalog.html`**

```html
{% extends "base.html" %}

{% block title %}Catalog | PolicyCodex{% endblock %}

{% block content %}
  <h2 class="text-2xl font-semibold mb-4">Policy catalog</h2>

  {% if is_empty_onboarding %}
    <div class="card bg-base-100 shadow-sm">
      <div class="card-body items-center text-center">
        <h3 class="card-title">No policies yet</h3>
        <p>Run the onboarding wizard, or sync the diocese's policy repo by running
           <code class="badge badge-ghost font-mono">python manage.py pull_working_copy</code>
           on the server.</p>
        <div class="card-actions">
          <a href="{% url 'onboarding_step' step='github-repo' %}" class="btn btn-primary">Start onboarding</a>
        </div>
      </div>
    </div>
  {% else %}
    {% if gap_count %}
      <div class="alert alert-warning mb-4">
        {{ gap_count }} polic{{ gap_count|pluralize:"y,ies" }} flagged: type not in the
        retention taxonomy. Review and re-classify.
      </div>
    {% endif %}

    <div class="card bg-base-100 shadow-sm mb-6">
      <div class="card-body">
        <h3 class="card-title text-lg">Approve a PR</h3>
        <p class="text-sm opacity-70">Enter the GitHub PR number to approve. (APP-17 will
           wire this to per-policy rows once PR tracking is persisted.)</p>
        <form method="post" action="{% url 'approve_pr' %}" class="flex items-end gap-3">
          {% csrf_token %}
          <div class="form-control">
            <label class="label" for="pr_number"><span class="label-text">PR number</span></label>
            <input type="number" name="pr_number" id="pr_number" min="1" required
                   class="input input-bordered w-32">
          </div>
          <button type="submit" class="btn btn-primary">Approve PR</button>
        </form>
      </div>
    </div>

    <div class="card bg-base-100 shadow-sm">
      <div class="card-body overflow-x-auto">
        <table class="table table-zebra">
          <thead>
            <tr><th>Policy</th><th>Kind</th><th>Gate</th><th>Flags</th><th class="text-right">Actions</th></tr>
          </thead>
          <tbody>
            {% for row in rows %}
              <tr>
                <td><a class="link link-primary" href="{% url 'policy_detail' slug=row.policy.slug %}">{{ row.policy.frontmatter.title|default:row.policy.slug }}</a></td>
                <td><span class="badge badge-ghost">{{ row.policy.kind }}</span></td>
                <td>
                  {% if row.gate == "published" %}<span class="badge badge-success">{{ row.gate|title }}</span>
                  {% elif row.gate == "reviewed" %}<span class="badge badge-warning">{{ row.gate|title }}</span>
                  {% else %}<span class="badge badge-ghost">{{ row.gate|title }}</span>{% endif %}
                </td>
                <td>
                  {% if row.policy.foundational %}<span class="badge badge-info">foundational</span>{% endif %}
                  {% if row.is_gap %}<span class="badge badge-error">no retention match</span>{% endif %}
                </td>
                <td class="text-right space-x-2">
                  {# L1 foundational gate (APP-20): foundational policies edit only via the typed table. #}
                  {% if row.policy.foundational %}
                    <a class="btn btn-sm btn-ghost" href="{% url 'foundational_edit' slug=row.policy.slug %}">Edit (typed table)</a>
                  {% else %}
                    <a class="btn btn-sm btn-ghost" href="{% url 'policy_edit' slug=row.policy.slug %}">Edit</a>
                  {% endif %}
                  {% if row.gate == "reviewed" %}
                    <form method="post" action="{% url 'publish_policy' slug=row.policy.slug %}" class="inline">
                      {% csrf_token %}
                      <button type="submit" class="btn btn-sm btn-primary">Publish</button>
                    </form>
                  {% endif %}
                </td>
              </tr>
            {% empty %}
              <tr><td colspan="5" class="text-center opacity-70">No policies in the working copy.</td></tr>
            {% endfor %}
          </tbody>
        </table>
      </div>
    </div>
  {% endif %}
{% endblock %}
```

> The duplicated `{% if messages %}` block from the old catalog.html is intentionally dropped — base.html already renders messages. Confirm the `onboarding_step` URL name + the `github-repo` first-step slug against `app/onboarding/urls.py`; if the name/slug differs, fix the empty-state CTA link (it is the only new URL reference here).

- [ ] **Step 2: Run the existing catalog tests**

Run: `ai/venv/bin/python -m pytest core/tests/test_catalog.py -v`
Expected: PASS (these assert on rendered data — titles, badges-by-text, gate words — not on old CSS classes; fix any test that pinned a removed class string by updating it to the DaisyUI equivalent).

- [ ] **Step 3: Browser-verify the slice (REQUIRED)**

Run the build + dev server, then view in the browser:
```bash
./bin/build-css.sh
ai/venv/bin/python manage.py runserver
```
Confirm at 1280×720: navbar + footer styled, Inter font applied, catalog table zebra-striped, badges colored by gate, empty-state card renders when no working copy, alert banners styled, focus rings visible on the PR input/buttons. Tune `--color-primary` in `assets/css/input.css` and re-run `./bin/build-css.sh` until the brand color reads well. **Do not proceed to Part B until this looks right in the browser** — DaisyUI classes cannot be eyeballed without the served stylesheet.

- [ ] **Step 4: Commit**

```bash
git add core/templates/catalog.html core/tests/test_catalog.py
git commit -m "feat(app-28): retemplate catalog.html to DaisyUI cards/table/badges"
```

---

# PART B — Retemplate the remaining 10 templates + polish

**Dispatch one subagent for Part B.** Build chain + base.html + catalog.html are done; this fans the design-system vocabulary across the rest. Every task ends with a browser check at 1280×720. Existing data-level tests must stay green; where a test pins an old CSS class string, update it to the DaisyUI equivalent rather than deleting the assertion.

The 10 remaining templates:
- `core/templates/policy_detail.html`
- `core/templates/policy_edit.html`
- `core/templates/foundational_edit.html`
- `core/templates/foundational_edit_forbidden.html`
- `core/templates/policy_edit_success.html`
- `core/templates/registration/login.html`
- `app/onboarding/templates/onboarding/base_wizard.html`
- `app/onboarding/templates/onboarding/step.html`
- `app/onboarding/templates/onboarding/retention_policy_upload.html`
- `app/onboarding/templates/onboarding/retention_policy_review.html`

### Task B1: login.html (fully specified)

**Files:** Modify `core/templates/registration/login.html`

- [ ] **Step 1: Rewrite**

```html
{% extends "base.html" %}
{% block title %}Sign in | PolicyCodex{% endblock %}
{% block content %}
  <div class="max-w-sm mx-auto">
    <div class="card bg-base-100 shadow-sm">
      <div class="card-body">
        <h2 class="card-title">Sign in</h2>
        {% if form.errors %}
          <div class="alert alert-error">Your username and password didn't match. Try again.</div>
        {% endif %}
        <form method="post">
          {% csrf_token %}
          <div class="form-control mb-3">
            <label class="label" for="{{ form.username.id_for_label }}"><span class="label-text">Username</span></label>
            {{ form.username }}
          </div>
          <div class="form-control mb-4">
            <label class="label" for="{{ form.password.id_for_label }}"><span class="label-text">Password</span></label>
            {{ form.password }}
          </div>
          <button type="submit" class="btn btn-primary w-full">Sign in</button>
          <input type="hidden" name="next" value="{{ next }}">
        </form>
      </div>
    </div>
  </div>
{% endblock %}
```

> Django renders `{{ form.username }}` as a bare `<input>` without DaisyUI classes. Add the classes via a widget-attrs tweak in the auth form OR a small `{% load widget_tweaks %}`-free approach: append `class="input input-bordered w-full"` by setting widget attrs where the login form is configured. If no custom auth form exists, accept the unstyled input for v0.1 OR add `form.fields['username'].widget.attrs` in a thin `AuthenticationForm` subclass wired in `core/urls.py`'s `LoginView(authentication_form=...)`. Keep the choice minimal; note it in the commit.

- [ ] **Step 2: Browser-verify** — sign-out, hit `/login/`, confirm card layout + error alert on bad creds.
- [ ] **Step 3: Commit** — `git commit -m "feat(app-28): retemplate login to DaisyUI card"`

### Task B2: policy_detail.html + policy_edit.html

**Files:** Modify both. Read each file first for exact current blocks/variables.

- [ ] **Step 1:** Wrap `policy_detail.html` body in a `card bg-base-100 shadow-sm` → `card-body`; render the frontmatter metadata as a `table table-zebra`; render `provides:` as `badge badge-info` chips; keep the escaped body in a `prose max-w-none` block; gate badge per the Design System mapping; the edit link as `btn btn-sm btn-primary` (still gated by the existing foundational branch — do not move the gate).
- [ ] **Step 2:** `policy_edit.html`: wrap the form in a card; title/summary inputs → `input input-bordered w-full` with `<label class="label">`; body → `textarea textarea-bordered w-full min-h-64`; submit → `btn btn-primary`, Cancel → `btn btn-ghost`; errors → `alert alert-error` per field or a summary alert.
- [ ] **Step 3:** Run `ai/venv/bin/python -m pytest core/tests/test_policy_detail.py core/tests/ -k "policy" -v`; update any class-pinned assertions.
- [ ] **Step 4:** Browser-verify both at 1280×720.
- [ ] **Step 5:** Commit — `git commit -m "feat(app-28): retemplate policy detail + edit to DaisyUI"`

### Task B3: foundational_edit.html + foundational_edit_forbidden.html + policy_edit_success.html

**Files:** Modify all three.

- [ ] **Step 1:** `foundational_edit.html` — wrap in a card; both `<table>`s become `table table-zebra` inside `overflow-x-auto`; form fields get `input input-bordered input-sm w-full`; delete checkbox → `checkbox checkbox-sm`; "Open PR" → `btn btn-primary`, Cancel → `btn btn-ghost`. **Preserve the formset structure exactly** (`{{ cforms.management_form }}`, `{{ rforms.management_form }}`, the `f.id`/`f.name`/`f.group`/... field cells, the `f.DELETE` cells, and the `{{ meta.summary }}` field) — Part C attaches HTMX row-add to these tables, so keep the `<tbody>` and field-cell shape stable. Give each `<tbody>` an `id` (`id="cls-rows"` and `id="ret-rows"`) for the HTMX target in Part C.
- [ ] **Step 2:** `foundational_edit_forbidden.html` → `alert alert-warning` with a `btn btn-primary` link to the typed-table editor.
- [ ] **Step 3:** `policy_edit_success.html` → success `card` with the PR link as `btn btn-primary` and a `btn btn-ghost` back-to-catalog link.
- [ ] **Step 4:** Run `ai/venv/bin/python -m pytest core/tests/test_foundational_edit.py -v`; update class-pinned assertions only.
- [ ] **Step 5:** Browser-verify.
- [ ] **Step 6:** Commit — `git commit -m "feat(app-28): retemplate foundational editor + forbidden + success"`

### Task B4: onboarding base_wizard.html + step.html

**Files:** Modify both.

- [ ] **Step 1:** `base_wizard.html` — render the progress indicator as DaisyUI `steps` (or a `progress progress-primary` with "Step X of Y" text); wrap `step_content` in a `card bg-base-100 shadow-sm` → `card-body`; `wizard_nav` buttons: Back → `btn btn-ghost`, Continue/Finish → `btn btn-primary`, Save & Exit → `btn btn-ghost btn-sm`. Keep the `{% block step_content %}` and `{% block wizard_nav %}` names unchanged (screen 7 overrides them).
- [ ] **Step 2:** `step.html` — wrap `form.as_p` output in a styled container; keep the APP-09..16 placeholder text in a `text-sm opacity-70` note.
- [ ] **Step 3:** Run `ai/venv/bin/python -m pytest app/onboarding/tests/ -v`; update class-pinned assertions.
- [ ] **Step 4:** Browser-verify the wizard shell at `/onboarding/`.
- [ ] **Step 5:** Commit — `git commit -m "feat(app-28): retemplate onboarding wizard shell to DaisyUI"`

### Task B5: retention_policy_upload.html + retention_policy_review.html + polish (empty-catalog state, AI-outage banner, titles)

**Files:** Modify both onboarding screen-7 templates; verify per-page `<title>` across all templates.

- [ ] **Step 1:** `retention_policy_upload.html` — file input → `file-input file-input-bordered w-full`; the existing `{{ error }}` block → `alert alert-error` (this is the **AI-outage / scanned-PDF banner** surface that APP-30 + the `except` branch feed); custom `wizard_nav` buttons restyled (Back ghost, "Upload & Extract" primary, Save & Exit ghost-sm). Keep `enctype="multipart/form-data"` and `name="action"` button values (`extract`, `back`, `save_exit`) byte-identical — the view dispatches on them.
- [ ] **Step 2:** `retention_policy_review.html` — classifications + retention tables → `table table-zebra` in `overflow-x-auto`; "Re-upload" → `btn btn-ghost` (action `reupload`), "Accept & Scaffold" → `btn btn-primary` (action `accept`). Keep action values byte-identical.
- [ ] **Step 3 (polish):** Confirm every template sets a real `{% block title %}` (base default is generic "PolicyCodex"); add page-specific titles to any that lack one (`policy_edit`, `foundational_edit`, wizard steps). The empty-catalog state (B/A4) and AI-outage banner (B5 Step 1) are now covered; no AI-outage banner exists outside screen 7, so nothing else to add.
- [ ] **Step 4:** Run the full onboarding suite: `ai/venv/bin/python -m pytest app/onboarding/tests/ -v`. Then full suite spot check (no regressions): `ai/venv/bin/python -m pytest -q`.
- [ ] **Step 5:** Browser-verify screen 7 (upload form, error alert with a deliberately bad file, review tables) at 1280×720; check focus order tab-through and contrast on badges/alerts.
- [ ] **Step 6:** Commit — `git commit -m "feat(app-28): retemplate onboarding screen 7 + page titles + a11y polish"`

---

# PART C — Live HTMX interactions

**Dispatch one subagent for Part C.** Two fragment endpoints under the `htmx` namespace (`core/htmx_urls.py`, currently empty). Templates from Part B provide the attach points. TDD throughout.

> Both interactions are progressive-enhancement: the existing full-page POST flows (`action=extract` on screen 7; the formset submit in the foundational editor) MUST still work with HTMX disabled. The HTMX endpoints are additive fragments, not replacements.

### Task C1: Live PDF-upload → extraction fragment (onboarding screen 7) with progress spinner

The current flow (`app/onboarding/retention_policy.py:113-167`) does a full-page POST `action=extract` that runs `extract_text` → APP-30 empty guard → `extract_retention_bundle` (AI) → stages a draft → renders the review screen. Part C adds an HTMX path that posts the file to a fragment endpoint and swaps in either the review table or the error alert **in place**, with an `hx-indicator` spinner during the seconds-long extraction (REQUIRED — extraction looks frozen on a projector otherwise).

**Files:**
- Create: `core/htmx_urls.py` endpoint (modify the empty `urlpatterns`)
- Create: `app/onboarding/htmx_views.py` (thin fragment view, keeps business logic in `retention_policy.handle`'s helpers)
- Create: `app/onboarding/templates/onboarding/_retention_result.html` (fragment: review table OR error alert)
- Modify: `app/onboarding/templates/onboarding/retention_policy_upload.html` (add `hx-post`, `hx-target`, `hx-indicator`, spinner)
- Test: `app/onboarding/tests/test_retention_htmx.py` (create)

> **Refactor first (DRY):** the extract/guard/stage logic in `retention_policy.handle`'s `action == "extract"` branch (lines 113-167) must be reused, not copy-pasted. Extract it into a module-level helper `def run_extraction(staging, upload) -> tuple[dict | None, str | None]` returning `(draft, error)` and call it from BOTH the existing `handle` branch and the new fragment view. Keep the APP-30 empty/scanned guard and the broad `except` exactly as-is inside the helper.

- [ ] **Step 1: Write the failing tests**

```python
# app/onboarding/tests/test_retention_htmx.py
from unittest.mock import patch
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse


@pytest.fixture
def user(db):
    return get_user_model().objects.create_user(username="admin", password="secret")


def _pdf_upload(text="real text"):
    from django.core.files.uploadedfile import SimpleUploadedFile
    return SimpleUploadedFile("policy.pdf", b"%PDF-1.4 fake", content_type="application/pdf")


def test_htmx_extract_url_reverses():
    assert reverse("htmx:retention_extract") == "/htmx/retention/extract/"


@pytest.mark.django_db
def test_htmx_extract_returns_review_fragment(client, user, tmp_path, settings):
    client.force_login(user)
    with patch("app.onboarding.htmx_views.run_extraction") as run:
        run.return_value = (
            {"classifications": [{"id": "hr", "name": "HR"}],
             "retention_schedule": [], "title": "t", "owner": "o", "data_yaml": "x"},
            None,
        )
        resp = client.post(reverse("htmx:retention_extract"),
                           {"pdf_file": _pdf_upload()}, HTTP_HX_REQUEST="true")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "HR" in body                      # review table rendered
    assert "<html" not in body.lower()       # fragment, not full page


@pytest.mark.django_db
def test_htmx_extract_returns_error_alert_on_empty(client, user):
    client.force_login(user)
    with patch("app.onboarding.htmx_views.run_extraction") as run:
        run.return_value = (None, "This looks like a scanned PDF...")
        resp = client.post(reverse("htmx:retention_extract"),
                           {"pdf_file": _pdf_upload()}, HTTP_HX_REQUEST="true")
    assert resp.status_code == 200
    assert "alert-error" in resp.content.decode()
    assert "scanned PDF" in resp.content.decode()
```

- [ ] **Step 2: Run to confirm failure**

Run: `ai/venv/bin/python -m pytest app/onboarding/tests/test_retention_htmx.py -v`
Expected: FAIL (`NoReverseMatch` / module not found).

- [ ] **Step 3: Refactor `run_extraction` out of `retention_policy.handle`**

In `app/onboarding/retention_policy.py`, lift lines 117-167's body into:
```python
def run_extraction(staging: Path, upload) -> tuple[dict | None, str | None]:
    """Save the upload, extract, guard, run AI, stage a draft.

    Returns (draft, None) on success or (None, error_message) on any failure.
    Reused by the full-page handler and the HTMX fragment view.
    """
    staging.mkdir(parents=True, exist_ok=True)
    source_pdf = staging / "source.pdf"
    with source_pdf.open("wb") as fh:
        for chunk in upload.chunks():
            fh.write(chunk)
    try:
        text = extract_text(source_pdf)
        if not text.strip():
            if pdf_has_embedded_images(source_pdf):
                err = ("This looks like a scanned PDF (an image with no text "
                       "layer), so there is nothing to extract automatically. "
                       "Upload a text-based PDF of the policy and try again.")
            else:
                err = ("We could not find any readable text in that document. "
                       "Check that it is a text-based PDF and try again.")
            shutil.rmtree(staging, ignore_errors=True)
            return None, err
        bundle = extract_retention_bundle(ClaudeProvider(), text)
        data_yaml_text = build_data_yaml(bundle)
    except RetentionExtractionError as exc:
        return None, (f"Could not read that document automatically: {exc}. "
                      "Try a different PDF.")
    except Exception as exc:  # noqa: BLE001 - same degrade-don't-500 contract as before
        logger.warning("APP-15 retention extraction failed: %s", exc)
        return None, ("We couldn't process that document. Check that it is a "
                      "valid PDF and try again. If the problem persists, the AI "
                      "service may be unavailable; contact your administrator.")
    draft = {
        "title": DEFAULT_TITLE, "owner": DEFAULT_OWNER,
        "classifications": bundle.get("classifications", []),
        "retention_schedule": bundle.get("retention_schedule", []),
        "data_yaml": data_yaml_text,
    }
    (staging / "draft.yaml").write_text(
        yaml.safe_dump(draft, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return draft, None
```
Then replace the `action == "extract"` branch body (lines 113-167) to call it:
```python
    if action == "extract":
        form = RetentionPolicyUploadForm(request.POST, request.FILES)
        if not form.is_valid():
            return _render_upload(request, target, state, form=form)
        _, staging = _paths()
        draft, error = run_extraction(staging, form.cleaned_data["pdf_file"])
        if error:
            return _render_upload(request, target, state, error=error)
        return _render_review(request, target, state, draft)
```
Run `ai/venv/bin/python -m pytest app/onboarding/tests/ -k retention -v` to confirm the existing screen-7 tests (including APP-30's two guard tests) still pass after the refactor.

- [ ] **Step 4: Add the fragment view + the `_retention_result.html` fragment**

```python
# app/onboarding/htmx_views.py
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.views.decorators.http import require_POST

from app.onboarding.forms import RetentionPolicyUploadForm
from app.onboarding.retention_policy import _paths, run_extraction


@login_required
@require_POST
def retention_extract(request):
    form = RetentionPolicyUploadForm(request.POST, request.FILES)
    if not form.is_valid():
        return render(request, "onboarding/_retention_result.html",
                      {"error": "Choose a PDF file to upload."})
    _, staging = _paths()
    draft, error = run_extraction(staging, form.cleaned_data["pdf_file"])
    return render(request, "onboarding/_retention_result.html",
                  {"draft": draft, "error": error,
                   "classifications": (draft or {}).get("classifications", []),
                   "retention_schedule": (draft or {}).get("retention_schedule", [])})
```

```html
{# app/onboarding/templates/onboarding/_retention_result.html #}
{% if error %}
  <div class="alert alert-error">{{ error }}</div>
{% else %}
  <div class="space-y-4">
    <div class="alert alert-success">Extraction complete. Review below, then Accept &amp; Scaffold.</div>
    <div class="overflow-x-auto">
      <table class="table table-zebra">
        <thead><tr><th>id</th><th>name</th></tr></thead>
        <tbody>
          {% for c in classifications %}<tr><td>{{ c.id }}</td><td>{{ c.name }}</td></tr>{% endfor %}
        </tbody>
      </table>
    </div>
    {# Accept posts back through the standard full-page accept flow. #}
    <form method="post" action="{% url 'onboarding_step' step='retention-policy' %}">
      {% csrf_token %}
      <button type="submit" name="action" value="accept" class="btn btn-primary">Accept &amp; Scaffold</button>
    </form>
  </div>
{% endif %}
```

> Confirm the `onboarding_step` URL name + `retention-policy` step slug against `app/onboarding/urls.py` and `STEP_SLUG`. The Accept button reuses the existing `action=accept` server path (which reads the staged draft) — the HTMX path only swaps the review fragment, it does not change accept/scaffold.

- [ ] **Step 5: Register the route**

```python
# core/htmx_urls.py
from django.urls import path
from app.onboarding import htmx_views

app_name = "htmx"

urlpatterns = [
    path("retention/extract/", htmx_views.retention_extract, name="retention_extract"),
]
```

- [ ] **Step 6: Wire the upload template for HTMX + spinner**

In `retention_policy_upload.html`, add to the upload form (keeping the non-HTMX submit as fallback): `hx-post="{% url 'htmx:retention_extract' %}"`, `hx-target="#extract-result"`, `hx-swap="innerHTML"`, `hx-encoding="multipart/form-data"`, `hx-indicator="#extract-spinner"`. Add the spinner + result container:
```html
<span id="extract-spinner" class="htmx-indicator loading loading-spinner loading-md text-primary"></span>
<div id="extract-result" class="mt-4"></div>
```
Add to `assets/css/input.css` (then re-run `./bin/build-css.sh`): HTMX toggles visibility via the `.htmx-indicator`/`.htmx-request` classes — DaisyUI's `loading` is visible by default, so hide it until requesting:
```css
.htmx-indicator { opacity: 0; transition: opacity 150ms; }
.htmx-request .htmx-indicator,
.htmx-request.htmx-indicator { opacity: 1; }
```

- [ ] **Step 7: Run the tests**

Run: `ai/venv/bin/python -m pytest app/onboarding/tests/test_retention_htmx.py app/onboarding/tests/ -k retention -v`
Expected: PASS (new HTMX tests + existing screen-7 + APP-30 guards).

- [ ] **Step 8: Browser-verify** — upload a real text PDF, confirm spinner shows during extraction then the review table swaps in; upload an image-only/empty PDF, confirm the error alert swaps in (no full-page reload). Confirm the non-HTMX fallback still works by disabling JS.

- [ ] **Step 9: Commit**

```bash
git add core/htmx_urls.py app/onboarding/htmx_views.py app/onboarding/templates/onboarding/_retention_result.html app/onboarding/templates/onboarding/retention_policy_upload.html app/onboarding/retention_policy.py app/onboarding/tests/test_retention_htmx.py assets/css/input.css
git commit -m "feat(app-28): live HTMX PDF extraction on screen 7 with progress spinner"
```

### Task C2: Client-side row-add in the foundational typed-table editor

The editor (`core/views.py:foundational_edit`, template `core/templates/foundational_edit.html`) renders two Django formsets (`ClassificationFormSet` prefix `cls`, `RetentionRowFormSet` prefix `ret`, each `extra=1`, `can_delete=True`). "Add row" must append one blank formset row and increment the management form's `TOTAL_FORMS` so the submit posts the new row.

**Files:**
- Create: two fragment views in `core/htmx_views.py`
- Create: `core/templates/_classification_row.html`, `core/templates/_retention_row.html` (single-row fragments)
- Modify: `core/htmx_urls.py` (two routes)
- Modify: `core/templates/foundational_edit.html` (Add-row buttons + tbody ids from B3)
- Test: `core/tests/test_foundational_htmx.py` (create)

> **DRY:** the single-row markup in the new fragment templates must match the row markup already in `foundational_edit.html` (B3). Extract each row's `<tr>...</tr>` into the `_classification_row.html` / `_retention_row.html` partial and `{% include %}` it from both the formset loop in `foundational_edit.html` and the fragment view. One row definition, two render sites.

- [ ] **Step 1: Write the failing tests**

```python
# core/tests/test_foundational_htmx.py
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse


@pytest.fixture
def user(db):
    return get_user_model().objects.create_user(username="admin", password="secret")


def test_row_urls_reverse():
    assert reverse("htmx:add_classification_row") == "/htmx/foundational/add-classification-row/"
    assert reverse("htmx:add_retention_row") == "/htmx/foundational/add-retention-row/"


@pytest.mark.django_db
def test_add_classification_row_renders_indexed_blank_row(client, user):
    client.force_login(user)
    resp = client.get(reverse("htmx:add_classification_row"), {"index": "3"},
                      HTTP_HX_REQUEST="true")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert 'name="cls-3-id"' in body        # next-index blank field
    assert 'name="cls-3-name"' in body
    assert "<tr" in body and "<html" not in body.lower()


@pytest.mark.django_db
def test_add_retention_row_renders_indexed_blank_row(client, user):
    client.force_login(user)
    resp = client.get(reverse("htmx:add_retention_row"), {"index": "2"},
                      HTTP_HX_REQUEST="true")
    body = resp.content.decode()
    assert 'name="ret-2-group"' in body
    assert 'name="ret-2-type"' in body
```

- [ ] **Step 2: Run to confirm failure**

Run: `ai/venv/bin/python -m pytest core/tests/test_foundational_htmx.py -v`
Expected: FAIL (`NoReverseMatch`).

- [ ] **Step 3: Add the fragment views**

```python
# core/htmx_views.py
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest
from django.shortcuts import render

from core.forms import ClassificationForm, RetentionRowForm


def _index(request) -> int | None:
    raw = request.GET.get("index", "")
    return int(raw) if raw.isdigit() else None


@login_required
def add_classification_row(request):
    i = _index(request)
    if i is None:
        return HttpResponseBadRequest("index required")
    form = ClassificationForm(prefix=f"cls-{i}")
    return render(request, "_classification_row.html", {"f": form})


@login_required
def add_retention_row(request):
    i = _index(request)
    if i is None:
        return HttpResponseBadRequest("index required")
    form = RetentionRowForm(prefix=f"ret-{i}")
    return render(request, "_retention_row.html", {"f": form})
```

> Using `prefix=f"cls-{i}"` makes the bound field names `cls-{i}-id`, `cls-{i}-name` — matching the formset's per-form naming so the management form (with bumped `TOTAL_FORMS`) binds them on submit.

- [ ] **Step 4: Add the row fragment templates**

```html
{# core/templates/_classification_row.html #}
<tr>
  <td>{{ f.id }}</td>
  <td>{{ f.name }}</td>
  <td></td>
</tr>
```
```html
{# core/templates/_retention_row.html #}
<tr>
  <td>{{ f.group }}</td>
  <td>{{ f.sub_group }}</td>
  <td>{{ f.type }}</td>
  <td>{{ f.retention }}</td>
  <td>{{ f.medium }}</td>
  <td>{{ f.retained_at }}</td>
  <td></td>
</tr>
```
Refactor `foundational_edit.html` (from B3) so its formset loops `{% include "_classification_row.html" with f=f %}` / `{% include "_retention_row.html" with f=f %}` — single source of row markup.

- [ ] **Step 5: Register routes**

Add to `core/htmx_urls.py`:
```python
from core import htmx_views
# ...
    path("foundational/add-classification-row/", htmx_views.add_classification_row, name="add_classification_row"),
    path("foundational/add-retention-row/", htmx_views.add_retention_row, name="add_retention_row"),
```

- [ ] **Step 6: Wire Add-row buttons in `foundational_edit.html`**

After each table, add a button that fetches a blank row and appends it, then bumps `TOTAL_FORMS`. HTMX appends the returned `<tr>` to the tbody; a tiny inline `hx-on` increments the management form count and the index:
```html
<button type="button" class="btn btn-sm btn-ghost mt-2"
        hx-get="{% url 'htmx:add_classification_row' %}"
        hx-target="#cls-rows" hx-swap="beforeend"
        hx-vals='js:{index: document.getElementById("id_cls-TOTAL_FORMS").value}'
        hx-on::after-request="let n=document.getElementById('id_cls-TOTAL_FORMS'); n.value=parseInt(n.value)+1;">
  + Add classification
</button>
```
Repeat for retention with `add_retention_row`, `#ret-rows`, and `id_ret-TOTAL_FORMS`.

> The `hx-vals='js:...'` reads the current `TOTAL_FORMS` (the next blank index, since indices are 0-based), and `hx-on::after-request` increments it so the next add and the submit agree. Verify the management-form input id is `id_cls-TOTAL_FORMS` / `id_ret-TOTAL_FORMS` (Django's default for those prefixes) by inspecting the rendered page.

- [ ] **Step 7: Run the tests + the existing editor suite**

Run: `ai/venv/bin/python -m pytest core/tests/test_foundational_htmx.py core/tests/test_foundational_edit.py -v`
Expected: PASS. The existing editor submit test confirms the formset still round-trips.

- [ ] **Step 8: Browser-verify** — open the typed-table editor, click "+ Add classification" twice, fill the new rows, submit, confirm the new rows persist into `data.yaml` and the PR opens (mock/observe per existing test setup). Confirm the form still submits correctly with zero added rows (no regression).

- [ ] **Step 9: Commit**

```bash
git add core/htmx_views.py core/htmx_urls.py core/templates/_classification_row.html core/templates/_retention_row.html core/templates/foundational_edit.html core/tests/test_foundational_htmx.py
git commit -m "feat(app-28): HTMX client-side row-add in foundational typed-table editor"
```

---

# PART D — Clean-VM verification harness (REPO-10) covers the build step

**Dispatch one subagent for Part D.** The Docker image must build the CSS before `collectstatic`, and the structural harness must assert the build step exists so the generic-ship install premise holds.

### Task D1: Dockerfile runs the build; harness asserts it

**Files:**
- Modify: `Dockerfile` (add the build step before `collectstatic`)
- Modify: `tests/test_docker_packaging.py` (extend assertions)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_docker_packaging.py`:
```python
def test_dockerfile_builds_css_before_collectstatic():
    text = _read("Dockerfile")
    assert "build-css.sh" in text, "Dockerfile must run the Tailwind build"
    build_at = text.index("build-css.sh")
    collect_at = text.index("collectstatic")
    assert build_at < collect_at, "CSS build must run before collectstatic"


def test_build_script_and_input_css_exist():
    assert (_ROOT / "bin" / "build-css.sh").is_file()
    assert (_ROOT / "assets" / "css" / "input.css").is_file()


def test_build_script_downloads_toolchain_not_vendored():
    script = _read("bin/build-css.sh")
    assert "tailwindlabs/tailwindcss" in script   # scripted download, not vendored binary
    assert "daisyui.mjs" in script
```

- [ ] **Step 2: Run to confirm failure**

Run: `ai/venv/bin/python -m pytest tests/test_docker_packaging.py -v`
Expected: FAIL on `test_dockerfile_builds_css_before_collectstatic` (Dockerfile has no build step yet).

- [ ] **Step 3: Add the build step to the Dockerfile**

The Docker image has `git` but needs `curl` for the download. Modify the apt line and add the build RUN before `collectstatic` (line 26). Replace lines 7-9:
```dockerfile
RUN apt-get update \
    && apt-get install -y --no-install-recommends git curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*
```
And insert before the `collectstatic` RUN (current line 24-26):
```dockerfile
# Build the Tailwind + daisyUI stylesheet (scripted download, no Node).
RUN bash bin/build-css.sh
```

- [ ] **Step 4: Run the harness tests**

Run: `ai/venv/bin/python -m pytest tests/test_docker_packaging.py -v`
Expected: PASS (all, including the new three).

- [ ] **Step 5: Live Docker build validation (REQUIRED — matches REPO-05/11 practice)**

Run (Colima/docker daemon up):
```bash
docker build --no-cache -t policycodex:app-28 .
```
Expected: the `build-css.sh` layer downloads the Tailwind binary + daisyUI bundles and emits `static/css/policycodex.css`, then `collectstatic` reports the compiled CSS among collected files, build succeeds. If `--no-cache` download is flaky in CI, note it; the structural tests are the gate, the live build is the evidence.

- [ ] **Step 6: Commit**

```bash
git add Dockerfile tests/test_docker_packaging.py
git commit -m "feat(app-28): Docker builds Tailwind CSS before collectstatic; harness guards it"
```

---

## Final verification (controller, after all Parts)

- [ ] Full suite green: `ai/venv/bin/python -m pytest -q` (expect ~513 + the new APP-28 tests; confirm no regressions).
- [ ] `./bin/build-css.sh` from a clean `assets/.toolchain/` (delete it first) produces a non-empty `static/css/policycodex.css`.
- [ ] Browser walk-through at 1280×720: login → catalog → policy detail → policy edit → foundational typed-table editor (add a row) → onboarding wizard → screen 7 live extraction (spinner + result swap). Every page styled, Inter applied, focus rings visible, badges/alerts contrast-legible.
- [ ] Update `CLAUDE.md` Current Status + `internal/PolicyWonk-Daily-Log.md` with the APP-28 close, suite delta, and the build-chain decision (scripted-download upstream Tailwind binary + daisyUI mjs, no Node, no vendored binary). Mark APP-28 resolved in `PolicyWonk-v0.1-Tickets.md`.

---

## Self-Review (against the ticket)

**Spec coverage:**
- (a) build chain → Part A (A1 script, A2 static config, A3/A4 prove on base + catalog, browser-verified). ✓
- (b) retemplate 12 templates → A3 (base), A4 (catalog), B1-B5 (the other 10); empty-catalog state (A4/B5), AI-outage banner (B5), a11y baseline at 1280×720 (every browser-verify step + B5 Step 5), favicon + per-page titles (A2/A3/B5 Step 3). ✓
- (c) live HTMX both interactions → C1 (PDF upload→extraction with REQUIRED `hx-indicator` spinner), C2 (typed-table row-add). ✓
- (d) REPO-10 harness covers the build step → D1 (Dockerfile build-before-collectstatic + three structural assertions + live build). ✓
- Hard dependency on APP-27 (`/htmx/` prefix) → satisfied; C populates the existing empty namespace. ✓

**Decisions locked:** scripted-download (not vendored binary) per Chuck 2026-06-08; upstream Tailwind v4 standalone + daisyUI 5 `.mjs` (official no-Node path) rather than a third-party combined fork (cleaner AGPL provenance); compiled CSS + downloaded toolchain gitignored, regenerated by `bin/build-css.sh`; HTMX/Inter/favicon vendored (small, stable, not platform-specific).

**Open items a subagent must resolve in-browser (flagged inline, not placeholders):** exact `@plugin` relative-path resolution (A1 Step 3), brand `--color-primary` value (A4 Step 3), `onboarding_step` URL name/first-step slug (A4, C1), management-form input ids (C2 Step 6), login-input DaisyUI classing approach (B1).

**Type/name consistency:** `run_extraction(staging, upload) -> (draft, error)` defined in C1 Step 3, consumed in C1 Step 4; formset prefixes `cls`/`ret` and field names match `core/forms.py`; `htmx` namespace routes (`retention_extract`, `add_classification_row`, `add_retention_row`) consistent across views, urls, templates, and tests.
