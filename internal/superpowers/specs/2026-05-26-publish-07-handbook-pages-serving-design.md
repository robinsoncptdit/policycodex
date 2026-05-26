# PUBLISH-07: Serve the Handbook at a Custom Subdomain via GitHub Pages

**Date:** 2026-05-26
**Ticket:** PUBLISH-07
**Predecessor:** PUBLISH-06 (build + upload Pages artifact, merged 2026-05-24 at `2ff22d4`, live on `pt-policy`)
**Status:** Design approved by Chuck 2026-05-26. Implementation plan to follow via `superpowers:writing-plans`.

## Summary

Wire the handbook artifact uploaded by PUBLISH-06 to actually serve at a public custom subdomain. v0.1 serving target is **GitHub Pages with a custom domain**. The work spans three pieces, all in one ticket:

1. **Template change.** Extend `repo-template/.github/workflows/build-handbook.yml` from one job (build + upload) to three (preflight + build + deploy). Update `astro.config.mjs` (both the vendored copy and the upstream source) to read `ASTRO_SITE_URL` from env with a placeholder fallback. Add tests.
2. **HOWTO Part 4.** Add a "Publish the Handbook at a Custom Domain" section to `HOWTO-GitHub-Team-Setup.md` covering DNS, org-level domain verification, Pages settings, HTTPS enforcement, and troubleshooting.
3. **Live install on `pt-policy`.** Stand up `https://handbook.ptdiocese.org/` end-to-end: DNS CNAME, org TXT verify for the apex `ptdiocese.org`, repo Pages settings, PR with the updated workflow, smoke-test, enforce HTTPS (next-day after Let's Encrypt).

## Goals

- A diocese can clone the repo template, run the onboarding wizard or follow the HOWTO, enable Pages in repo Settings, and have the handbook serving at their chosen subdomain with HTTPS, with no code edits required.
- For dioceses that have not yet enabled Pages, the `Build handbook` workflow stays green (build + upload succeed; deploy job is skipped gracefully, not failed).
- The Astro `site:` URL is dynamic per-diocese, derived from the GitHub Pages API at build time. No per-diocese config in source.
- `handbook.ptdiocese.org` resolves and serves the real PT handbook by end of ticket, verifying the design against the real diocese.

## Non-goals

- Self-hosted serving alternatives (Caddy, Nginx on a VM). Defer to v0.2+.
- Wiring the wizard (APP-08..16) to capture the subdomain or to set DNS automatically. PUBLISH-07 ships the HOWTO so a diocese IT director can do it by hand; wizard-driven capture is a future ticket.
- Required-check enforcement of `deploy-pages` on the ruleset. Same advisory-only posture as `foundational-guard` per the Week-4 decision.
- Org-level domain verification automation. It is a one-time TXT record; the HOWTO walks the operator through it.

## Architecture

### Workflow shape

`repo-template/.github/workflows/build-handbook.yml` becomes three jobs in one file:

1. **`preflight`** (new, ~10s)
   - Runs on every push to `main` touching `policies/**` or `handbook/**` (existing path filter).
   - Calls `gh api repos/${{ github.repository }}/pages` via the preinstalled GitHub CLI.
   - On 200: if response `cname` is non-empty, emit `site_url=https://<cname>`; otherwise emit `site_url=<html_url>` (which the API returns already URL-prefixed). Emit `pages_configured=true` either way.
   - On 404 or non-zero exit: emits `pages_configured=false` + `site_url=` (empty); succeeds the job.
   - Permissions: `contents: read` only.

2. **`build`** (existing, modified)
   - `needs: preflight`. Always runs.
   - Adds `env: { ASTRO_SITE_URL: ${{ needs.preflight.outputs.site_url }} }` on the "Build the handbook" step. When `pages_configured=false` the env var is empty; `astro.config.mjs` falls back to the placeholder.
   - All other steps unchanged from PUBLISH-06.

3. **`deploy`** (new)
   - `needs: build`.
   - `if: needs.preflight.outputs.pages_configured == 'true'`. Skipped (gray, not red) when Pages is not configured.
   - `environment: { name: github-pages, url: ${{ steps.deployment.outputs.page_url }} }`.
   - Single step: `actions/deploy-pages@v5` (latest release 2026-03-25; verified via `gh api repos/actions/deploy-pages/releases/latest` on 2026-05-26).

Top-level `permissions:` block expands to `contents: read`, `pages: write`, `id-token: write`. Existing `concurrency:` block flips `cancel-in-progress` from `true` to `false` per GitHub's Pages recommendation, since cancelling mid-deploy can corrupt the live site. Group name stays `handbook-pages`.

### Site URL flow

```
preflight: gh api repos/$REPO/pages
  -> reads cname (custom domain) or html_url
  -> outputs pages_configured + site_url

build: env: ASTRO_SITE_URL = needs.preflight.outputs.site_url
  -> astro.config.mjs: site: process.env.ASTRO_SITE_URL || 'https://handbook.example.org'
  -> npm run build produces canonical URLs against the real domain
  -> artifact uploaded

deploy: actions/deploy-pages
  -> publishes to https://<custom-domain>/
```

Zero per-diocese configuration. The diocese enables Pages in Settings + adds custom domain; everything else flows from the Pages API response.

### Astro config change

```js
// handbook/astro.config.mjs  AND  repo-template/handbook/astro.config.mjs
import { defineConfig } from 'astro/config';

export default defineConfig({
  // Set automatically by .github/workflows/build-handbook.yml from your
  // repo's Pages config. The literal fallback below only applies for local
  // builds without Pages enabled.
  site: process.env.ASTRO_SITE_URL || 'https://handbook.example.org',
});
```

**Both files must change together.** `sync-handbook.sh` copies upstream `handbook/astro.config.mjs` over the vendored copy; if the two diverge, re-vendoring silently reverts the change. A test asserts byte-equality of the two files.

### CNAME file: NOT committed

Per GitHub Pages docs, when the source is "GitHub Actions" (not a branch), no `CNAME` file is committed to the repo. The custom domain lives in repo Settings → Pages. The template never creates one; the HOWTO does not instruct creating one.

## HOWTO Part 4 outline

Appended to `HOWTO-GitHub-Team-Setup.md`. Estimated ~80 lines, matching Parts 1-3 prose density.

1. **What you'll set up.** Public GitHub Pages site at your chosen subdomain (e.g., `handbook.example.org`), HTTPS via Let's Encrypt, automatic re-deploy on every merge to `main`. Cost: zero on Team or higher.
2. **Prereqs.** Org on Team or higher (Pages from private repos requires Team+; access-restricted Pages requires Enterprise Cloud and is out of scope for v0.1). Repo created from the template. `build-handbook.yml` present. DNS control of the subdomain's parent zone.
3. **Step 1: Verify your apex domain at the org level (one-time, recommended).** Org Settings → Pages → Add a domain → enter the apex (e.g., `example.org`). Add the TXT record GitHub provides at `_github-pages-challenge-<org>.example.org`. Verify with `dig +short TXT`. Click Verify. Locks every subdomain at that apex to your org. Keep the TXT in place.
4. **Step 2: Create the subdomain CNAME.** `handbook.example.org` → `<org>.github.io` (org name only; no repo name in the target).
5. **Step 3: Enable Pages on the policy repo.** Repo Settings → Pages → Source: **GitHub Actions** (NOT "Deploy from a branch"). Enter `handbook.example.org` as the custom domain. Save.
6. **Step 4: Trigger a deploy.** Push any commit to `main` or re-run the latest `Build handbook` workflow. Watch the `deploy` job go from gray to green. The job summary shows the live URL.
7. **Step 5: Enforce HTTPS.** Toggle Enforce HTTPS in repo Settings → Pages after Let's Encrypt provisions (up to 24h).
8. **Troubleshooting.** CNAME target uses org name only (common mistake). DNS propagation (up to a few hours). What gray-deploy looks like (Pages not configured) vs. red-deploy (real failure). What to do if `_github-pages-challenge-<org>` TXT goes missing.

## Live install on `pt-policy`

End-to-end stand-up of `https://handbook.ptdiocese.org/`. Mix of Chuck-side and Scarlet-side actions.

| Step | Owner | Action |
|---|---|---|
| 1 | Chuck | Create DNS CNAME: `handbook.ptdiocese.org` → `diocese-of-pensacola-tallahassee.github.io`. |
| 2 | Chuck | Org domain verify (apex): add TXT at `_github-pages-challenge-diocese-of-pensacola-tallahassee.ptdiocese.org`. Verify in org Settings → Pages. Keep TXT in place. |
| 3 | Chuck | `pt-policy` Settings → Pages → Source: GitHub Actions. Custom domain: `handbook.ptdiocese.org`. Save. |
| 4 | Scarlet | Open PR on `pt-policy` with the updated `build-handbook.yml` (3 jobs) and the updated `handbook/astro.config.mjs`. Squash-merge using the same admin-bypass-and-restore pattern as PUBLISH-06's install PR #2 (the ruleset requires an approving review the PR author cannot self-supply). |
| 5 | Scarlet | Watch the workflow run. Preflight green; build green with `ASTRO_SITE_URL=https://handbook.ptdiocese.org`; deploy green; environment URL appears. |
| 6 | Scarlet | Smoke (see Testing section below). |
| 7 | Chuck | Next day: toggle Enforce HTTPS in repo Settings → Pages. |

The template-and-HOWTO changes merge to `PolicyCodex/main` first; the `pt-policy` PR vendors the resulting `build-handbook.yml` + `handbook/astro.config.mjs` over.

## Testing

### Template tests (`repo-template/tests/`)

Extending existing PUBLISH-06 test files (`test_build_handbook_workflow.py`, `test_handbook_vendor.py`). Estimated 6-8 new tests:

- `build-handbook.yml` has three jobs in order: `preflight`, `build`, `deploy`.
- `preflight` calls `gh api repos/${{ github.repository }}/pages`; has `contents: read` permissions only; outputs `pages_configured` and `site_url`.
- `build` has `needs: preflight`; its build step sets `ASTRO_SITE_URL` env var from preflight output.
- `deploy` has `needs: build` AND `if: needs.preflight.outputs.pages_configured == 'true'`; declares the `github-pages` environment; uses `actions/deploy-pages@v5`.
- Top-level `permissions:` block has `pages: write` AND `id-token: write`.
- `concurrency:` has `cancel-in-progress: false`.
- `repo-template/handbook/astro.config.mjs` reads `process.env.ASTRO_SITE_URL` with the `https://handbook.example.org` fallback.
- `handbook/astro.config.mjs` (upstream) is byte-equal to `repo-template/handbook/astro.config.mjs` (prevents sync-handbook.sh from silently reverting the env-var change).

### Live smoke on `pt-policy`

Manual verification, no automation, post-merge.

| Check | Pass criterion |
|---|---|
| Workflow run | All three jobs green; `deploy` job summary shows `https://handbook.ptdiocese.org/`. |
| HTTPS resolves | `curl -fsSL -I https://handbook.ptdiocese.org/` returns `200 OK`. |
| Cert valid | Browser shows the lock icon; `openssl s_client -connect handbook.ptdiocese.org:443 -servername handbook.ptdiocese.org </dev/null 2>/dev/null \| openssl x509 -noout -issuer` shows Let's Encrypt or the GitHub Pages CA. |
| Content correct | Page contains the diocese's policy index, not the placeholder. |
| Canonical URL | View source → `<link rel="canonical">` uses `handbook.ptdiocese.org`, not `handbook.example.org`. |
| Pages env in GitHub | Repo → Environments → `github-pages` shows the live deployment. |

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| `sync-handbook.sh` reverts the `astro.config.mjs` change if someone edits the vendored copy but not the upstream. | Edit BOTH files. Add the byte-equality test (above). |
| `actions/deploy-pages@v5` could ship a v6 between spec and implementation. | Re-verify the latest tag on the planning day; bump if a v6 has shipped and Node-24 vs. v5 differences are reviewed. |
| `gh api repos/.../pages` returns 404 when Pages is not enabled. Pre-flight job must handle non-zero exit gracefully. | Plan specifies `set +e` + check `$?` + `gh api ... 2>/dev/null \|\| true` pattern. Test the false path against a known-Pages-disabled repo before merge. |
| Let's Encrypt provisioning delay (up to 24h) means Enforce HTTPS is a day-2 toggle. | HOWTO explicitly sets the expectation. Live PT install treats step 7 as a follow-up. |
| `pt-policy` admin-bypass on the `main` ruleset (same pattern as PUBLISH-06 PR #2). | Reuse the established pattern: capture ruleset state via API pre-bypass, restore exact prior state post-merge, verify, log the diff in the daily log. |
| Current `concurrency: { cancel-in-progress: true }` is wrong for Pages deploys; cancelling mid-deploy can corrupt the site. | Flip to `false` as part of this ticket. |
| First-time canonical-URL change might invalidate any cached `<link rel="canonical">` consumers. | No cached consumers exist; this is the first production deploy. Not a real risk; noted for completeness. |

## Dependencies

- PUBLISH-06 (merged 2026-05-24 at `2ff22d4`; live on `pt-policy`).
- `repo-template/tests/` infrastructure (PUBLISH-06, REPO-09).
- Org Team tier with `main` ruleset enforcing (REPO-08, resolved 2026-05-24).
- DNS control of `ptdiocese.org` (Chuck-owned per OQ-06 resolution).

## Definition of Done

- `repo-template/.github/workflows/build-handbook.yml` carries the three-job structure with all template tests passing.
- `repo-template/handbook/astro.config.mjs` and `handbook/astro.config.mjs` both read `ASTRO_SITE_URL` with the placeholder fallback; byte-equality test passes.
- `HOWTO-GitHub-Team-Setup.md` has Part 4 with the eight sub-sections above.
- `pt-policy` PR with the updated workflow + astro config is merged via the documented admin-bypass-and-restore pattern; daily-log captures the ruleset diff.
- `https://handbook.ptdiocese.org/` returns 200 with valid HTTPS, serves real PT policy content, and the canonical URL in the page source matches the live domain.
- Enforce HTTPS toggled on (may be day-2 after Let's Encrypt provisions).
- Daily-log entry captures the install timeline and any deviations.
