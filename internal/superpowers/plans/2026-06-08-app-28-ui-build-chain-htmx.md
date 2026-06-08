# APP-28 Implementation Plan: Tailwind + DaisyUI Build Chain, Retemplate, Live HTMX, REPO-10 Harness

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the Django admin app a production CSS build (Tailwind standalone CLI + DaisyUI, committed output), retemplate all 12 templates to the DaisyUI/Inter/slate vocabulary, wire two live HTMX interactions under `/htmx/`, and extend the REPO-10 harness to assert the stylesheet ships.

**Architecture:** A gitignored toolchain (`.tools/`) downloaded by `scripts/build-css.sh` compiles `static/css/input.css` -> committed `static/css/policycodex.css`. WhiteNoise serves the committed CSS; nothing new runs at install, so the Docker/clean-VM path is unchanged. HTMX endpoints route through the single top-level `core/htmx_urls` tree (`htmx` namespace): onboarding screen-7 actions become fragment swaps via one dispatch view, and the foundational typed-table gains a server-rendered row-add fragment with an out-of-band management-form bump.

**Tech Stack:** Tailwind CSS v4 standalone CLI (single static binary), DaisyUI 5 `.mjs` plugin bundles, HTMX 2.x, Inter (self-hosted woff2), Django 6 templates, WhiteNoise `CompressedManifestStaticFilesStorage`, pytest-django. Test interpreter: `ai/venv/bin/python`.

**Spec:** `internal/superpowers/specs/2026-06-08-app-28-ui-build-chain-htmx-design.md`. Implement in order **a -> b -> c -> d**. The DaisyUI-standalone risk is de-risked inside (a) on a 2-template slice before (b) fans out.

---

## File Structure

**Created:**
- `scripts/build-css.sh` — platform-detecting fetch of Tailwind binary + DaisyUI `.mjs` into `.tools/`, then compile `policycodex.css`.
- `static/css/input.css` — Tailwind v4 entrypoint: `@import "tailwindcss"`, DaisyUI `@plugin`s, `@source` template dirs, `@font-face` Inter, theme vars.
- `static/css/policycodex.css` — committed compiled output (regenerated, never hand-edited).
- `static/js/htmx.min.js` — committed HTMX 2.x.
- `static/fonts/InterVariable.woff2`, `static/fonts/InterVariable-Italic.woff2` — committed self-hosted Inter (SIL OFL).
- `app/onboarding/htmx_urls.py` — onboarding fragment routes (no `app_name`; folds into the `htmx` namespace).
- `core/templates/fragments/classification_row.html`, `core/templates/fragments/retention_row.html` — row-add fragments with OOB management-form bump.
- `app/onboarding/templates/onboarding/_screen7_body.html` — the swappable wizard-step body (upload OR review OR error) for screen 7.
- `tests/test_css_build.py` — env-gated drift guard + structural assertions on the committed CSS.
- `core/tests/test_foundational_row.py` — row-add fragment view tests.

**Modified:**
- `policycodex_site/settings.py` — add `STATICFILES_DIRS = [BASE_DIR / 'static']`.
- `.gitignore` — add `.tools/`.
- `core/htmx_urls.py` — include onboarding fragments + foundational row endpoint.
- `core/views.py` — add `foundational_row` fragment view.
- `app/onboarding/retention_policy.py` — add `screen7_fragment` dispatch view returning fragments / `HX-Redirect`.
- `core/tests/test_htmx_urls.py` — assert the new endpoints reverse.
- All 12 templates (8 core + 4 onboarding) — retemplate to DaisyUI/Inter/slate.
- `tests/test_generic_ship.py` — add `static/` CSS/JS to the shipping scan (generic-ship guard).
- `install.sh` / `README.md` (dev notes) — document `build-css.sh` as the CSS regeneration step.

**Visual target:** `internal/mockups/disc-demo-tailwind.html`. Brand color via DaisyUI `--color-primary` (slate-blue `#4a5f8a`), slate palette, Inter.

---

## Conventions for every task

- Run tests with `ai/venv/bin/python -m pytest ...` (no root venv exists).
- Commit straight to `main` after each task's tests pass (trunk-based; eager commits).
- Co-author trailer on every commit: `Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>`.
- Shipping templates stay generic: never write "Pensacola", "Tallahassee", or a diocese name into `core/` or `app/` templates. Diocese name comes from context vars only.

---

## PART (a) — Build chain + de-risking slice

### Task A1: Toolchain script, input.css, static settings, committed JS/fonts

**Files:**
- Create: `scripts/build-css.sh`
- Create: `static/css/input.css`
- Create: `static/js/htmx.min.js` (downloaded)
- Create: `static/fonts/InterVariable.woff2`, `static/fonts/InterVariable-Italic.woff2` (downloaded)
- Modify: `.gitignore`
- Modify: `policycodex_site/settings.py:143` (after `STATIC_ROOT`)

- [ ] **Step 1: Add `.tools/` to `.gitignore`**

Append one line under the existing `.worktrees/` line:

```
.tools/
```

- [ ] **Step 2: Create `scripts/build-css.sh`**

```bash
#!/usr/bin/env bash
# Regenerate static/css/policycodex.css from static/css/input.css using the
# Tailwind standalone CLI + DaisyUI. The toolchain lives in a gitignored
# .tools/ dir and is fetched on demand; only the compiled CSS is committed.
# Run from the repo root: scripts/build-css.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TOOLS="$ROOT/.tools"
mkdir -p "$TOOLS"

# 1. Tailwind standalone CLI binary (platform-detected).
case "$(uname -s)-$(uname -m)" in
  Darwin-arm64)  TW="tailwindcss-macos-arm64" ;;
  Darwin-x86_64) TW="tailwindcss-macos-x64" ;;
  Linux-aarch64) TW="tailwindcss-linux-arm64" ;;
  Linux-x86_64)  TW="tailwindcss-linux-x64" ;;
  *) echo "Unsupported platform: $(uname -s)-$(uname -m)" >&2; exit 1 ;;
esac
if [ ! -x "$TOOLS/tailwindcss" ]; then
  echo "Downloading Tailwind standalone CLI ($TW)..."
  curl -fsSLo "$TOOLS/tailwindcss" \
    "https://github.com/tailwindlabs/tailwindcss/releases/latest/download/$TW"
  chmod +x "$TOOLS/tailwindcss"
fi

# 2. DaisyUI plugin bundles (Node-free .mjs).
for f in daisyui.mjs daisyui-theme.mjs; do
  if [ ! -f "$TOOLS/$f" ]; then
    echo "Downloading $f..."
    curl -fsSLo "$TOOLS/$f" \
      "https://github.com/saadeghi/daisyui/releases/latest/download/$f"
  fi
done

# 3. Compile (minified).
echo "Compiling static/css/policycodex.css..."
"$TOOLS/tailwindcss" \
  -i "$ROOT/static/css/input.css" \
  -o "$ROOT/static/css/policycodex.css" \
  --minify
echo "Done."
```

- [ ] **Step 3: Create `static/css/input.css`**

`@source` lines point the v4 content scanner at the Django template trees (relative to this file) so utility classes used in templates are not purged. `@plugin` paths are relative to this file but the `.mjs` live in `.tools/`; build-css.sh copies them next to input.css is NOT done — instead reference them by relative path from repo root. Use absolute-from-root style via `../../.tools/`.

```css
@import "tailwindcss";

/* Do not scan the toolchain or compiled output. */
@source not "../../.tools";

/* Scan the Django template trees so utility classes survive purge. */
@source "../../core/templates";
@source "../../app/onboarding/templates";

@plugin "../../.tools/daisyui.mjs";
@plugin "../../.tools/daisyui-theme.mjs" {
  name: "policycodex";
  default: true;
  color-scheme: light;
  --color-primary: #4a5f8a;
  --color-primary-content: #ffffff;
  --color-base-100: #ffffff;
  --color-base-200: #f1f5f9;
  --color-base-300: #e2e8f0;
  --color-base-content: #0f172a;
  --radius-box: 0.5rem;
  --radius-field: 0.375rem;
}

@font-face {
  font-family: "Inter";
  font-style: normal;
  font-weight: 100 900;
  font-display: swap;
  src: url("../fonts/InterVariable.woff2") format("woff2");
}
@font-face {
  font-family: "Inter";
  font-style: italic;
  font-weight: 100 900;
  font-display: swap;
  src: url("../fonts/InterVariable-Italic.woff2") format("woff2");
}

:root {
  font-family: "Inter", system-ui, sans-serif;
}

/* Gate badges: the three workflow states, named to match {{ gate }}. */
.gate-drafted   { background: #fef3c7; color: #92400e; }
.gate-reviewed  { background: #dbeafe; color: #1e40af; }
.gate-published { background: #d1fae5; color: #065f46; }
.gap-badge      { background: #fee2e2; color: #991b1b; }
```

