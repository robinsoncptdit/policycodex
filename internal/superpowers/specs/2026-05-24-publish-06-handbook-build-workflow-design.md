# PUBLISH-06: Handbook Build Workflow Design

**Date:** 2026-05-24
**Ticket:** PUBLISH-06 (M, Week 3-4 carry) - "GitHub Actions workflow: build handbook on push to `main`, deploy artifact"
**Depends on:** PUBLISH-01 (Astro proof, done), REPO-04 (PT policy repo, done)
**Status:** Approved 2026-05-24

## Goal

Close the merge-to-handbook loop. When a diocese merges a policy PR to `main` in its policy repo, GitHub Actions builds the Astro handbook from the repo's own `policies/` and uploads a deployable GitHub Pages artifact. Actual subdomain serving stays in PUBLISH-07 (Week 5).

## Decisions locked (brainstorm 2026-05-24)

1. **Build location: vendor into `repo-template/`.** The handbook build runs in the diocese policy repo's own Actions. The Astro project and the build workflow are vendored into `repo-template/` and copied into the diocese repo during onboarding, alongside the existing `.github/` foundational-guard (REPO-09). This matches the repo-template precedent and the ship-generic model, and avoids cross-repo checkout of the private app repo. Rejected: a thin workflow that checks out PolicyCodex (needs a PAT); a central build in the app repo (not generic).

2. **Deploy depth: build + upload Pages artifact only.** The workflow runs `actions/upload-pages-artifact` and stops. No `deploy-pages` job, no custom domain. PUBLISH-07 adds the deploy job and `handbook.ptdiocese.org`. Clean build/serve split per the sprint plan.

3. **Content feeding: copy step, not a re-pointed glob base.** The workflow copies the repo's root `policies/` into the Astro content dir before building. Chosen over re-pointing Astro's glob `base` to `../policies` because it is robust (no dependence on Astro allowing an out-of-tree content base) and keeps the vendored Astro project unmodified from source.

## Architecture

The diocese policy repo, after onboarding, contains:

```
<diocese-repo>/
  policies/                      # the diocese's policy markdown (flat + bundles)
  handbook/                      # vendored Astro project (from repo-template/)
  .github/
    workflows/
      foundational-guard.yml     # REPO-09 (existing)
      build-handbook.yml         # PUBLISH-06 (new)
    scripts/
      foundational_guard.py      # REPO-09 (existing)
```

On `push` to `main`, `build-handbook.yml` copies `policies/` into `handbook/src/content/policies/`, builds the Astro site, verifies the output, and uploads it as a Pages artifact.

## Components

### 1. `repo-template/handbook/`

A copy of the app repo's `handbook/` Astro project (Astro ^5), with one difference: the sample content under `src/content/policies/` is removed (replaced by a `.gitkeep` so the empty dir is tracked). The diocese's real policies populate it at build time via the copy step. Everything else (`package.json`, `astro.config.mjs`, `src/content.config.ts`, `src/layouts/Base.astro`, `src/pages/`, `scripts/verify-build.mjs`) is carried over unchanged.

The existing glob loader in `content.config.ts` already handles both layouts:

```js
loader: glob({ pattern: ['*.md', '*/policy.md'], base: './src/content/policies' })
```

so flat `policies/<slug>.md` and foundational bundles `policies/<slug>/policy.md` both render without change.

`astro.config.mjs` keeps its placeholder `site: 'https://handbook.example.org'`; PUBLISH-07 sets the real subdomain.

