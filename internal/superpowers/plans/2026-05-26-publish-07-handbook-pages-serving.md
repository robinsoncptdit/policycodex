# PUBLISH-07 Implementation Plan: Serve the Handbook at a Custom Subdomain via GitHub Pages

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the Pages artifact uploaded by PUBLISH-06 to actually serve at a public custom subdomain (`handbook.<diocese>.org`), with HTTPS, with zero per-diocese source-code config, and gracefully skipping the deploy step for dioceses who have not yet enabled Pages.

**Architecture:** Extend `repo-template/.github/workflows/build-handbook.yml` from one job (build + upload) to three jobs (preflight + build + deploy). The preflight job calls the GitHub Pages API for the repo to learn the configured custom-domain URL and whether Pages is configured at all. The build job consumes that URL via an `ASTRO_SITE_URL` env var; `handbook/astro.config.mjs` reads it with a placeholder fallback. The deploy job uses `actions/deploy-pages@v5`, conditioned on preflight reporting `pages_configured=true` (otherwise the deploy job is skipped gracefully, not failed). Plus a new HOWTO Part 4 and an updated PUBLISH-07 ticket entry. The live install on `pt-policy` runs after merge as a controller activity, not an implementer step.

**Tech Stack:** GitHub Actions, gh CLI in workflow steps, Astro ^5 (Node 20+), Python 3.14 + PyYAML for structural tests, bash.

**Design doc:** `internal/superpowers/specs/2026-05-26-publish-07-handbook-pages-serving-design.md` (committed `4f60f96`)

---

## Scope notes (read before starting)