- [ ] **Step 4: Download committed HTMX + Inter**

Run from repo root:

```bash
mkdir -p static/js static/fonts
curl -fsSLo static/js/htmx.min.js https://unpkg.com/htmx.org@2.0.4/dist/htmx.min.js
# Inter variable fonts (SIL OFL) from the official rsms/inter release.
curl -fsSL -o /tmp/inter.zip https://github.com/rsms/inter/releases/latest/download/Inter.zip
unzip -j -o /tmp/inter.zip 'web/InterVariable.woff2' 'web/InterVariable-Italic.woff2' -d static/fonts
ls -la static/fonts static/js
```

Expected: `static/js/htmx.min.js` (~50KB) and two `InterVariable*.woff2` files present. If the Inter release layout differs, fetch `InterVariable.woff2` from https://rsms.me/inter/font-files/InterVariable.woff2 and the italic from the same path.

- [ ] **Step 5: Add `STATICFILES_DIRS` to settings**

In `policycodex_site/settings.py`, immediately after the `STATIC_ROOT = BASE_DIR / 'staticfiles'` line (currently line 143):

```python
STATIC_ROOT = BASE_DIR / 'staticfiles'
# Project-level static sources (committed compiled CSS, HTMX, fonts). Without
# this, collectstatic only sees per-app static dirs and would miss policycodex.css.
STATICFILES_DIRS = [BASE_DIR / 'static']
```

- [ ] **Step 6: Make the script executable and commit (no compiled CSS yet)**

```bash
chmod +x scripts/build-css.sh
git add .gitignore scripts/build-css.sh static/css/input.css static/js/htmx.min.js static/fonts/ policycodex_site/settings.py
git commit -m "$(cat <<'EOF'
feat(app-28a): add Tailwind/DaisyUI build chain scaffolding

Gitignored .tools/ toolchain fetched by scripts/build-css.sh; committed
HTMX + self-hosted Inter; STATICFILES_DIRS so collectstatic sees them.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

### Task A2: De-risking slice — retemplate `base.html` + `catalog.html`, compile, browser-verify

This is the **risk gate**. If the standalone CLI cannot load the DaisyUI `.mjs` plugin, stop and fall back to plain Tailwind utilities for the ~6 component patterns (`btn`, `card`, `badge`, `alert`, `navbar`, `table`) before retemplating anything else.

**Files:**
- Modify: `core/templates/base.html` (full rewrite)
- Modify: `core/templates/catalog.html` (full rewrite)
- Create (output): `static/css/policycodex.css`

- [ ] **Step 1: Rewrite `core/templates/base.html` as the DaisyUI shell**

```html
{% load static %}
<!doctype html>
<html lang="en" data-theme="policycodex">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{% block title %}PolicyCodex{% endblock %}</title>
    <link rel="icon" href="{% static 'favicon.svg' %}" type="image/svg+xml">
    <link rel="stylesheet" href="{% static 'css/policycodex.css' %}">
    <script src="{% static 'js/htmx.min.js' %}" defer></script>
  </head>
  <body class="min-h-screen bg-base-200 text-base-content flex flex-col">
    <header class="navbar bg-base-100 border-b border-base-300 px-6">
      <div class="flex-1 flex items-center gap-2">
        <span class="w-7 h-7 rounded bg-primary text-primary-content flex items-center justify-center text-xs font-semibold">PC</span>
        <a href="{% url 'catalog' %}" class="font-semibold text-base-content">PolicyCodex</a>
      </div>
      {% if user.is_authenticated %}
        <div class="flex items-center gap-4">
          <span class="text-xs text-slate-500">Signed in as {{ user.username }}</span>
          <form method="post" action="{% url 'logout' %}">
            {% csrf_token %}
            <button type="submit" class="btn btn-ghost btn-sm">Sign out</button>
          </form>
        </div>
      {% endif %}
    </header>

    <main class="flex-1 w-full max-w-5xl mx-auto px-6 py-8">
      {% if messages %}
        <div class="space-y-2 mb-6">
          {% for message in messages %}
            <div class="alert alert-{{ message.tags|default:'info' }} text-sm py-2">{{ message }}</div>
          {% endfor %}
        </div>
      {% endif %}
      {% block content %}{% endblock %}
    </main>

    <footer class="border-t border-base-300 px-6 py-4 text-center">
      <small class="text-xs text-slate-500">
        PolicyCodex v0.1 &middot;
        <a href="{{ source_url }}" class="link link-hover text-primary">View Source</a> (AGPL-3.0)
      </small>
    </footer>
  </body>
</html>
```

Note: Django message tags are `debug info success warning error`; DaisyUI alert modifiers are `alert-info alert-success alert-warning alert-error`. `error` maps directly; `debug` falls back to `info` via the `|default`. Add a `favicon.svg` to `static/` in step 2.

- [ ] **Step 2: Add a minimal `static/favicon.svg`**

```bash
cat > static/favicon.svg <<'EOF'
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" rx="6" fill="#4a5f8a"/><text x="16" y="22" font-family="system-ui,sans-serif" font-size="14" font-weight="600" fill="#fff" text-anchor="middle">PC</text></svg>
EOF
```

- [ ] **Step 3: Rewrite `core/templates/catalog.html`**

Preserve every context var and URL the view supplies (`is_empty_onboarding`, `gap_count`, `rows`, `row.policy`, `row.gate`, `row.is_gap`, `row.policy.foundational`, the L1 foundational branch). Keep the gate-comment intent.

```html
{% extends "base.html" %}

{% block title %}Catalog | PolicyCodex{% endblock %}