### 2. `repo-template/.github/workflows/build-handbook.yml`

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

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: npm
          cache-dependency-path: handbook/package-lock.json
      - name: Stage policies into the handbook content dir
        run: |
          rm -rf handbook/src/content/policies/*
          cp -r policies/* handbook/src/content/policies/
      - name: Install dependencies
        working-directory: handbook
        run: npm ci
      - name: Build
        working-directory: handbook
        run: npm run build
      - name: Verify build output
        working-directory: handbook
        run: npm run verify
      - name: Upload Pages artifact
        uses: actions/upload-pages-artifact@v3
        with:
          path: handbook/dist
```

Notes:
- `npm ci` requires a committed `handbook/package-lock.json`. The app `handbook/` already has one; the vendored copy carries it (it also feeds the npm cache key).
- `verify-build.mjs` currently asserts a fixed sample-file list. It must be generalized to verify the build produced `index.html` plus at least one policy page (any non-trivial `index.html` under `dist/policies/`), rather than naming the sample slugs. This is a plan step done in the app `handbook/` (the source) and carried to the vendored copy by `sync-handbook.sh`.

### 3. `repo-template/sync-handbook.sh`

A small script that re-copies the app repo's `handbook/` into `repo-template/handbook/`, excluding `node_modules/`, `dist/`, `.astro/`, and the sample content under `src/content/policies/` (leaving a `.gitkeep`). Run whenever the app `handbook/` changes (PUBLISH-02..05 will), so the vendored copy does not silently drift. Keeps re-vendoring a one-command operation.

### 4. `repo-template/README.md` update

Document the new build workflow: what it does, that it depends on a vendored `handbook/`, the one-time enabling steps (Pages settings come with PUBLISH-07), and how to re-vendor via `sync-handbook.sh`.

## Data flow

1. Editor merges a policy PR to `main` (via the app's publish action, APP-19).
2. `push` to `main` touching `policies/**` fires `build-handbook.yml`.
3. Workflow copies `policies/` into the handbook content dir.
4. Astro builds `handbook/dist/`.
5. `verify-build.mjs` confirms expected output exists and is non-trivial.
6. `upload-pages-artifact` publishes `dist/` as the `github-pages` artifact.
7. (PUBLISH-07) a `deploy-pages` job serves it at the diocese subdomain.

## Error handling

- Malformed policy frontmatter fails the Astro build (the `content.config.ts` Zod schema already enforces, e.g., foundational policies must declare a non-empty `provides:`). A failed build is a red check on `main`. Acceptable for v0.1; pre-merge build validation is a future enhancement (see Out of scope).
- A missing or empty `policies/` produces a handbook with no policy pages but a valid `index.html`; the generalized `verify` requires at least one policy page, so a genuinely empty build fails loudly.

## Testing

**Automated (Python, in the main suite, no Node required)** - `repo-template/tests/test_build_handbook.py`:
- The workflow file exists and triggers on `push` to `main` with `policies/**` and `handbook/**` paths.
- The workflow includes the staging copy step, `npm ci`, `npm run build`, `npm run verify`, and `upload-pages-artifact`.
- The vendored `handbook/` has `package.json`, `astro.config.mjs`, `src/content.config.ts`, `src/layouts/Base.astro`, and a committed `package-lock.json`.
- The vendored `handbook/src/content/policies/` carries no sample markdown (only `.gitkeep`).

**Build smoke (during the plan, local):** drop a small sample `policies/` (one flat policy + one bundle) next to the vendored handbook, run the copy step + `npm run build && npm run verify`, confirm `dist/index.html` and a `dist/policies/<slug>/index.html` render. This proves the copy mechanism and the generalized verify before the ticket is called done.

**Live smoke (one-time, out of band):** install the workflow on `pt-policy`, merge a PR, confirm the `github-pages` artifact builds. This is a you+me step paired with REPO-09's pending deploy, not part of the automated suite.

## Out of scope (PUBLISH-06)

- Deploy / serving / custom subdomain (PUBLISH-07).
- PR-time build validation (push-to-main only, per ticket). Noted as a future enhancement.
- A live deploy job (`deploy-pages`).
- Image/theme work (PUBLISH-03) and URL scheme (PUBLISH-02), which evolve the app `handbook/` independently; `sync-handbook.sh` is how their output reaches the vendored copy later.

## Affected files

- Create: `repo-template/handbook/**` (vendored Astro project, sample content stripped).
- Create: `repo-template/.github/workflows/build-handbook.yml`.
- Create: `repo-template/sync-handbook.sh`.
- Create: `repo-template/tests/test_build_handbook.py`.
- Modify: `handbook/scripts/verify-build.mjs` (generalize the expected-files check; carried to the vendored copy by the sync script).
- Modify: `repo-template/README.md`.

(`handbook/package-lock.json` already exists; no new lockfile is created.)