- Decisions locked in the design doc: (1) GitHub Pages with custom domain is the v0.1 serving target (Caddy/Nginx are out of scope for v0.1, the ticket text from before this decision will be updated in Task 1); (2) preflight gate makes the deploy job skipped (gray) rather than failed (red) on repos that have not yet enabled Pages, so install-N's first merges go green; (3) site URL flows from the Pages API at build time so there is no per-diocese source config; (4) `cancel-in-progress` flips from `true` to `false` because cancelling a Pages deploy mid-flight can corrupt the live site.
- `actions/deploy-pages@v5` was the latest tag as of design (2026-05-26, verified via `gh api repos/actions/deploy-pages/releases/latest`). Task 4's first step re-verifies; if a v6 ships between design and implementation, stop and check with the controller.
- The `astro.config.mjs` change must land in BOTH `handbook/astro.config.mjs` (the upstream Astro source) AND `repo-template/handbook/astro.config.mjs` (the vendored copy). `repo-template/sync-handbook.sh` copies the upstream file over the vendored one, so editing only the vendored copy gets silently reverted on the next re-vendor. The plan covers both via the sync script. A new byte-equality test guards this going forward.
- HOWTO insertion point matters: `HOWTO-GitHub-Team-Setup.md` has Parts 1, 2, 3 followed by closing sections (`Verify it works`, `Your values`, `Why this matters`) starting at line 95. Part 4 must be inserted BEFORE `Verify it works`, NOT appended at end-of-file. The HOWTO style for each Part is one `##` heading, a short intro paragraph, a flat numbered list of steps, optional follow-up paragraphs. Do not introduce H3 sub-headings inside Part 4; match Parts 1-3 voice and structure.
- Test interpreter, inside a worktree: `/Users/chuck/PolicyWonk/ai/venv/bin/python` (absolute path from the parent; the `ai/venv` directory is gitignored, so it does not exist inside the worktree). Outside a worktree (controller running in the parent): `ai/venv/bin/python` works fine. All commands in this plan use the absolute parent path so they work in either location.
- Current main test baseline: 373 (end of Week 4 Wave 2 per `internal/PolicyWonk-Week-4-Demo.md`). This plan adds 6 new tests (Task 3) and modifies 2 existing tests (Task 3). End-state expectation: 379 passing.
- The implementer's plan ends at Task 6 (self-report to controller). The live install on `pt-policy` (DNS, org domain verify, Pages settings, PR with the new workflow, admin-bypass-and-restore, smoke, day-2 Enforce-HTTPS) is a controller + Chuck activity captured in the "Post-merge live install" appendix below. It is not a subagent task.
- The `pt-policy` admin-bypass-and-restore pattern is established (PUBLISH-06 PR #2, REPO-09 install, Node-24 PR #4). Chuck explicitly authorizes each bypass at the moment of merge; the controller captures the pre-bypass ruleset state via API and verifies post-restore byte-equality (modulo the `updated_at` field). Do not bake bypass-actor JSON into this plan.

## File Structure

- Modify: `PolicyWonk-v0.1-Tickets.md` (one row, PUBLISH-07's entry) - update stale "Caddy or Nginx" text to reflect the GitHub Pages decision.
- Modify: `handbook/astro.config.mjs` - read `ASTRO_SITE_URL` env var with placeholder fallback.
- Modify: `repo-template/handbook/astro.config.mjs` - same content, via `sync-handbook.sh`.
- Modify: `repo-template/tests/test_build_handbook.py` - update 2 existing tests; add 6 new tests.
- Modify: `repo-template/.github/workflows/build-handbook.yml` - rewrite to 3 jobs (preflight + build + deploy).
- Modify: `HOWTO-GitHub-Team-Setup.md` - insert Part 4 BEFORE the `## Verify it works` section.

No new files.

---

### Task 1: Update the stale PUBLISH-07 ticket entry

The PUBLISH-07 row in `PolicyWonk-v0.1-Tickets.md` predates the design decision and still says "Caddy or Nginx reverse-proxy config (or GitHub Pages alternative)." Refresh it so the ticket text matches the decision and points at the design doc, similar to how APP-22's parenthetical method-list was corrected in its plan.

**Files:**
- Modify: `PolicyWonk-v0.1-Tickets.md` (one row)

- [ ] **Step 1: Locate and replace the PUBLISH-07 row**

In `PolicyWonk-v0.1-Tickets.md`, find the row:

```
| PUBLISH-07 | Subdomain deployment doc and Caddy or Nginx reverse-proxy config (or GitHub Pages alternative) | M | 4 | None |
```

Replace it with:

```
| PUBLISH-07 | Serve the handbook at a public custom subdomain via GitHub Pages (DNS CNAME + org-level apex verification + Pages settings + three-job workflow with preflight gate + Astro site URL from Pages API + HOWTO Part 4 + live install on `pt-policy` at `handbook.ptdiocese.org`). Design: `internal/superpowers/specs/2026-05-26-publish-07-handbook-pages-serving-design.md`. | M | 4 | PUBLISH-06 |
```

(Estimate stays `M`, week stays `4`, dependency changes from `None` to `PUBLISH-06` since the deploy extends PUBLISH-06's artifact.)

- [ ] **Step 2: Commit**

```bash
git add PolicyWonk-v0.1-Tickets.md
git commit -m "docs(PUBLISH-07): refresh ticket entry to match GitHub Pages decision + design doc"
```

---

### Task 2: Wire `astro.config.mjs` to read `ASTRO_SITE_URL` (both copies in lockstep)

**Files:**
- Modify: `handbook/astro.config.mjs`
- Modify: `repo-template/handbook/astro.config.mjs` (via `sync-handbook.sh`)

- [ ] **Step 1: Replace `handbook/astro.config.mjs` (the upstream source) with the env-var version**

Write `handbook/astro.config.mjs`:

```js
// @ts-check
import { defineConfig } from 'astro/config';

export default defineConfig({
  // Set automatically by .github/workflows/build-handbook.yml from your
  // repo's Pages config. The literal fallback below only applies for local
  // builds without Pages enabled.
  site: process.env.ASTRO_SITE_URL || 'https://handbook.example.org',
});
```

- [ ] **Step 2: Re-vendor with `sync-handbook.sh`**

From repo root (or worktree root):

Run: `bash repo-template/sync-handbook.sh`
Expected: prints `Vendored handbook -> .../repo-template/handbook`. No errors.

- [ ] **Step 3: Verify both files match byte-for-byte**

Run: `diff handbook/astro.config.mjs repo-template/handbook/astro.config.mjs`
Expected: no output (files identical).

- [ ] **Step 4: Verify a local Astro build still succeeds with the placeholder**

Run: `cd handbook && npm ci && npm run build && cd ..`
Expected: build completes. The placeholder `https://handbook.example.org` is what canonical URLs in `handbook/dist/` will reference (this is the no-Pages local fallback path; Pages-enabled deploys overwrite via the workflow env).

- [ ] **Step 5: Commit**

```bash
git add handbook/astro.config.mjs repo-template/handbook/astro.config.mjs
git commit -m "feat(PUBLISH-07): astro site URL reads ASTRO_SITE_URL env var with placeholder fallback"
```

---

### Task 3: Template tests for the new workflow shape (TDD red)

Write the structural tests that describe the new workflow + the byte-equality invariant. Two existing tests get their assertions flipped (concurrency value, `actions/deploy-pages` presence); six new tests get appended. All run RED against the current PUBLISH-06 workflow; Task 4 implements them green.

**Files:**
- Modify: `repo-template/tests/test_build_handbook.py`

- [ ] **Step 1: Add the `HANDBOOK_UPSTREAM` path constant near the top of the file**

Open `repo-template/tests/test_build_handbook.py`. After the existing line `WORKFLOW = REPO_TEMPLATE / ".github" / "workflows" / "build-handbook.yml"`, add:

```python
HANDBOOK_UPSTREAM = REPO_TEMPLATE.parent / "handbook"
```

- [ ] **Step 2: Flip `test_workflow_serializes_builds_with_concurrency` to assert `cancel-in-progress: False`**

Replace the existing function body with:

```python
def test_workflow_serializes_builds_with_concurrency():
    wf = yaml.safe_load(WORKFLOW.read_text())
    concurrency = wf["concurrency"]
    assert concurrency["group"]
    # PUBLISH-07: Pages deploys should NOT be cancelled mid-flight; GitHub's
    # own guidance is cancel-in-progress: false for Pages, since cancelling
    # mid-deploy can corrupt the live site.
    assert concurrency["cancel-in-progress"] is False
```

- [ ] **Step 3: Update `test_workflow_has_build_and_upload_steps` to require `deploy-pages` PRESENT**

Replace the existing function body with:

```python
def test_workflow_has_build_and_upload_steps():
    text = WORKFLOW.read_text()
    # staging copy, install, build, verify, artifact upload (build job)
    assert "cp -r policies/" in text
    assert "npm ci" in text
    assert "npm run build" in text
    assert "npm run verify" in text
    assert "actions/upload-pages-artifact" in text
    # PUBLISH-07: deploy job uses actions/deploy-pages
    assert "actions/deploy-pages@v5" in text
```

- [ ] **Step 4: Append `test_workflow_has_three_jobs_in_order`**

```python
def test_workflow_has_three_jobs_in_order():
    wf = yaml.safe_load(WORKFLOW.read_text())
    jobs = list(wf["jobs"].keys())
    assert jobs == ["preflight", "build", "deploy"], jobs
```

- [ ] **Step 5: Append `test_preflight_job_queries_pages_api_and_declares_outputs`**

```python
def test_preflight_job_queries_pages_api_and_declares_outputs():
    wf = yaml.safe_load(WORKFLOW.read_text())
    preflight = wf["jobs"]["preflight"]
    assert preflight["runs-on"] == "ubuntu-latest"
    assert preflight["permissions"] == {"contents": "read"}
    outputs = preflight["outputs"]
    assert "pages_configured" in outputs
    assert "site_url" in outputs
    # The check step must call the Pages API via gh.
    step_run = "\n".join(s.get("run", "") for s in preflight["steps"])
    assert "gh api" in step_run
    assert "repos/${{ github.repository }}/pages" in step_run
```

- [ ] **Step 6: Append `test_build_job_needs_preflight_and_passes_site_url_env`**

```python
def test_build_job_needs_preflight_and_passes_site_url_env():
    wf = yaml.safe_load(WORKFLOW.read_text())
    build = wf["jobs"]["build"]
    assert build["needs"] == "preflight"
    # The "Build the handbook" step must receive ASTRO_SITE_URL from preflight.
    build_step = next(s for s in build["steps"] if s.get("name") == "Build the handbook")
    assert build_step["env"]["ASTRO_SITE_URL"] == "${{ needs.preflight.outputs.site_url }}"
```

- [ ] **Step 7: Append `test_deploy_job_uses_deploy_pages_and_is_gated_on_preflight`**

```python
def test_deploy_job_uses_deploy_pages_and_is_gated_on_preflight():
    wf = yaml.safe_load(WORKFLOW.read_text())
    deploy = wf["jobs"]["deploy"]
    # Must depend on both build (for artifact) and preflight (for the gate).
    assert deploy["needs"] == ["build", "preflight"]
    assert deploy["if"] == "needs.preflight.outputs.pages_configured == 'true'"
    env = deploy["environment"]
    assert env["name"] == "github-pages"
    assert env["url"] == "${{ steps.deployment.outputs.page_url }}"
    # Single deploy step pinned to v5.
    step = next(s for s in deploy["steps"] if s.get("uses", "").startswith("actions/deploy-pages"))
    assert step["uses"] == "actions/deploy-pages@v5"
    assert step["id"] == "deployment"
```

- [ ] **Step 8: Append `test_upstream_and_vendored_astro_config_are_byte_equal`**

```python
def test_upstream_and_vendored_astro_config_are_byte_equal():
    # sync-handbook.sh copies upstream handbook/astro.config.mjs over the
    # vendored copy. If they diverge, the next re-vendor silently reverts
    # the env-var reading change. Assert byte-equality to catch that.
    upstream = (HANDBOOK_UPSTREAM / "astro.config.mjs").read_bytes()
    vendored = (HANDBOOK / "astro.config.mjs").read_bytes()
    assert upstream == vendored
```

- [ ] **Step 9: Append `test_vendored_astro_config_reads_site_url_env_var`**

```python
def test_vendored_astro_config_reads_site_url_env_var():
    text = (HANDBOOK / "astro.config.mjs").read_text()
    assert "process.env.ASTRO_SITE_URL" in text
    # Placeholder fallback for local builds without Pages.
    assert "'https://handbook.example.org'" in text
```

- [ ] **Step 10: Run the tests to verify red**

Run: `/Users/chuck/PolicyWonk/ai/venv/bin/python -m pytest repo-template/tests/test_build_handbook.py -v`
Expected against the current PUBLISH-06 workflow:
- `test_workflow_serializes_builds_with_concurrency` FAILS (current is `True`)
- `test_workflow_has_build_and_upload_steps` FAILS (current lacks `actions/deploy-pages@v5`)
- `test_workflow_has_three_jobs_in_order` FAILS (current has one job, `build`)
- `test_preflight_job_queries_pages_api_and_declares_outputs` FAILS (no preflight)
- `test_build_job_needs_preflight_and_passes_site_url_env` FAILS (build has no `needs`)
- `test_deploy_job_uses_deploy_pages_and_is_gated_on_preflight` FAILS (no deploy job)
- `test_upstream_and_vendored_astro_config_are_byte_equal` PASSES (Task 2 ensured this)
- `test_vendored_astro_config_reads_site_url_env_var` PASSES (Task 2 ensured this)

- [ ] **Step 11: Commit the red tests**

```bash
git add repo-template/tests/test_build_handbook.py
git commit -m "test(PUBLISH-07): three-job workflow tests + astro byte-equality guard (red)"
```

---

### Task 4: Rewrite the workflow to three jobs (TDD green)

**Files:**
- Modify: `repo-template/.github/workflows/build-handbook.yml`

- [ ] **Step 1: Re-verify `actions/deploy-pages@v5` is still the latest tag**

Run: `gh api repos/actions/deploy-pages/releases/latest --jq '.tag_name'`
Expected: `v5.0.0` (as of design 2026-05-26).

If anything other than `v5.0.0`, STOP and check in with the controller. The spec may need updating for a v6 bump.

- [ ] **Step 2: Replace `repo-template/.github/workflows/build-handbook.yml` with the three-job version**

Write `repo-template/.github/workflows/build-handbook.yml`:

```yaml
name: Build handbook

on:
  push:
    branches: [main]
    paths:
      - 'policies/**'
      - 'handbook/**'

permissions:
  contents: read
  pages: write
  id-token: write

# Pages handles its own queue; cancelling mid-deploy can corrupt the live
# site. Stay serialized, but do NOT cancel-in-progress (GitHub's own
# recommendation for the Pages flow).
concurrency:
  group: handbook-pages
  cancel-in-progress: false

jobs:
  preflight:
    runs-on: ubuntu-latest
    permissions:
      contents: read
    outputs:
      pages_configured: ${{ steps.check.outputs.pages_configured }}
      site_url: ${{ steps.check.outputs.site_url }}
    steps:
      - name: Check Pages configuration
        id: check
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          set +e
          response=$(gh api "repos/${{ github.repository }}/pages" 2>/dev/null)
          rc=$?
          set -e
          if [ "$rc" -ne 0 ]; then
            echo "pages_configured=false" >> "$GITHUB_OUTPUT"
            echo "site_url=" >> "$GITHUB_OUTPUT"
            exit 0
          fi
          cname=$(echo "$response" | jq -r '.cname // empty')
          if [ -n "$cname" ]; then
            site_url="https://$cname"
          else
            site_url=$(echo "$response" | jq -r '.html_url')
          fi
          echo "pages_configured=true" >> "$GITHUB_OUTPUT"
          echo "site_url=$site_url" >> "$GITHUB_OUTPUT"

  build:
    needs: preflight
    runs-on: ubuntu-latest
    steps:
      - name: Check out the policy repo
        uses: actions/checkout@v6
      - name: Set up Node
        uses: actions/setup-node@v6
        with:
          node-version: '20'
          cache: npm
          cache-dependency-path: handbook/package-lock.json
      - name: Stage policies into the handbook content dir
        run: |
          rm -rf handbook/src/content/policies/*
          # `policies/.` copies the directory contents without relying on
          # glob expansion, so an empty or dotfile-only policies/ does not
          # error the step (the build then fails clearly at verify instead).
          cp -r policies/. handbook/src/content/policies/
      - name: Install dependencies
        working-directory: handbook
        run: npm ci
      - name: Build the handbook
        working-directory: handbook
        run: npm run build
        env:
          ASTRO_SITE_URL: ${{ needs.preflight.outputs.site_url }}
      - name: Verify the build output
        working-directory: handbook
        run: npm run verify
      - name: Upload the Pages artifact
        uses: actions/upload-pages-artifact@v5
        with:
          path: handbook/dist

  deploy:
    needs: [build, preflight]
    if: needs.preflight.outputs.pages_configured == 'true'
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - name: Deploy to GitHub Pages
        id: deployment
        uses: actions/deploy-pages@v5
```

- [ ] **Step 3: Run the template tests and confirm all green**

Run: `/Users/chuck/PolicyWonk/ai/venv/bin/python -m pytest repo-template/tests/test_build_handbook.py -v`
Expected: every test in the file passes (5 existing + 6 new = 11 tests).

- [ ] **Step 4: Commit**

```bash
git add repo-template/.github/workflows/build-handbook.yml
git commit -m "feat(PUBLISH-07): three-job workflow (preflight + build + deploy) with graceful Pages skip"
```

---

### Task 5: Insert HOWTO Part 4 before the closing sections

`HOWTO-GitHub-Team-Setup.md` has Parts 1, 2, 3 followed by closing sections (`Verify it works`, `Your values`, `Why this matters`) starting at line 95 (verify exact line in your editor; the file may have grown). Part 4 inserts BEFORE `## Verify it works`. Match the Parts 1-3 voice: one `##` heading, a short intro paragraph, a flat numbered list of steps. No H3 sub-headings inside the Part. No em dashes. Active voice, second person.

**Files:**
- Modify: `HOWTO-GitHub-Team-Setup.md`

- [ ] **Step 1: Locate the insertion point**

Run: `grep -n '^## Verify it works' HOWTO-GitHub-Team-Setup.md`
Expected: one line number returned (e.g., `95:## Verify it works`). Note this line number; Part 4 inserts immediately before it (i.e., before the blank line that precedes `## Verify it works`).

- [ ] **Step 2: Insert the Part 4 section before `## Verify it works`**

Add the following block (note: it ends with a blank line, then `## Verify it works` resumes the existing file):

```markdown
## Part 4: Publish the handbook at a public custom subdomain

PolicyCodex builds your handbook on every merge to `main` (the build runs from `.github/workflows/build-handbook.yml`, vendored from the repo template). Once you complete this part, every merge also publishes the handbook to a public subdomain you control, served by GitHub Pages with HTTPS via Let's Encrypt. Cost is zero on the Team plan or higher.

Pages publishing from a private repo requires the Team plan or higher. Access-restricted ("private") Pages requires Enterprise Cloud and is out of scope for v0.1.

You need DNS control of the parent zone of your chosen subdomain. For example, to publish at `handbook.example.org`, you must be able to add CNAME and TXT records under `example.org`.

1. **Verify your apex domain at the org level (one-time, recommended).** This locks every subdomain at your apex (`*.example.org`) to your GitHub org, so no one else can stand up a `*.example.org` Pages site on a different account. On GitHub, open your org's **Settings**, then **Pages**, then **Add a domain**, and enter your apex (`example.org`, not `handbook.example.org`). GitHub shows you a TXT record. Add it to your DNS at the name `_github-pages-challenge-<your-org>.example.org` with the value GitHub provides. Verify propagation with `dig +short TXT _github-pages-challenge-<your-org>.example.org`. Back in GitHub, click **Verify**. Leave the TXT record in place; removing it un-verifies the apex.

2. **Create the subdomain CNAME.** In your DNS provider, add a CNAME record: name `handbook` (resolving to `handbook.example.org`), value `<your-org>.github.io` (your GitHub org name only, no repo name). Wait for DNS to propagate (a few minutes to a few hours). Verify with `dig +short CNAME handbook.example.org`; it should return `<your-org>.github.io.`.

3. **Enable Pages on the policy repo.** Open your policy repo's **Settings**, then **Pages**. Under **Build and deployment**, set **Source** to **GitHub Actions** (not "Deploy from a branch"). Under **Custom domain**, enter `handbook.example.org` and **Save**. GitHub runs a DNS check; wait for the green check (usually under a minute, once Step 2 has propagated). Do NOT commit a `CNAME` file to your repo; with the Actions source, the custom domain lives in Settings only.

4. **Trigger a deploy.** Push any commit to `main` (or re-run the latest **Build handbook** workflow from the Actions tab). The workflow now has three jobs: `preflight` checks the Pages configuration, `build` builds the handbook with your custom domain set as the canonical site URL, and `deploy` publishes to Pages. All three should go green. The `deploy` job summary shows the live URL. Visit it and confirm the handbook loads.

5. **Enforce HTTPS.** After Let's Encrypt provisions a certificate for your subdomain (this can take up to 24 hours from when DNS first resolved correctly), GitHub makes an **Enforce HTTPS** checkbox available in **Settings**, **Pages**. Enable it. From that point, plain-HTTP requests automatically redirect to HTTPS.

If the `deploy` job is gray rather than green, Pages is not yet enabled on the repo; complete Step 3. If the `deploy` job is red, open its log; the most common causes are a mismatch between the CNAME target and your GitHub org name (the target uses the org name only, not the repo path), or DNS that has not yet propagated. If the **Enforce HTTPS** checkbox is missing, Let's Encrypt has not provisioned yet; come back later. If you accidentally remove the `_github-pages-challenge-<your-org>` TXT record, re-add it from your org's Settings, Pages page; the apex stays verified for a grace period.

```

- [ ] **Step 3: Verify the file is well-formed**

Run: `grep -c '^## Part' HOWTO-GitHub-Team-Setup.md`
Expected: `4` (Parts 1, 2, 3, 4).

Run: `grep -n '^## Verify it works' HOWTO-GitHub-Team-Setup.md`
Expected: one line number, somewhere after Part 4.

Run: `grep -n '—' HOWTO-GitHub-Team-Setup.md || echo "no em dashes"`
Expected: `no em dashes`.

- [ ] **Step 4: Commit**

```bash
git add HOWTO-GitHub-Team-Setup.md
git commit -m "docs(PUBLISH-07): HOWTO Part 4 - publish the handbook at a public custom subdomain"
```

---

### Task 6: Full-suite verification and self-report to controller

**Files:** none (verification only).

- [ ] **Step 1: Run the full Python suite from repo root (or worktree root)**

Run: `/Users/chuck/PolicyWonk/ai/venv/bin/python -m pytest -q`
Expected: `379 passed` (373 baseline + 6 new template tests), zero failures, zero errors.

If the count is off, do not panic; the baseline could have shifted (the controller may have merged additional tests since this plan was written). The shape of the assertion is: existing tests + 6 new = total. Confirm the 6 new tests are among the passing ones.

- [ ] **Step 2: Confirm git status is clean and the expected commits are present**

Run: `git status`
Expected: clean working tree.

Run: `git log --oneline -5`
Expected (newest first, one commit per task except Task 4 commits with Task 3's red on its branch already; result is roughly):
- `docs(PUBLISH-07): HOWTO Part 4 ...`
- `feat(PUBLISH-07): three-job workflow ...`
- `test(PUBLISH-07): three-job workflow tests ...`
- `feat(PUBLISH-07): astro site URL reads ASTRO_SITE_URL ...`
- `docs(PUBLISH-07): refresh ticket entry ...`

- [ ] **Step 3: Self-report DONE to the controller**

Report back with: (a) the five commit SHAs in order; (b) the final test count; (c) any deviations from this plan (note especially if the `deploy-pages@v5` re-verification in Task 4 Step 1 found a v6 release).

Stop here. The live install on `pt-policy` is the controller's job, captured in the appendix below.

---

## Self-Review checklist (run before requesting review)

- Spec coverage:
  - Three-job workflow → Task 4
  - `cancel-in-progress: false` → Task 3 test flip + Task 4 yaml
  - Dynamic Astro site URL → Task 2 (both files) + Task 4 yaml (env passthrough)
  - Byte-equality of upstream + vendored astro config → Task 3 (test) + Task 2 (re-vendor)
  - Pre-flight graceful skip on `gh api ... 404` → Task 4 yaml (`set +e`, exit on non-zero, no `set -e` after) and tested via deploy-job `if` condition
  - `actions/deploy-pages@v5` pin → Task 4 Step 1 re-verify + Task 3 test + Task 4 yaml
  - HOWTO Part 4 with five flat numbered steps + troubleshooting → Task 5
  - Stale PUBLISH-07 ticket text refresh → Task 1
  - Full-suite verification + self-report → Task 6
  - All present.
- No placeholders. Every step has runnable code or commands.
- Type/name consistency: `pages_configured` and `site_url` consistent across preflight outputs, build env, deploy `if`, and tests.
- Em-dash check: Task 5 Step 3 grep guards the HOWTO; the rest of the plan should be em-dash-free by convention.
- YAGNI: no Caddy/Nginx serving, no required-check enforcement of `deploy-pages`, no wizard wiring for the subdomain capture, no Pages-API caching layer.

## Dispatch note

Implementer runs in `isolation: "worktree"`, Sonnet. First action inside the worktree: `git merge main` into the auto-branch (baseline 373 tests). Critical Operational Note: never `cd /Users/chuck/PolicyWonk` for git operations; operate only inside the worktree. The gitignored venv is absent in the worktree: run pytest via `/Users/chuck/PolicyWonk/ai/venv/bin/python` against the worktree directory. `gh` CLI must be authenticated; the implementer can confirm with `gh auth status` and, if needed, ask the controller to re-auth before re-running Task 4 Step 1. Two-stage pre-merge review (spec reviewer then quality reviewer) before the controller fast-forwards into main.

---

## Post-merge live install on `pt-policy` (controller activity, NOT implementer task)

Runs after Tasks 1-6 merge to `PolicyCodex/main` and code review clears. Mix of Chuck-side and controller-side actions. The admin-bypass-and-restore pattern is established (PUBLISH-06 PR #2 install, REPO-09 install, Node-24 PR #4); do not re-specify the JSON inline.

1. **Chuck creates the DNS CNAME.** In the DNS provider for `ptdiocese.org`, add CNAME `handbook` → `diocese-of-pensacola-tallahassee.github.io`. Verify with `dig +short CNAME handbook.ptdiocese.org`; expect `diocese-of-pensacola-tallahassee.github.io.`.

2. **Chuck verifies the apex `ptdiocese.org` at the org level.** In the `Diocese-of-Pensacola-Tallahassee` org's Settings → Pages, add `ptdiocese.org` as a domain. Place the TXT GitHub provides at `_github-pages-challenge-diocese-of-pensacola-tallahassee.ptdiocese.org`. Verify in the GitHub UI. Keep the TXT in place.

3. **Chuck enables Pages on `pt-policy`.** Repo Settings → Pages → Source: GitHub Actions. Custom domain: `handbook.ptdiocese.org`. Save. Wait for the green DNS check.

4. **Controller opens the `pt-policy` PR vendoring the merged workflow + astro config.** Clone or update a local working copy of `pt-policy`. Copy `repo-template/.github/workflows/build-handbook.yml` and `repo-template/handbook/astro.config.mjs` from `PolicyCodex/main` over the corresponding `pt-policy` files. Open a PR titled "PUBLISH-07: serve handbook at handbook.ptdiocese.org".

5. **Chuck authorizes the admin-bypass on ruleset `16256205`; controller captures the pre-state, applies bypass, squash-merges the PR, restores the ruleset to its exact prior state, verifies byte-equality (modulo `updated_at`).** Same procedure as the prior installs (see the 2026-05-24 daily-log entries for PR #2, REPO-09, and PR #4 for the exact `gh api` calls used; do not duplicate them in this plan, since the procedure has stayed identical across all three).

6. **Controller watches the workflow run.** Expected: preflight green emitting `pages_configured=true` and `site_url=https://handbook.ptdiocese.org`; build green with the env var in effect; deploy green with the live URL in the run summary.

7. **Controller runs the smoke checks.**

```bash
curl -fsSL -I https://handbook.ptdiocese.org/
# Expected: HTTP/2 200; valid HTTPS.

curl -fsSL https://handbook.ptdiocese.org/ | grep '<link rel="canonical"'
# Expected: <link rel="canonical" href="https://handbook.ptdiocese.org/...">
# NOT: handbook.example.org (the placeholder).

openssl s_client -connect handbook.ptdiocese.org:443 -servername handbook.ptdiocese.org </dev/null 2>/dev/null \
  | openssl x509 -noout -issuer -subject -dates
# Expected: issuer is Let's Encrypt (or GitHub's Pages CA); CN=handbook.ptdiocese.org; not expired.
```

Also a quick browser check: lock icon present, content matches the real PT handbook.

8. **Chuck enables Enforce HTTPS (day-2).** Usually next day, after Let's Encrypt has provisioned. Repo Settings → Pages → check Enforce HTTPS. Verify: `curl -fsSL -I http://handbook.ptdiocese.org/` returns a 301 to `https://`.

9. **Controller appends a Week-5 entry to `internal/PolicyWonk-Daily-Log.md`** capturing: the five PolicyCodex commit SHAs from Tasks 1-6, the `pt-policy` merge SHA, the ruleset pre/post JSON diffs (verifying only `updated_at` differs), the workflow run URL, the live `handbook.ptdiocese.org` URL, the cert issuer + expiry from the smoke, and any deviations.

10. **Controller updates CLAUDE.md's Week-4 status block (or opens the Week-5 status block) with the PUBLISH-07 close-out** and updates `internal/PolicyWonk-Week-4-Demo.md`'s "Risks and residuals" → "Handbook is built but not served" line to "Resolved by PUBLISH-07 (2026-05-DD)."

The live install is independent code; if any smoke check fails, the failure is operational, not a regression of the Tasks 1-6 merge, and is fixed in a follow-up.

---

## Execution handoff

Plan complete and saved to `internal/superpowers/plans/2026-05-26-publish-07-handbook-pages-serving.md`. Two execution options:

1. **Subagent-driven (recommended).** Dispatch a worktree subagent for Tasks 1-6 via `isolation: "worktree"`, two-stage spec+quality review per task, controller (Scarlet) does the post-merge live install separately. Matches the Week-3 + Week-4 dispatch pattern.

2. **Inline execution.** Controller runs Tasks 1-6 in this session, then the post-merge live install with Chuck.

Which approach?