{% block content %}
  <div class="flex items-end justify-between mb-6">
    <h2 class="text-xl font-semibold text-slate-900 tracking-tight">Policy catalog</h2>
  </div>

  {% if is_empty_onboarding %}
    <div class="card bg-base-100 border border-base-300">
      <div class="card-body items-center text-center py-12">
        <h3 class="text-lg font-medium text-slate-900">No policies yet</h3>
        <p class="text-sm text-slate-500 max-w-md">
          Run the onboarding wizard, or sync the diocese's policy repo by running
          <code class="text-xs">python manage.py pull_working_copy</code> on the server.
        </p>
      </div>
    </div>
  {% else %}
    {% if gap_count %}
      <div class="alert alert-warning text-sm mb-4">
        {{ gap_count }} polic{{ gap_count|pluralize:"y,ies" }} flagged: type not in the retention taxonomy. Review and re-classify.
      </div>
    {% endif %}

    <div class="card bg-base-100 border border-base-300 mb-6">
      <div class="card-body">
        <h3 class="card-title text-sm font-semibold uppercase tracking-wider text-slate-500">Approve a PR</h3>
        <p class="text-sm text-slate-500">Enter the GitHub PR number to approve.</p>
        <form method="post" action="{% url 'approve_pr' %}" class="flex items-end gap-2">
          {% csrf_token %}
          <div>
            <label for="pr_number" class="block text-xs text-slate-500 mb-1">PR number</label>
            <input type="number" name="pr_number" id="pr_number" min="1" required
                   class="input input-bordered input-sm w-32">
          </div>
          <button type="submit" class="btn btn-primary btn-sm">Approve PR</button>
        </form>
      </div>
    </div>

    <div class="card bg-base-100 border border-base-300">
      <table class="table">
        <thead>
          <tr class="text-xs uppercase tracking-wider text-slate-500">
            <th>Title</th><th>Kind</th><th>Gate</th><th class="text-right">Actions</th>
          </tr>
        </thead>
        <tbody>
          {% for row in rows %}
            <tr class="hover:bg-slate-50">
              <td>
                <a href="{% url 'policy_detail' slug=row.policy.slug %}" class="font-medium text-slate-900 hover:text-primary">
                  {{ row.policy.frontmatter.title|default:row.policy.slug }}
                </a>
                {% if row.policy.foundational %}
                  <span class="text-xs text-slate-400 ml-1">foundational</span>
                {% endif %}
                {% if row.is_gap %}
                  <span class="gap-badge inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ml-1">no retention match</span>
                {% endif %}
              </td>
              <td><span class="badge badge-ghost badge-sm">{{ row.policy.kind }}</span></td>
              <td><span class="gate-{{ row.gate }} inline-flex items-center px-2 py-0.5 rounded text-xs font-medium">{{ row.gate|title }}</span></td>
              <td class="text-right space-x-2">
                {# L1 foundational gate (APP-20): foundational policies edit only through #}
                {# the typed-table UI. Any future Delete affordance MUST live inside the #}
                {# not-foundational branch so it inherits the gate by construction. #}
                {% if row.policy.foundational %}
                  <a href="{% url 'foundational_edit' slug=row.policy.slug %}" class="link link-primary text-sm">Edit (typed table)</a>
                {% else %}
                  <a href="{% url 'policy_edit' slug=row.policy.slug %}" class="link link-primary text-sm">Edit</a>
                {% endif %}
                {% if row.gate == "reviewed" %}
                  <form method="post" action="{% url 'publish_policy' slug=row.policy.slug %}" class="inline">
                    {% csrf_token %}
                    <button type="submit" class="btn btn-primary btn-xs">Publish</button>
                  </form>
                {% endif %}
              </td>
            </tr>
          {% empty %}
            <tr><td colspan="4" class="text-center text-slate-500 py-6">No policies in the working copy.</td></tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
  {% endif %}
{% endblock %}
```

- [ ] **Step 4: Compile the CSS**

Run: `scripts/build-css.sh`
Expected: prints download lines (first run), then `Compiling...` / `Done.`, and `static/css/policycodex.css` exists and is non-trivially sized (`wc -c static/css/policycodex.css` > 10000).

**If this step fails** because the `@plugin` directive errors under the standalone CLI: this is the spec's named risk. Switch input.css to plain Tailwind only (drop the `@plugin` lines), and in the templates replace DaisyUI component classes (`btn`, `card`, `badge`, `alert`, `navbar`, `table`, `input`) with the equivalent utility recipes from the mockup (e.g. button -> `px-3 py-1.5 text-sm bg-primary text-primary-content rounded-md font-medium hover:opacity-90`). Record the decision at the top of this plan and continue. Do not proceed to (b) until the slice compiles and renders.

- [ ] **Step 5: Browser-verify the slice at 1280x720**

Run the dev server and load `/catalog/` (log in first). Confirm: navbar renders with the PC mark, Inter font is active, the empty-state card and/or the policy table render with DaisyUI styling, gate badges show their colors, the footer "View Source" link is present. Resize the window to 1280x720 (projector resolution) and confirm no horizontal scroll / clipped content.

```bash
ai/venv/bin/python manage.py runserver 0.0.0.0:8000
```

(Use the Chrome browser tools to load `http://localhost:8000/catalog/`, screenshot at 1280x720, and confirm visually. Stop the server when done.)

- [ ] **Step 6: Commit the slice + compiled CSS**

```bash
git add core/templates/base.html core/templates/catalog.html static/css/policycodex.css static/favicon.svg
git commit -m "$(cat <<'EOF'
feat(app-28a): de-risk DaisyUI standalone build on base + catalog slice

Compiled policycodex.css committed; base shell + catalog retemplated to
DaisyUI/Inter/slate, browser-verified at 1280x720.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

### Task A3: Drift-guard + structural CSS tests

**Files:**
- Create: `tests/test_css_build.py`

- [ ] **Step 1: Write the tests**

```python
"""APP-28a: guard the committed Tailwind/DaisyUI CSS.

Structural assertions run everywhere (offline). The drift guard regenerates
the CSS and diffs it; it is env-gated (mirrors INGEST-06's POLICYCODEX_CORPUS_DIR
pattern) so the offline suite stays green and CI/local with the toolchain wired
runs the real check.
"""
import os
import subprocess
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_CSS = _ROOT / "static" / "css" / "policycodex.css"


def test_compiled_css_is_committed_and_nontrivial():
    assert _CSS.is_file(), "static/css/policycodex.css must be committed"
    assert _CSS.stat().st_size > 10_000, "compiled CSS looks empty/truncated"


def test_compiled_css_carries_brand_and_component_sentinels():
    text = _CSS.read_text(encoding="utf-8")
    # Brand color (from the daisyui-theme @plugin) and a DaisyUI component rule
    # both survive the build. If the plain-Tailwind fallback was taken, the
    # .btn sentinel below must be updated to the chosen utility recipe.
    assert "#4a5f8a" in text or "74 95 138" in text or "4a5f8a" in text.lower()
    assert ".btn" in text


@pytest.mark.skipif(
    os.environ.get("POLICYCODEX_BUILD_CSS") != "1",
    reason="set POLICYCODEX_BUILD_CSS=1 to run the CSS drift guard (needs the toolchain)",
)
def test_committed_css_matches_a_fresh_build():
    subprocess.run([str(_ROOT / "scripts" / "build-css.sh")], check=True, cwd=_ROOT)
    diff = subprocess.run(
        ["git", "diff", "--exit-code", "static/css/policycodex.css"],
        cwd=_ROOT, capture_output=True, text=True,
    )
    assert diff.returncode == 0, (
        "Committed policycodex.css is stale. Run scripts/build-css.sh and commit:\n"
        + diff.stdout
    )
```

- [ ] **Step 2: Run the tests**

Run: `ai/venv/bin/python -m pytest tests/test_css_build.py -v`
Expected: 2 pass, 1 skipped (drift guard skips without the env var).

- [ ] **Step 3: Verify the drift guard actually fires (one-time manual check)**

Run: `POLICYCODEX_BUILD_CSS=1 ai/venv/bin/python -m pytest tests/test_css_build.py::test_committed_css_matches_a_fresh_build -v`
Expected: PASS (the committed CSS matches a fresh build). If it FAILS, the committed CSS is stale — run `scripts/build-css.sh`, re-commit, and re-run.

- [ ] **Step 4: Commit**

```bash
git add tests/test_css_build.py
git commit -m "$(cat <<'EOF'
test(app-28a): structural + env-gated drift guard for compiled CSS

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## PART (b) — Retemplate the remaining 10 templates

Each task rewrites one template (or a tight group) to the same vocabulary established in the slice: `card bg-base-100 border border-base-300`, `btn btn-primary` / `btn btn-ghost`, `input input-bordered`, `table`, `alert`, `badge`, gate badge spans, Inter, slate text (`text-slate-900` headings, `text-slate-500` secondary). After every template change, recompile (`scripts/build-css.sh`) so new utility classes land in `policycodex.css`, then commit template + regenerated CSS together. Keep all context vars, URLs, form fields, and CSRF tokens intact. **Never introduce a diocese name.**

> After each task below: run `scripts/build-css.sh`, run `ai/venv/bin/python -m pytest -q` to confirm nothing broke, then `git add` the template(s) **and** `static/css/policycodex.css` and commit.

### Task B1: `policy_detail.html`

- [ ] **Step 1: Rewrite**

```html
{% extends "base.html" %}

{% block title %}{{ policy.frontmatter.title|default:policy.slug }} | PolicyCodex{% endblock %}

{% block content %}
  <div class="text-xs text-slate-500 mb-2">
    <a href="{% url 'catalog' %}" class="hover:text-slate-700">Policies</a>
    <span class="mx-1">/</span>
    <span class="text-slate-700">{{ policy.frontmatter.title|default:policy.slug }}</span>
  </div>

  <div class="flex items-start justify-between">
    <div>
      <h2 class="text-2xl font-semibold text-slate-900 tracking-tight">{{ policy.frontmatter.title|default:policy.slug }}</h2>
      <div class="flex items-center gap-2 mt-2">
        <code class="text-xs text-slate-500">policies/{{ policy.slug }}</code>
        <span class="badge badge-ghost badge-sm">{{ policy.kind }}</span>
        {% if policy.foundational %}<span class="text-xs text-slate-400">foundational</span>{% endif %}
        <span class="gate-{{ gate }} inline-flex items-center px-2 py-0.5 rounded text-xs font-medium">{{ gate|title }}</span>
      </div>
    </div>
  </div>

  {% if policy.foundational and policy.provides %}
    <div class="card bg-base-100 border border-base-300 mt-6">
      <div class="card-body">
        <h3 class="card-title text-sm font-semibold uppercase tracking-wider text-slate-500">Provides</h3>
        <ul class="list-disc list-inside text-sm text-slate-700">
          {% for item in policy.provides %}<li>{{ item }}</li>{% endfor %}
        </ul>
      </div>
    </div>
  {% endif %}

  <div class="grid grid-cols-3 gap-8 mt-8">
    <div class="col-span-2">
      <h3 class="text-sm font-semibold uppercase tracking-wider text-slate-500 mb-3">Document</h3>
      <pre class="text-sm text-slate-700 whitespace-pre-wrap bg-base-100 border border-base-300 rounded-lg p-4">{{ policy.body }}</pre>
    </div>
    <div class="col-span-1">
      <h3 class="text-sm font-semibold uppercase tracking-wider text-slate-500 mb-3">Metadata</h3>
      <dl class="space-y-3 text-sm">
        {% for key, value in policy.frontmatter.items %}
          <div><dt class="text-xs text-slate-500">{{ key }}</dt><dd class="text-slate-900 mt-0.5">{{ value }}</dd></div>
        {% endfor %}
      </dl>
    </div>
  </div>

  {# L1 foundational gate (APP-20/APP-23): foundational policies edit only through #}
  {# the typed-table UI; flat policies show the ordinary edit link. #}
  <div class="mt-8 flex items-center gap-3">
    {% if policy.foundational %}
      <span class="text-sm text-slate-500">This policy is foundational; edit through the typed-table UI.</span>
      <a href="{% url 'foundational_edit' slug=policy.slug %}" class="btn btn-primary btn-sm">Edit (typed table)</a>
    {% else %}
      <a href="{% url 'policy_edit' slug=policy.slug %}" class="btn btn-primary btn-sm">Edit</a>
    {% endif %}
    <a href="{% url 'catalog' %}" class="btn btn-ghost btn-sm">Back to catalog</a>
  </div>
{% endblock %}
```

- [ ] **Step 2: Recompile, test, commit** (`scripts/build-css.sh`; `ai/venv/bin/python -m pytest -q`; commit template + CSS with message `feat(app-28b): retemplate policy_detail`).

### Task B2: `policy_edit.html`, `policy_edit_success.html`

- [ ] **Step 1: Rewrite `core/templates/policy_edit.html`**

The view passes `policy` and a `PolicyEditForm` `form` (fields `title`, `body`, `summary`). Render fields explicitly with DaisyUI inputs.

```html
{% extends "base.html" %}

{% block title %}Edit {{ policy.frontmatter.title|default:policy.slug }} | PolicyCodex{% endblock %}

{% block content %}
  <h2 class="text-xl font-semibold text-slate-900 tracking-tight mb-1">Edit {{ policy.frontmatter.title|default:policy.slug }}</h2>
  <p class="text-sm text-slate-500 mb-6">Saving opens a pull request that flows Drafted &rarr; Reviewed &rarr; Published.</p>

  <form method="post" class="card bg-base-100 border border-base-300">
    <div class="card-body space-y-4">
      {% csrf_token %}
      <div>
        <label for="{{ form.title.id_for_label }}" class="block text-xs text-slate-500 mb-1">Title</label>
        {{ form.title }}
        {{ form.title.errors }}
      </div>
      <div>
        <label for="{{ form.body.id_for_label }}" class="block text-xs text-slate-500 mb-1">Body (markdown)</label>
        {{ form.body }}
        {{ form.body.errors }}
      </div>
      <div>
        <label for="{{ form.summary.id_for_label }}" class="block text-xs text-slate-500 mb-1">Change summary (optional)</label>
        {{ form.summary }}
        <p class="text-xs text-slate-400 mt-1">{{ form.summary.help_text }}</p>
      </div>
      <div class="flex gap-2">
        <button type="submit" class="btn btn-primary btn-sm">Open PR</button>
        <a href="{% url 'catalog' %}" class="btn btn-ghost btn-sm">Cancel</a>
      </div>
    </div>
  </form>
{% endblock %}
```

To give the widgets DaisyUI classes without touching `core/forms.py` field-by-field, add Tailwind `@layer` defaults is overkill; instead add CSS in `input.css` that styles bare form controls inside `.card-body` is brittle. Simplest: append a small base rule to `input.css` after the `:root` block so unclassed inputs/textareas pick up the input look:

```css
.card-body input[type="text"],
.card-body input[type="number"],
.card-body textarea {
  @apply input input-bordered w-full;
}
.card-body textarea { @apply h-auto leading-relaxed; }
```

(Add that to `static/css/input.css` in this step and recompile.)

- [ ] **Step 2: Rewrite `core/templates/policy_edit_success.html`**

The view passes `policy` and `pr` (a dict with a `url`). Verify the existing field name by reading the current template before editing; mirror whatever keys it references.

```html
{% extends "base.html" %}

{% block title %}PR opened | PolicyCodex{% endblock %}

{% block content %}
  <div class="card bg-base-100 border border-base-300 max-w-xl mx-auto">
    <div class="card-body items-center text-center py-10">
      <div class="badge badge-success badge-lg mb-2">Pull request opened</div>
      <h2 class="text-lg font-medium text-slate-900">Your change to {{ policy.frontmatter.title|default:policy.slug }} is in review</h2>
      <p class="text-sm text-slate-500">A reviewer must approve before it can be published.</p>
      {% if pr.url %}<a href="{{ pr.url }}" class="btn btn-primary btn-sm">View pull request</a>{% endif %}
      <a href="{% url 'catalog' %}" class="btn btn-ghost btn-sm">Back to catalog</a>
    </div>
  </div>
{% endblock %}
```

- [ ] **Step 3: Read the current `policy_edit_success.html` first** to confirm the `pr` key name (`pr.url` vs `pr.html_url`) and adjust the link above to match before saving.

- [ ] **Step 4: Recompile, test, commit** (message `feat(app-28b): retemplate policy edit + success`).

### Task B3: `foundational_edit.html`, `foundational_edit_forbidden.html`

These get the typed-table styling AND, in Part (c), the HTMX Add-row buttons. In (b) only restyle; (c) wires the buttons. Add `id` to each `<tbody>` now so (c) can target them.

- [ ] **Step 1: Rewrite `core/templates/foundational_edit.html`**

Preserve `cforms`/`rforms` formsets, `management_form`, `meta`, `error`. Add `id="cls-rows"` and `id="ret-rows"` on the tbodies (used in Part c).

```html
{% extends "base.html" %}

{% block title %}Edit {{ policy.frontmatter.title|default:policy.slug }} | PolicyCodex{% endblock %}

{% block content %}
  <h2 class="text-xl font-semibold text-slate-900 tracking-tight mb-1">Edit {{ policy.frontmatter.title|default:policy.slug }}</h2>
  <p class="text-sm text-slate-500 mb-6">This is a foundational policy. Saving opens a pull request that flows Drafted &rarr; Reviewed &rarr; Published.</p>

  {% if error %}<div class="alert alert-error text-sm mb-4">{{ error }}</div>{% endif %}

  <form method="post" class="space-y-8">
    {% csrf_token %}

    <section>
      <h3 class="text-sm font-semibold uppercase tracking-wider text-slate-500 mb-3">Classifications</h3>
      {{ cforms.management_form }}
      <div class="card bg-base-100 border border-base-300 overflow-hidden">
        <table class="table table-sm">
          <thead><tr class="text-xs uppercase tracking-wider text-slate-500"><th>id</th><th>name</th><th class="w-16">delete</th></tr></thead>
          <tbody id="cls-rows">
            {% for f in cforms %}
              <tr class="hover:bg-slate-50">
                <td>{{ f.id }}{{ f.id.errors }}</td>
                <td>{{ f.name }}{{ f.name.errors }}</td>
                <td>{% if f.DELETE %}{{ f.DELETE }}{% endif %}</td>
              </tr>
            {% endfor %}
          </tbody>
        </table>
      </div>
      {# APP-28c wires this button to htmx:foundational_row #}
      <button type="button" class="btn btn-ghost btn-xs mt-2"
              hx-post="{% url 'htmx:foundational_row' slug=policy.slug %}"
              hx-vals='js:{formset: "cls", index: document.getElementById("id_cls-TOTAL_FORMS").value}'
              hx-target="#cls-rows" hx-swap="beforeend">+ Add classification</button>
    </section>

    <section>
      <h3 class="text-sm font-semibold uppercase tracking-wider text-slate-500 mb-3">Retention schedule</h3>
      {{ rforms.management_form }}
      <div class="card bg-base-100 border border-base-300 overflow-hidden">
        <table class="table table-sm">
          <thead><tr class="text-xs uppercase tracking-wider text-slate-500">
            <th>group</th><th>sub_group</th><th>type</th><th>retention</th><th>medium</th><th>retained_at</th><th class="w-16">delete</th>
          </tr></thead>
          <tbody id="ret-rows">
            {% for f in rforms %}
              <tr class="hover:bg-slate-50">
                <td>{{ f.group }}{{ f.group.errors }}</td>
                <td>{{ f.sub_group }}</td>
                <td>{{ f.type }}{{ f.type.errors }}</td>
                <td>{{ f.retention }}{{ f.retention.errors }}</td>
                <td>{{ f.medium }}</td>
                <td>{{ f.retained_at }}</td>
                <td>{% if f.DELETE %}{{ f.DELETE }}{% endif %}</td>
              </tr>
            {% endfor %}
          </tbody>
        </table>
      </div>
      <button type="button" class="btn btn-ghost btn-xs mt-2"
              hx-post="{% url 'htmx:foundational_row' slug=policy.slug %}"
              hx-vals='js:{formset: "ret", index: document.getElementById("id_ret-TOTAL_FORMS").value}'
              hx-target="#ret-rows" hx-swap="beforeend">+ Add retention rule</button>
    </section>

    <div>
      <label for="{{ meta.summary.id_for_label }}" class="block text-xs text-slate-500 mb-1">Change summary (optional)</label>
      {{ meta.summary }}
    </div>

    <div class="flex gap-2">
      <button type="submit" class="btn btn-primary btn-sm">Open PR</button>
      <a href="{% url 'catalog' %}" class="btn btn-ghost btn-sm">Cancel</a>
    </div>
  </form>
{% endblock %}
```

The `{% url 'htmx:foundational_row' %}` reference requires the URL from Part (c). Since (b) runs before (c), the template would `NoReverseMatch` at render. To keep (b) shippable, add the URL route in this task first (it is a one-liner; the view comes in (c)). Insert into `core/htmx_urls.py` now:

```python
from django.urls import include, path
from core import views as core_views

app_name = "htmx"

urlpatterns = [
    path("foundational/<slug:slug>/row/", core_views.foundational_row, name="foundational_row"),
]
```

...and add a stub `foundational_row` to `core/views.py` (real body lands in Part c Task C3):

```python
@login_required
@require_POST
def foundational_row(request, slug):
    raise Http404("APP-28c not yet wired")  # replaced in Task C3
```

This keeps the template reversible now and the suite green; Task C3 replaces the stub. (The matching `test_htmx_urls.py` update also moves to Part c.)

- [ ] **Step 2: Rewrite `core/templates/foundational_edit_forbidden.html`** (read it first to confirm its context var, likely `policy`).

```html
{% extends "base.html" %}

{% block title %}Foundational policy | PolicyCodex{% endblock %}

{% block content %}
  <div class="card bg-base-100 border border-base-300 max-w-xl mx-auto">
    <div class="card-body items-center text-center py-10">
      <div class="badge badge-warning badge-lg mb-2">Edit blocked</div>
      <h2 class="text-lg font-medium text-slate-900">{{ policy.frontmatter.title|default:policy.slug }} is a foundational policy</h2>
      <p class="text-sm text-slate-500">Edit it through the typed-table editor, not the flat editor.</p>
      <a href="{% url 'foundational_edit' slug=policy.slug %}" class="btn btn-primary btn-sm">Open typed-table editor</a>
      <a href="{% url 'catalog' %}" class="btn btn-ghost btn-sm">Back to catalog</a>
    </div>
  </div>
{% endblock %}
```

- [ ] **Step 3: Recompile, run full suite, commit** (message `feat(app-28b): retemplate foundational editor + reserve htmx row route`). The full suite must stay green with the stub route.

### Task B4: `registration/login.html`

- [ ] **Step 1: Read the current `core/templates/registration/login.html`** to confirm whether it extends `base.html` and the form var name (`form`).

- [ ] **Step 2: Rewrite to a centered DaisyUI card**

```html
{% extends "base.html" %}

{% block title %}Sign in | PolicyCodex{% endblock %}

{% block content %}
  <div class="card bg-base-100 border border-base-300 max-w-sm mx-auto mt-12">
    <div class="card-body space-y-4">
      <h2 class="text-lg font-semibold text-slate-900 text-center">Sign in</h2>
      {% if form.errors %}<div class="alert alert-error text-sm">Your username and password didn't match. Try again.</div>{% endif %}
      <form method="post" class="space-y-4">
        {% csrf_token %}
        <div>
          <label for="{{ form.username.id_for_label }}" class="block text-xs text-slate-500 mb-1">Username</label>
          {{ form.username }}
        </div>
        <div>
          <label for="{{ form.password.id_for_label }}" class="block text-xs text-slate-500 mb-1">Password</label>
          {{ form.password }}
        </div>
        <button type="submit" class="btn btn-primary btn-sm w-full">Sign in</button>
      </form>
    </div>
  </div>
{% endblock %}
```

If the current login template does NOT extend `base.html` (standalone), keep it extending base for the shell. The `.card-body input` rule from Task B2 styles the username/password inputs.

- [ ] **Step 3: Recompile, test, browser-verify the login page renders, commit** (message `feat(app-28b): retemplate login`).

### Task B5: Onboarding shell — `base_wizard.html`, `step.html`

- [ ] **Step 1: Rewrite `app/onboarding/templates/onboarding/base_wizard.html`**

Preserve `index`, `total`, `step.title`, `multipart`, `prev_step`, `is_last`, and the `wizard_nav` / `step_content` blocks (screen-7 templates override `wizard_nav` to empty).

```html
{% extends "base.html" %}

{% block title %}Onboarding | PolicyCodex{% endblock %}

{% block content %}
  <div class="max-w-2xl mx-auto">
    <div class="flex items-center gap-1.5 mb-2">
      {% for n in ""|center:total %}
        <div class="h-1.5 flex-1 rounded-full {% if forloop.counter <= index %}bg-primary{% else %}bg-base-300{% endif %}"></div>
      {% endfor %}
    </div>
    <p class="text-xs text-slate-500 mb-6">Step {{ index }} of {{ total }} &middot; {{ step.title }}</p>

    <form method="post"{% if multipart %} enctype="multipart/form-data"{% endif %} class="card bg-base-100 border border-base-300">
      <div class="card-body space-y-4">
        {% csrf_token %}
        {% block step_content %}{% endblock %}
        {% block wizard_nav %}
        <div class="flex justify-between pt-4 border-t border-base-300">
          <div>{% if prev_step %}<button type="submit" name="action" value="back" class="btn btn-ghost btn-sm">&larr; Back</button>{% endif %}</div>
          <div class="flex gap-2">
            <button type="submit" name="action" value="continue" class="btn btn-primary btn-sm">{% if is_last %}Finish{% else %}Continue{% endif %}</button>
            <button type="submit" name="action" value="save_exit" class="btn btn-ghost btn-sm">Save and exit</button>
          </div>
        </div>
        {% endblock %}
      </div>
    </form>
  </div>
{% endblock %}
```

The progress-bar loop uses `""|center:total` to iterate `total` times (a template-only count with no view change). Verify it renders the right number of segments in the browser.

- [ ] **Step 2: Rewrite `app/onboarding/templates/onboarding/step.html`**

```html
{% extends "onboarding/base_wizard.html" %}

{% block step_content %}
  {% if form %}
    {{ form.as_p }}
  {% else %}
    <p class="text-sm text-slate-500">This screen's content lands in APP-09 through APP-16.</p>
  {% endif %}
{% endblock %}
```

- [ ] **Step 3: Recompile, test, browser-verify a wizard step renders (progress bar + nav), commit** (message `feat(app-28b): retemplate onboarding wizard shell`).

### Task B6: DoD extras — AI-outage banner partial, a11y pass, full-suite visual sweep

- [ ] **Step 1: Create a reusable AI-outage alert partial** `core/templates/fragments/ai_outage.html`:

```html
<div class="alert alert-error text-sm">
  <span>We couldn't reach the AI service. Your work is saved; try again, or contact your administrator if it persists.</span>
</div>
```

(Used by the screen-7 extract fragment in Part c. Creating it here keeps the retemplate vocabulary in one pass.)

- [ ] **Step 2: a11y baseline sweep** across all retemplated pages: every form control has an associated `<label for>` (done above), focus rings are visible (DaisyUI `input`/`btn` provide them), and text/background contrast meets WCAG AA (slate-900 on white, slate-500 for secondary only). Fix any unlabeled control found.

- [ ] **Step 3: Browser-verify each page at 1280x720**: catalog (empty + populated), policy_detail, policy_edit, foundational_edit, login, a wizard step. Confirm no clipping, consistent navbar/footer, Inter active everywhere.

- [ ] **Step 4: Recompile, run full suite, commit** (message `feat(app-28b): DoD extras — outage banner, a11y, favicon, titles`).

---

## PART (c) — Live HTMX under `/htmx/`

### Task C1: Onboarding screen-7 fragment dispatch view

**Files:**
- Modify: `app/onboarding/retention_policy.py`
- Create: `app/onboarding/templates/onboarding/_screen7_body.html`
- Create: `app/onboarding/htmx_urls.py`
- Modify: `core/htmx_urls.py`

- [ ] **Step 1: Extract the screen-7 body into a swappable partial**

Create `app/onboarding/templates/onboarding/_screen7_body.html`. It renders ONE of three states based on `mode` (`upload` / `review` / nothing). The outer element has `id="screen7-body"` so HTMX can `outerHTML`-swap it.

```html
<div id="screen7-body" class="space-y-4">
  {% if mode == "review" %}
    <p class="text-sm text-slate-600">Review the extracted data. Accept to scaffold your foundational Document Retention Policy, or re-upload a corrected PDF.</p>

    <h3 class="text-sm font-semibold uppercase tracking-wider text-slate-500">{{ classifications|length }} classifications</h3>
    <div class="card bg-base-100 border border-base-300 overflow-hidden">
      <table class="table table-sm"><thead><tr><th>id</th><th>name</th></tr></thead>
        <tbody>{% for c in classifications %}<tr><td>{{ c.id }}</td><td>{{ c.name }}</td></tr>{% endfor %}</tbody>
      </table>
    </div>

    <h3 class="text-sm font-semibold uppercase tracking-wider text-slate-500">{{ retention_schedule|length }} retention rows</h3>
    <div class="card bg-base-100 border border-base-300 overflow-hidden">
      <table class="table table-sm"><thead><tr><th>group</th><th>type</th><th>retention</th></tr></thead>
        <tbody>{% for r in retention_schedule %}<tr><td>{{ r.group }}</td><td>{{ r.type }}</td><td>{{ r.retention }}</td></tr>{% endfor %}</tbody>
      </table>
    </div>

    <div class="flex justify-between pt-4 border-t border-base-300">
      <button type="submit" name="action" value="reupload" class="btn btn-ghost btn-sm"
              hx-post="{% url 'htmx:onboarding_screen7' %}" hx-target="#screen7-body" hx-swap="outerHTML">Re-upload a different PDF</button>
      <button type="submit" name="action" value="accept" class="btn btn-primary btn-sm"
              hx-post="{% url 'htmx:onboarding_screen7' %}" hx-target="#screen7-body" hx-swap="outerHTML"
              hx-indicator="#screen7-spinner">Accept and scaffold</button>
    </div>
  {% else %}
    <p class="text-sm text-slate-600">Upload your diocese's Document Retention Policy. We extract its classifications and retention schedule for you to review.</p>
    {{ form.as_p }}
    {% if error %}<div class="alert alert-error text-sm">{{ error }}</div>{% endif %}
    <div class="flex justify-between pt-4 border-t border-base-300">
      <button type="submit" name="action" value="back" class="btn btn-ghost btn-sm"
              hx-post="{% url 'htmx:onboarding_screen7' %}" hx-target="#screen7-body" hx-swap="outerHTML">&larr; Back</button>
      <button type="submit" name="action" value="extract" class="btn btn-primary btn-sm"
              hx-post="{% url 'htmx:onboarding_screen7' %}" hx-target="#screen7-body" hx-swap="outerHTML"
              hx-encoding="multipart/form-data" hx-indicator="#screen7-spinner">Upload and extract</button>
      <button type="submit" name="action" value="save_exit" class="btn btn-ghost btn-sm"
              hx-post="{% url 'htmx:onboarding_screen7' %}" hx-target="#screen7-body" hx-swap="outerHTML">Save and exit</button>
    </div>
  {% endif %}
  <div id="screen7-spinner" class="htmx-indicator flex items-center gap-3 text-sm text-slate-500">
    <span class="loading loading-spinner loading-sm text-primary"></span>
    Extracting classifications and retention schedule. This usually takes 15 to 30 seconds.
  </div>
</div>
```

The buttons live inside the wizard `<form>` (screen-7's two page templates wrap this partial in the form). All actions `hx-post` to one endpoint targeting `#screen7-body`. The `htmx-indicator` spinner shows during the seconds-long extract/accept calls (DaisyUI `loading loading-spinner`; HTMX toggles `.htmx-indicator` opacity automatically). Add to `input.css` so the indicator is hidden by default and shown during a request:

```css
.htmx-indicator { opacity: 0; transition: opacity 0.2s; }
.htmx-request .htmx-indicator, .htmx-request.htmx-indicator { opacity: 1; }
```

- [ ] **Step 2: Point the two screen-7 page templates at the partial**

Rewrite `app/onboarding/templates/onboarding/retention_policy_upload.html`:

```html
{% extends "onboarding/base_wizard.html" %}
{% block wizard_nav %}{% endblock %}
{% block step_content %}{% include "onboarding/_screen7_body.html" with mode="upload" %}{% endblock %}
```

Rewrite `app/onboarding/templates/onboarding/retention_policy_review.html`:

```html
{% extends "onboarding/base_wizard.html" %}
{% block wizard_nav %}{% endblock %}
{% block step_content %}{% include "onboarding/_screen7_body.html" with mode="review" %}{% endblock %}
```

- [ ] **Step 3: Add the fragment dispatch view to `app/onboarding/retention_policy.py`**

Add a new view that mirrors `handle()`'s action dispatch but returns fragment responses. Reuse `_paths`, `_load_draft`, `_base_ctx`-style context, and the existing extract/accept logic. Add at the end of the file:

```python
from django.http import HttpResponse
from django.template.loader import render_to_string


def _render_body(request, *, mode, form=None, error=None, classifications=None, retention_schedule=None):
    html = render_to_string("onboarding/_screen7_body.html", {
        "mode": mode,
        "form": form or RetentionPolicyUploadForm(),
        "error": error,
        "classifications": classifications or [],
        "retention_schedule": retention_schedule or [],
    }, request=request)
    return HttpResponse(html)


def screen7_fragment(request):
    """HTMX endpoint (APP-28c): all screen-7 actions return a #screen7-body
    fragment swap, except navigation (back/save_exit/accept) which returns an
    HX-Redirect so the browser performs a real page change.
    """
    target = wizard.step_for(STEP_SLUG)
    state = wizard.load_state(request)
    policies_dir, staging = _paths()
    action = request.POST.get("action")

    if action == "back":
        prev = wizard.prev_step(STEP_SLUG)
        url = f"/onboarding/{prev.slug}/" if prev else f"/onboarding/{STEP_SLUG}/"
        return _hx_redirect(url)
    if action == "save_exit":
        messages.info(request, "Your progress is saved. Resume onboarding any time.")
        return _hx_redirect("/catalog/")

    if action == "extract":
        return _do_extract(request, staging)
    if action == "reupload":
        if staging.exists():
            shutil.rmtree(staging)
        return _render_body(request, mode="upload")
    if action == "accept":
        return _do_accept(request, state, policies_dir, staging)

    draft = _load_draft(staging)
    if draft is not None:
        return _render_body(request, mode="review",
                            classifications=draft.get("classifications", []),
                            retention_schedule=draft.get("retention_schedule", []))
    return _render_body(request, mode="upload")


def _hx_redirect(url):
    resp = HttpResponse(status=204)
    resp["HX-Redirect"] = url
    return resp
```

The extract and accept logic is the body of `handle()` (lines 113-214), lifted into helpers that RETURN fragment responses instead of full-page renders. The AI-call sequence (APP-30 empty-PDF guard, `extract_retention_bundle`, `build_data_yaml`, the `RetentionExtractionError` and bare-`except` branches) stays byte-for-byte; only the return targets change from `_render_upload(...)`/`_render_review(...)` to `_render_body(...)`/`_hx_redirect(...)`. Add both helpers to `app/onboarding/retention_policy.py`:

```python
def _do_extract(request, staging):
    form = RetentionPolicyUploadForm(request.POST, request.FILES)
    if not form.is_valid():
        return _render_body(request, mode="upload", form=form)
    staging.mkdir(parents=True, exist_ok=True)
    source_pdf = staging / "source.pdf"
    with source_pdf.open("wb") as fh:
        for chunk in form.cleaned_data["pdf_file"].chunks():
            fh.write(chunk)
    try:
        text = extract_text(source_pdf)
        if not text.strip():
            if pdf_has_embedded_images(source_pdf):
                guard_error = (
                    "This looks like a scanned PDF (an image with no text "
                    "layer), so there is nothing to extract automatically. "
                    "Upload a text-based PDF of the policy and try again."
                )
            else:
                guard_error = (
                    "We could not find any readable text in that document. "
                    "Check that it is a text-based PDF and try again."
                )
            shutil.rmtree(staging, ignore_errors=True)
            return _render_body(request, mode="upload", error=guard_error)
        bundle = extract_retention_bundle(ClaudeProvider(), text)
        data_yaml_text = build_data_yaml(bundle)
    except RetentionExtractionError as exc:
        return _render_body(
            request, mode="upload",
            error=f"Could not read that document automatically: {exc}. Try a different PDF.",
        )
    except Exception as exc:  # noqa: BLE001 - onboarding must not 500 on a bad
        # upload or an AI provider outage; degrade to the AI-outage fragment.
        logger.warning("APP-15 retention extraction failed: %s", exc)
        return _render_body(
            request, mode="upload",
            error="We couldn't process that document. Check that it is a valid "
                  "PDF and try again. If the problem persists, the AI service "
                  "may be unavailable; contact your administrator.",
        )
    draft = {
        "title": DEFAULT_TITLE,
        "owner": DEFAULT_OWNER,
        "classifications": bundle.get("classifications", []),
        "retention_schedule": bundle.get("retention_schedule", []),
        "data_yaml": data_yaml_text,
    }
    (staging / "draft.yaml").write_text(
        yaml.safe_dump(draft, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    return _render_body(request, mode="review",
                        classifications=draft["classifications"],
                        retention_schedule=draft["retention_schedule"])


def _do_accept(request, state, policies_dir, staging):
    draft = _load_draft(staging)
    if draft is None:
        return _render_body(request, mode="upload")
    bundle_dir = scaffold_retention_bundle(
        policies_dir,
        title=draft["title"],
        owner=draft["owner"],
        narrative=_NARRATIVE_STUB,
        data_yaml_text=draft["data_yaml"],
        source_pdf=staging / "source.pdf" if (staging / "source.pdf").is_file() else None,
    )
    config = load_working_copy_config()
    author_name, author_email = get_git_author(request.user)
    config_yaml_text = build_config_yaml(state.all_data())
    try:
        pr = finalize_onboarding(
            working_dir=config.working_dir,
            config_yaml_text=config_yaml_text,
            bundle_dir=bundle_dir,
            provider=GitHubProvider(),
            author_name=author_name,
            author_email=author_email,
            base_branch=config.branch,
            username=request.user.get_username(),
        )
    except (RuntimeError, ValueError) as exc:
        logger.error("APP-16 onboarding finalize failed: %s", exc)
        messages.error(
            request,
            "Couldn't publish your configuration to the policy repository. "
            "Your choices are saved locally; ask your administrator to retry.",
        )
        return _render_body(request, mode="review",
                            classifications=draft.get("classifications", []),
                            retention_schedule=draft.get("retention_schedule", []))
    shutil.rmtree(staging.parent, ignore_errors=True)
    state.mark_complete(STEP_SLUG)
    messages.success(
        request,
        f"Onboarding complete. Configuration pull request opened: {pr.get('url', '')}",
    )
    return _hx_redirect("/catalog/")
```

The non-HTMX `handle()` stays in place as the GET entry point and full-page fallback; refactor its `extract`/`accept` branches to call these same helpers so the two paths never drift.

> **Verify the `wizard` API before writing `screen7_fragment`:** the existing `handle()` is called with `(request, target, state)` already built by the generic `onboarding_step` view — it does not call `wizard.step_for`/`wizard.load_state` itself. Read `app/onboarding/urls.py` + the `onboarding_step` view to see how `target` and `state` are constructed, and build them the same way inside `screen7_fragment` (which is reached directly via `/htmx/`, so it must construct them). Use the real helper names (`wizard.index_of`, `wizard.STEPS`, `wizard.prev_step`, `wizard.is_last`, plus whatever loads wizard state). For `back`, use `reverse("onboarding_step", kwargs={"step": prev.slug})` rather than a hardcoded path.

- [ ] **Step 4: Create `app/onboarding/htmx_urls.py`**

```python
"""APP-28c: onboarding HTMX fragment routes, mounted under /htmx/onboarding/.
No app_name: names fold into the parent `htmx` namespace (reverse as
`htmx:onboarding_screen7`)."""
from django.urls import path

from app.onboarding import retention_policy

urlpatterns = [
    path("screen7/", retention_policy.screen7_fragment, name="onboarding_screen7"),
]
```

- [ ] **Step 5: Wire it into `core/htmx_urls.py`**

```python
from django.urls import include, path
from core import views as core_views

app_name = "htmx"

urlpatterns = [
    path("onboarding/", include("app.onboarding.htmx_urls")),
    path("foundational/<slug:slug>/row/", core_views.foundational_row, name="foundational_row"),
]
```

- [ ] **Step 6: Recompile CSS (new utility classes), run suite, commit** (message `feat(app-28c): onboarding screen-7 HTMX fragment dispatch`).

### Task C2: Screen-7 view tests

**Files:**
- Create: `app/onboarding/tests/test_screen7_htmx.py` (mirror the existing test dir layout; read an existing onboarding test first for the fixture/auth helper pattern).

- [ ] **Step 1: Write tests** covering: extract success returns a `#screen7-body` review fragment; the APP-30 empty-PDF guard returns an upload fragment with the scan message AND the AI is never called (preserve the existing spy test through the fragment path); accept returns 204 + `HX-Redirect: /catalog/`; back/save_exit return `HX-Redirect`. Reuse the existing tests' mocking of `ClaudeProvider`/`extract_retention_bundle` and the staging dir. Show the AI-never-called assertion explicitly:

```python
def test_empty_pdf_guard_returns_upload_fragment_and_never_calls_ai(client, logged_in_user, staging_dir, monkeypatch):
    called = {"ai": False}
    def _boom(*a, **k):
        called["ai"] = True
        raise AssertionError("AI must not be called on an empty PDF")
    monkeypatch.setattr("app.onboarding.retention_policy.extract_retention_bundle", _boom)
    # ... POST action=extract with an image-only/empty-text PDF fixture ...
    resp = client.post("/htmx/onboarding/screen7/", {"action": "extract", "pdf_file": empty_pdf})
    assert resp.status_code == 200
    assert b"screen7-body" in resp.content
    assert b"scanned PDF" in resp.content
    assert called["ai"] is False
```

- [ ] **Step 2: Run** `ai/venv/bin/python -m pytest app/onboarding/tests/test_screen7_htmx.py -v` → all pass.

- [ ] **Step 3: Browser-verify** the live flow at 1280x720: upload a text PDF, watch the spinner show during extraction, see the review fragment swap in, click Accept, land on the catalog. Commit (message `test(app-28c): screen-7 HTMX fragment view tests`).

### Task C3: Foundational typed-table row-add

**Files:**
- Modify: `core/views.py` (replace the `foundational_row` stub from Task B3)
- Create: `core/templates/fragments/classification_row.html`, `core/templates/fragments/retention_row.html`
- Modify: `core/tests/test_htmx_urls.py`
- Create: `core/tests/test_foundational_row.py`

- [ ] **Step 1: Write the failing test** `core/tests/test_foundational_row.py`:

```python
import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_foundational_row_classification_returns_indexed_tr(client, django_user_model):
    user = django_user_model.objects.create_user("u", password="p")
    client.force_login(user)
    url = reverse("htmx:foundational_row", kwargs={"slug": "document-retention"})
    resp = client.post(url, {"formset": "cls", "index": "3"})
    assert resp.status_code == 200
    body = resp.content.decode()
    assert 'name="cls-3-id"' in body
    assert 'name="cls-3-name"' in body
    # OOB bump of the management form to the next total.
    assert 'name="cls-TOTAL_FORMS"' in body
    assert 'hx-swap-oob="true"' in body
    assert 'value="4"' in body


def test_foundational_row_retention_returns_indexed_tr(client, django_user_model):
    user = django_user_model.objects.create_user("u", password="p")
    client.force_login(user)
    url = reverse("htmx:foundational_row", kwargs={"slug": "document-retention"})
    resp = client.post(url, {"formset": "ret", "index": "0"})
    assert resp.status_code == 200
    body = resp.content.decode()
    assert 'name="ret-0-group"' in body
    assert 'name="ret-0-type"' in body
    assert 'name="ret-TOTAL_FORMS"' in body
```

- [ ] **Step 2: Run to confirm it fails** — `ai/venv/bin/python -m pytest core/tests/test_foundational_row.py -v` → FAIL (stub raises Http404).

- [ ] **Step 3: Replace the `foundational_row` stub in `core/views.py`** (imports `ClassificationForm`, `RetentionRowForm` from `core.forms`):

```python
@login_required
@require_POST
def foundational_row(request, slug):
    """APP-28c: return one fresh typed-table row plus an out-of-band bump of
    the formset's TOTAL_FORMS, so HTMX can append a row without a reload and
    the Django formset accepts it on POST. `slug` scopes the request to a
    bundle but the row markup is bundle-independent."""
    which = request.POST.get("formset")
    try:
        index = int(request.POST.get("index", "0"))
    except (TypeError, ValueError):
        index = 0
    if which == "ret":
        form = RetentionRowForm(prefix=f"ret-{index}")
        template = "fragments/retention_row.html"
        prefix = "ret"
    else:
        form = ClassificationForm(prefix=f"cls-{index}")
        template = "fragments/classification_row.html"
        prefix = "cls"
    return render(request, template, {
        "form": form, "prefix": prefix, "index": index, "next_total": index + 1,
    })
```

Add the import near the top of `core/views.py` (it already imports the formsets and meta form):

```python
from core.forms import ClassificationForm, RetentionRowForm
```

- [ ] **Step 4: Create the row fragments**

`core/templates/fragments/classification_row.html`:

```html
<tr class="hover:bg-slate-50">
  <td>{{ form.id }}</td>
  <td>{{ form.name }}</td>
  <td><label class="text-xs text-slate-500"><input type="checkbox" name="{{ prefix }}-{{ index }}-DELETE"> remove</label></td>
</tr>
<input type="hidden" id="id_{{ prefix }}-TOTAL_FORMS" name="{{ prefix }}-TOTAL_FORMS" value="{{ next_total }}" hx-swap-oob="true">
```

`core/templates/fragments/retention_row.html`:

```html
<tr class="hover:bg-slate-50">
  <td>{{ form.group }}</td>
  <td>{{ form.sub_group }}</td>
  <td>{{ form.type }}</td>
  <td>{{ form.retention }}</td>
  <td>{{ form.medium }}</td>
  <td>{{ form.retained_at }}</td>
  <td><label class="text-xs text-slate-500"><input type="checkbox" name="{{ prefix }}-{{ index }}-DELETE"> remove</label></td>
</tr>
<input type="hidden" id="id_{{ prefix }}-TOTAL_FORMS" name="{{ prefix }}-TOTAL_FORMS" value="{{ next_total }}" hx-swap-oob="true">
```

The trailing `<input ... hx-swap-oob="true">` is a top-level sibling of the `<tr>`: HTMX pulls it out of the response and swaps it by id (updating the management form's TOTAL_FORMS) before appending the `<tr>` into `#cls-rows`/`#ret-rows`.

- [ ] **Step 5: Run to confirm pass** — `ai/venv/bin/python -m pytest core/tests/test_foundational_row.py -v` → PASS.

- [ ] **Step 6: Update `core/tests/test_htmx_urls.py`**

Replace the now-false "empty urlpatterns" assertion with reverse checks for the real endpoints:

```python
"""APP-28c: the /htmx/ tree now carries the first fragment endpoints."""
from django.urls import reverse

from core import urls as core_urls


def test_core_urls_includes_the_htmx_prefix():
    prefixes = [str(p.pattern) for p in core_urls.urlpatterns]
    assert "htmx/" in prefixes


def test_htmx_endpoints_reverse_under_the_namespace():
    assert reverse("htmx:foundational_row", kwargs={"slug": "x"}) == "/htmx/foundational/x/row/"
    assert reverse("htmx:onboarding_screen7") == "/htmx/onboarding/screen7/"
```

- [ ] **Step 7: Run the full suite** — `ai/venv/bin/python -m pytest -q` → green.

- [ ] **Step 8: Browser-verify** the foundational editor at 1280x720: click "+ Add classification" and "+ Add retention rule", confirm a blank row appends without reload, fill it in, submit, and confirm the formset accepts the new row (PR opens / no validation error on the management form). Recompile CSS if any new utility classes were introduced, then commit (message `feat(app-28c): HTMX row-add for the foundational typed table`).

---

## PART (d) — REPO-10 harness + docs

### Task D1: Assert the stylesheet ships; document the build step

**Files:**
- Create: `tests/test_static_assets_ship.py`
- Modify: `tests/test_generic_ship.py`
- Modify: `install.sh` (dev-notes comment) and/or `README.md`

- [ ] **Step 1: Write `tests/test_static_assets_ship.py`**

The clean-VM guarantee is that the compiled CSS is committed and discoverable by `collectstatic`'s finders (which is exactly what runs at Docker build). Assert discoverability + the served sentinel rather than spinning a server.

```python
"""REPO-10 / APP-28d: the compiled CSS and HTMX ship and are collectible."""
import pytest
from django.contrib.staticfiles import finders

pytestmark = pytest.mark.django_db


def test_policycodex_css_is_collectible():
    assert finders.find("css/policycodex.css") is not None
    assert finders.find("js/htmx.min.js") is not None


def test_served_css_carries_brand_and_component_sentinels():
    path = finders.find("css/policycodex.css")
    text = open(path, encoding="utf-8").read()
    assert "4a5f8a" in text.lower() or "74 95 138" in text  # brand color survived
    assert ".btn" in text  # DaisyUI component survived (update if fallback taken)
```

- [ ] **Step 2: Run** — `ai/venv/bin/python -m pytest tests/test_static_assets_ship.py -v` → PASS.

- [ ] **Step 3: Extend the generic-ship scan to cover `static/`**

In `tests/test_generic_ship.py`, add `"static"` to `_SHIPPING_ROOTS` so the committed CSS/JS/SVG are checked for diocese-name leakage (the compiled CSS is generic Tailwind output, so this passes; it guards a future hand-edit). Update line 23:

```python
_SHIPPING_ROOTS = ("app", "core", "ai", "ingest", "policycodex_site", "repo-template", "static")
```

The `.woff2` fonts have no scanned suffix, so they're skipped; `.css`/`.js`/`.svg`/`.html` under `static/` are scanned. Run `ai/venv/bin/python -m pytest tests/test_generic_ship.py -v` → PASS (if it flags anything, the leak is real — fix the asset, don't loosen the test).

- [ ] **Step 4: Document `build-css.sh` as the regeneration step**

Add a short dev note. In `install.sh`, near the top comment block, add a line:

```
# CSS is pre-compiled and committed (static/css/policycodex.css). To regenerate
# after editing templates or theme vars, run: scripts/build-css.sh
```

And add a "Rebuilding the CSS" subsection to `README.md` under the existing developer/build notes (one paragraph: run `scripts/build-css.sh`; the toolchain auto-downloads into the gitignored `.tools/`; commit the regenerated `static/css/policycodex.css`).

- [ ] **Step 5: Run the full suite and commit**

Run: `ai/venv/bin/python -m pytest -q`
Expected: all green (plus the CSS drift guard skipped unless `POLICYCODEX_BUILD_CSS=1`).

```bash
git add tests/test_static_assets_ship.py tests/test_generic_ship.py install.sh README.md
git commit -m "$(cat <<'EOF'
feat(app-28d): assert compiled CSS ships; document build-css.sh

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Final verification

- [ ] **Full suite green:** `ai/venv/bin/python -m pytest -q`
- [ ] **Drift guard green with toolchain:** `POLICYCODEX_BUILD_CSS=1 ai/venv/bin/python -m pytest tests/test_css_build.py -q`
- [ ] **Docker build still works** (the install path is unchanged, but confirm collectstatic picks up the new dir): `docker build --no-cache -t policycodex-app28 .` (on a machine with a docker daemon / Colima) → image builds, `collectstatic` reports the css/js/fonts collected.
- [ ] **Browser sweep at 1280x720** of every retemplated page + both HTMX interactions.

---

## Out of scope (do not build)

- OCR for scanned PDFs (INGEST-08, post-freeze).
- The wizard completion screen (APP-29; ships in this same vocabulary later).
- Wizard-managed handbook publishing / automatic CNAME (v0.2, PRD P2.7).
- Commercial component libraries (off the table while AGPL).
