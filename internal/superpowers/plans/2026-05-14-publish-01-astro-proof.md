# PUBLISH-01 Astro Proof Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A standalone Astro project at `handbook/` that builds a multi-page static site from a sample markdown directory matching the foundational-policy bundle layout. Demonstrates that the publish pipeline can take `policies/<slug>/policy.md` + `policies/<slug>.md` mixed inputs and produce the deployable handbook. Sets up PUBLISH-06 (Actions deploy) for Week 4.

**Architecture:** Standalone Astro 5 project in a top-level `handbook/` directory, fully isolated from the Django/Python app side. Astro Content Collections drive the type-safe ingest of policy markdown; a Zod schema validates the foundational-policy frontmatter (so a malformed `provides:` in any policy.md fails the build). Sample content lives at `handbook/src/content/policies/` and mirrors the diocese's policy-repo layout (mix of flat `<slug>.md` files and bundle directories `<slug>/policy.md`). The build outputs static HTML at `handbook/dist/`. Sample content is synthetic and diocese-agnostic (`Diocese of Anytown`); the actual handbook generation in production reads from `policies/` in the diocese's policy repo (PUBLISH-06 wires that in Week 4).

**Tech Stack:** Node 20+ (verified locally at v20.20.0), npm 10+ (10.8.2 local), Astro 5.x, Zod 3.x, TypeScript. No Python.

**Ticket reference:** `PolicyWonk-v0.1-Tickets.md` PUBLISH-01. SSG decision rationale: `internal/PolicyWonk-SSG-Evaluation.md` (chose Astro for parish-team-approachability). Bundle layout to render: `internal/PolicyWonk-Foundational-Policy-Design.md`.

**BASE:** `main` at SHA `d9da925`.

---

## File Structure

- Create: `handbook/` — top-level directory holding the Astro project.
- Create: `handbook/package.json` — npm manifest with `^` range pins (no exact versions).
- Create: `handbook/astro.config.mjs` — Astro configuration.
- Create: `handbook/tsconfig.json` — TypeScript config (extends `astro/tsconfigs/strict`).
- Create: `handbook/.gitignore` — node_modules, dist, .astro.
- Create: `handbook/README.md` — what the project is, how to build, sample-vs-real content.
- Create: `handbook/src/content.config.ts` — Content Collections schema (Zod) for the `policies` collection.
- Create: `handbook/src/layouts/Base.astro` — single shared layout with title/header/footer.
- Create: `handbook/src/pages/index.astro` — handbook home page listing all policies.
- Create: `handbook/src/pages/policies/[slug].astro` — dynamic per-policy page.
- Create: sample content at `handbook/src/content/policies/`:
  - `handbook/src/content/policies/onboarding.md` — flat policy example.
  - `handbook/src/content/policies/code-of-conduct.md` — second flat example.
  - `handbook/src/content/policies/retention/policy.md` + `handbook/src/content/policies/retention/data.yaml` — foundational bundle example.
- Create: `handbook/scripts/verify-build.mjs` — Node verifier that asserts the expected files exist after `npm run build` (used as the build-verification step in lieu of pytest).

No changes outside `handbook/`. The Django app, ingest pipeline, and AI pipeline are untouched.

---

## Why `handbook/` at the top level

Two alternatives considered:
- `publish/astro/` — groups with other future publish-lane work but adds an extra dir.
- `handbook/` (chosen) — short, obvious, matches the user-visible product name ("the handbook"), and the README will explain that it's the SSG side of the system. PUBLISH-06's Actions workflow will live at `.github/workflows/publish-handbook.yml`; the path is clear from context.

---

## Why npm dep pinning uses `^` ranges, not exact

The repo's Python convention is `>=` floor pins to dodge stale-pin drift in subagent training data. The npm convention is `^` (caret) ranges, which mean "compatible patch and minor updates." For consistency with the npm ecosystem and to avoid lockfile churn on every minor update, use `^` ranges in `package.json`. `npm install` produces `package-lock.json` which pins exactly; that file is committed for reproducibility but contains no human-authored pins. Result: no exact pins in human-authored files, full reproducibility via the lockfile.

---

## Astro syntax verification

Astro and Content Collections syntax has evolved across Astro 4→5. The implementing subagent SHOULD use `mcp__plugin_context7_context7__query-docs` to verify the current syntax for:
- `defineCollection` / `glob` loader (Astro 5 uses `loader: glob({...})`, NOT the deprecated `type: 'content'`)
- Zod schema fields available on `defineCollection`'s `schema` callback
- `getCollection` and `render()` usage in `.astro` pages

The plan below uses Astro 5.x patterns as of January 2026 training data. Verify before committing.

---

## Task 1: Worktree pre-flight

**Files:**
- None modified.

- [ ] **Step 1: Confirm BASE**

```bash
git rev-parse HEAD
```

Expected: `d9da925` or descendant.

- [ ] **Step 2: Confirm Node + npm available**

```bash
node --version
npm --version
```

Expected: Node `v20.x` or higher; npm `10.x` or higher. If lower, stop and report.

- [ ] **Step 3: Confirm no `handbook/` directory exists yet**

```bash
test ! -d handbook && echo OK || echo EXISTS
```

Expected: `OK`. If `EXISTS`, stop and report. (No clobbering.)

- [ ] **Step 4: Pre-flight Astro doc check**

Use the Context7 MCP to confirm Astro 5 Content Collections syntax:

```
Query: "Astro 5 defineCollection glob loader Zod schema"
```

Note the current `defineCollection` / `loader: glob({pattern: ..., base: ...})` syntax. If it differs from the pattern in Task 3 Step 3 below, follow Context7's current form, NOT the example in this plan.

- [ ] **Step 5: No commit yet.**

---

## Task 2: Astro project scaffold + dependency install (TDD-adapted)

**Files:**
- Create: `handbook/package.json`
- Create: `handbook/astro.config.mjs`
- Create: `handbook/tsconfig.json`
- Create: `handbook/.gitignore`
- Create: `handbook/README.md`

Astro doesn't have a pytest equivalent, so the "test" in TDD-for-Astro is the build itself: write the verification script first (it will fail because the project doesn't exist), then scaffold the minimum to make it pass.

- [ ] **Step 1: Write the verification script first (it will fail)**

Create `handbook/scripts/verify-build.mjs`:

```javascript
#!/usr/bin/env node
/**
 * Verify that `npm run build` produced the expected static files.
 * Used in place of a unit-test runner for the Astro proof.
 */
import { existsSync, readFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const dist = join(__dirname, '..', 'dist');

const expected = [
  'index.html',
  'policies/onboarding/index.html',
  'policies/code-of-conduct/index.html',
  'policies/retention/index.html',
];

let failed = 0;
for (const rel of expected) {
  const full = join(dist, rel);
  if (!existsSync(full)) {
    console.error(`MISSING: dist/${rel}`);
    failed += 1;
    continue;
  }
  const html = readFileSync(full, 'utf-8');
  if (html.length < 100) {
    console.error(`TOO SMALL: dist/${rel} (${html.length} bytes)`);
    failed += 1;
    continue;
  }
  console.log(`OK: dist/${rel} (${html.length} bytes)`);
}

if (failed > 0) {
  console.error(`\n${failed} expected file(s) missing or empty.`);
  process.exit(1);
}
console.log(`\nAll ${expected.length} expected files present.`);
process.exit(0);
```

Make it executable; document that it's invoked AFTER `npm run build` writes `dist/`.

- [ ] **Step 2: Create `handbook/package.json`**

```json
{
  "name": "handbook",
  "version": "0.0.1",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "astro dev",
    "build": "astro build",
    "preview": "astro preview",
    "verify": "node scripts/verify-build.mjs"
  },
  "dependencies": {
    "astro": "^5.0.0"
  },
  "devDependencies": {
    "typescript": "^5.4.0"
  }
}
```

Note on Zod: Astro 5 re-exports a `z` helper from `astro:content` for collection schemas; the implementer does not need to install `zod` separately. Confirm via Context7 if uncertain.

- [ ] **Step 3: Create `handbook/astro.config.mjs`**

```javascript
// @ts-check
import { defineConfig } from 'astro/config';

export default defineConfig({
  // Site is required for canonical URLs at build time. Replace with the
  // diocese's deploy URL when PUBLISH-06 wires the production build.
  site: 'https://handbook.example.org',
});
```

- [ ] **Step 4: Create `handbook/tsconfig.json`**

```json
{
  "extends": "astro/tsconfigs/strict"
}
```

- [ ] **Step 5: Create `handbook/.gitignore`**

```
node_modules/
dist/
.astro/
.env
.env.production
.DS_Store
```

- [ ] **Step 6: Create `handbook/README.md`**

```markdown
# Handbook (PolicyCodex Astro Proof)

This is the static-site-generation side of PolicyCodex. It renders a
diocese's published policies into a deployable HTML handbook.

In v0.1 (this commit), the project ships with synthetic sample content
under `src/content/policies/` to prove the build works against the
foundational-policy bundle layout. In production, PUBLISH-06 (Week 4)
wires this build against the diocese's actual `policies/` directory
from their policy repo.

## Build

```
cd handbook
npm install
npm run build
npm run verify
```

`npm run build` writes static HTML to `dist/`. `npm run verify` checks
that the expected files exist.

## Content layout

The `policies` collection accepts two shapes:

- Flat: `src/content/policies/<slug>.md`. Use for normal policies.
- Bundle: `src/content/policies/<slug>/policy.md` (+ optional
  `data.yaml`). Use for foundational policies whose structured data
  drives app configuration. Frontmatter on `policy.md` declares
  `foundational: true` and `provides: [...]`. See
  `internal/PolicyWonk-Foundational-Policy-Design.md` (in the repo
  root) for the full design.

## Sample content is generic by design

The samples in `src/content/policies/` use `Diocese of Anytown` and
synthetic policy content. v0.1 ships the codebase generic; real
diocesan content lives in each diocese's separate policy repo.
```

- [ ] **Step 7: Install dependencies**

```bash
cd handbook && npm install
```

Expected: `package-lock.json` is created. No errors. `node_modules/` is populated. Inspect briefly: `ls node_modules | head -20` confirms `astro` is present.

- [ ] **Step 8: First-pass scaffolded build will fail (no source files yet)**

```bash
cd handbook && npm run build 2>&1 | tail -20 || true
```

Expected: Astro complains about missing `src/pages/`. That's the "test fails first" signal. Do not commit yet.

- [ ] **Step 9: Commit (scaffold-only)**

```bash
git add handbook/package.json handbook/package-lock.json handbook/astro.config.mjs handbook/tsconfig.json handbook/.gitignore handbook/README.md handbook/scripts/verify-build.mjs
git commit -m "feat(PUBLISH-01): scaffold Astro 5 project at handbook/ + verify script"
```

---

## Task 3: Content Collections schema (Zod)

**Files:**
- Create: `handbook/src/content.config.ts`

- [ ] **Step 1: Verify current Astro 5 syntax via Context7**

```
Query: "Astro 5 content.config.ts defineCollection glob loader z.object"
```

The code in Step 2 reflects the Astro 5 syntax as of training data. Reconcile any differences with current docs.

- [ ] **Step 2: Create `handbook/src/content.config.ts`**

```typescript
import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

const policies = defineCollection({
  // Glob picks up BOTH flat `<slug>.md` and bundle `<slug>/policy.md` files.
  // Astro derives the slug from the path; for bundles, the slug is the
  // parent directory name, not "policy".
  loader: glob({ pattern: ['*.md', '*/policy.md'], base: './src/content/policies' }),
  schema: z.object({
    title: z.string(),
    owner: z.string().optional(),
    foundational: z.boolean().default(false),
    provides: z.array(z.string()).default([]),
    effective_date: z.coerce.date().optional(),
    last_review: z.coerce.date().optional(),
    retention_period: z.string().optional(),
  }).refine(
    (data) => !data.foundational || data.provides.length > 0,
    {
      message: 'foundational policies must declare a non-empty provides: [...] list',
      path: ['provides'],
    }
  ),
});

export const collections = { policies };
```

The `.refine()` enforces the foundational-policy invariant at build time: any `policy.md` marked `foundational: true` without a `provides:` list fails the build. This is the Astro-side reflection of INGEST-07's `BundleError` for the same case.

- [ ] **Step 3: Verify it parses by running the build (still expected to fail on missing pages)**

```bash
cd handbook && npm run build 2>&1 | tail -10 || true
```

Expected: complaint shifts to missing pages, not collections.

- [ ] **Step 4: Commit**

```bash
git add handbook/src/content.config.ts
git commit -m "feat(PUBLISH-01): policies Content Collection with Zod schema"
```

---

## Task 4: Layouts + pages

**Files:**
- Create: `handbook/src/layouts/Base.astro`
- Create: `handbook/src/pages/index.astro`
- Create: `handbook/src/pages/policies/[slug].astro`

- [ ] **Step 1: Create `handbook/src/layouts/Base.astro`**

```astro
---
interface Props { title: string }
const { title } = Astro.props;
---
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{title}</title>
    <link rel="canonical" href={new URL(Astro.url.pathname, Astro.site)} />
  </head>
  <body>
    <header>
      <h1><a href="/">Diocese of Anytown Handbook</a></h1>
    </header>
    <main>
      <slot />
    </main>
    <footer>
      <p>Generated by PolicyCodex.</p>
    </footer>
  </body>
</html>
```

- [ ] **Step 2: Create `handbook/src/pages/index.astro`**

```astro
---
import { getCollection } from 'astro:content';
import Base from '../layouts/Base.astro';

const policies = (await getCollection('policies')).sort((a, b) =>
  a.id.localeCompare(b.id)
);
---
<Base title="Diocese of Anytown Handbook">
  <h2>Policies</h2>
  <ul>
    {policies.map((p) => (
      <li>
        <a href={`/policies/${p.id.replace(/\/policy$/, '')}/`}>{p.data.title}</a>
        {p.data.foundational && <span> (foundational)</span>}
      </li>
    ))}
  </ul>
</Base>
```

Note on URL shape: Astro's `glob` loader sets `entry.id` to the path relative to `base`, with extensions stripped (e.g., `onboarding`, `retention/policy`). For bundles, the URL we want is `/policies/retention/`, so the index strips the trailing `/policy` segment. Verify via Context7 if Astro 5's id-derivation differs.

- [ ] **Step 3: Create `handbook/src/pages/policies/[slug].astro`**

```astro
---
import { getCollection, render } from 'astro:content';
import Base from '../../layouts/Base.astro';

export async function getStaticPaths() {
  const policies = await getCollection('policies');
  return policies.map((p) => {
    // For bundles (slug ends with "/policy"), use the parent dir name.
    // For flat policies, use the id as-is.
    const slug = p.id.endsWith('/policy') ? p.id.slice(0, -'/policy'.length) : p.id;
    return { params: { slug }, props: { entry: p } };
  });
}

const { entry } = Astro.props;
const { Content } = await render(entry);
---
<Base title={entry.data.title}>
  <article>
    <h2>{entry.data.title}</h2>
    {entry.data.foundational && (
      <p><strong>Foundational policy</strong> provides:
        {' '}
        {entry.data.provides.join(', ')}
      </p>
    )}
    {entry.data.owner && <p>Owner: {entry.data.owner}</p>}
    {entry.data.last_review && (
      <p>Last review: {entry.data.last_review.toISOString().slice(0, 10)}</p>
    )}
    <hr />
    <Content />
  </article>
</Base>
```

- [ ] **Step 4: First build attempt (still expected to fail on missing content)**

```bash
cd handbook && npm run build 2>&1 | tail -15 || true
```

Expected: the build now compiles the pages but emits 0 routes because the `policies` collection is empty. That's Task 5's territory.

- [ ] **Step 5: Commit**

```bash
git add handbook/src/layouts handbook/src/pages
git commit -m "feat(PUBLISH-01): Base layout + index page + dynamic policy page"
```

---

## Task 5: Sample content (generic diocese)

**Files:**
- Create: `handbook/src/content/policies/onboarding.md`
- Create: `handbook/src/content/policies/code-of-conduct.md`
- Create: `handbook/src/content/policies/retention/policy.md`
- Create: `handbook/src/content/policies/retention/data.yaml`

Synthetic, diocese-agnostic. No PT references.

- [ ] **Step 1: Create `handbook/src/content/policies/onboarding.md`**

```markdown
---
title: New Employee Onboarding
owner: HR
foundational: false
effective_date: 2025-01-01
last_review: 2025-01-01
---

# New Employee Onboarding

This is sample content for the Astro proof. The Diocese of Anytown
welcomes new employees with a structured onboarding process covering
benefits enrollment, code of conduct review, and IT setup.

## First day checklist

1. Complete I-9 verification.
2. Sign the code of conduct.
3. Receive diocese laptop and email account.

(Sample content only; real onboarding policies live in the diocese's
policy repo.)
```

- [ ] **Step 2: Create `handbook/src/content/policies/code-of-conduct.md`**

```markdown
---
title: Code of Conduct
owner: Chancellor
foundational: false
effective_date: 2024-06-01
last_review: 2025-06-01
---

# Code of Conduct

This is sample content for the Astro proof. The Diocese of Anytown's
code of conduct outlines expectations for ethical behavior, conflict-of-
interest disclosures, and the reporting mechanism for concerns.

## Reporting concerns

Concerns may be raised through the diocese's confidential reporting
channel or directly with the Chancellor's office.

(Sample content only.)
```

- [ ] **Step 3: Create `handbook/src/content/policies/retention/policy.md` (foundational bundle example)**

```markdown
---
title: Document Retention Policy
owner: Chancellor
foundational: true
provides:
  - classifications
  - retention-schedule
effective_date: 2024-08-01
last_review: 2024-08-01
retention_period: Permanent
---

# Document Retention Policy

This is sample content for the Astro proof. The Diocese of Anytown's
document retention policy establishes mandatory retention periods,
classifications, and disposal procedures for diocesan records.

The classifications and the retention schedule live in the companion
`data.yaml` file in this bundle and are consumed directly by the
PolicyCodex application.

(Sample content only.)
```

- [ ] **Step 4: Create `handbook/src/content/policies/retention/data.yaml`**

```yaml
# Sample data.yaml for the Astro proof.
# Real foundational-policy bundles live in each diocese's policy repo;
# the Astro project here proves the bundle layout renders without
# the data.yaml content being rendered into HTML in v0.1.

classifications:
  - id: administrative
    name: Administrative
  - id: financial
    name: Financial
  - id: personnel
    name: Personnel

retention_schedule:
  - group: Administrative Records
    type: General correspondence
    retention: 3 years
  - group: Financial Records
    type: Audited financial statements
    retention: Permanent
```

The Zod schema in Task 3 does not require `data.yaml` (it is not in the policies collection — Astro only loads `*.md` and `*/policy.md`). `data.yaml` ships in the bundle directory for parity with the real bundle pattern; INGEST-07 reads it, PUBLISH-01 ignores it. PUBLISH-02 or a later ticket will render it.

- [ ] **Step 5: Run the build**

```bash
cd handbook && npm run build
```

Expected: build succeeds. Console reports "3 page(s) built" (index + 3 policy pages = 4, depending on Astro's reporting).

- [ ] **Step 6: Run the verifier**

```bash
cd handbook && npm run verify
```

Expected: `All 4 expected files present.` (Note: the verifier in Task 2 asserts 4 paths; if Astro produces directory-style URLs like `dist/policies/onboarding/index.html`, the verifier matches that. Confirm during implementation.)

If `npm run verify` reports any MISSING / TOO SMALL, fix before committing.

- [ ] **Step 7: Commit**

```bash
git add handbook/src/content/policies
git commit -m "feat(PUBLISH-01): sample policies content (flat + bundle, generic diocese)"
```

---

## Task 6: End-to-end verification + handoff

**Files:**
- None modified.

- [ ] **Step 1: Clean build from scratch**

```bash
cd handbook && rm -rf dist .astro && npm run build && npm run verify
echo "exit=$?"
```

Expected: exit 0; 4 expected files present.

- [ ] **Step 2: Confirm no leakage of PT-specific tokens**

```bash
grep -ri --include='*.astro' --include='*.md' --include='*.yaml' --include='*.ts' --include='*.mjs' --include='*.json' -E 'pensacola|tallahassee|pt-policy|policycodex(?!\b)' handbook/ || echo "no PT leakage"
```

Expected: `no PT leakage`. (One mention of `policycodex` IS in the README header and `package.json` name's parent context; that's the framework name, not PT-specific. The grep above tolerates that.)

Alternatively, check just for PT specifically:

```bash
grep -ri 'pensacola\|tallahassee\|pt-policy' handbook/ || echo "no PT leakage"
```

Expected: `no PT leakage`.

- [ ] **Step 3: Confirm Python suite still green**

The handbook/ work is Python-isolated, but run the suite to confirm no accidental cross-pollution:

```bash
cd /Users/chuck/PolicyWonk && python -m pytest -v
```

Expected: 116 passing (unchanged from BASE).

- [ ] **Step 4: Compose self-report**

Cover:
- Goal in one sentence.
- Astro version that landed (from `package.json` resolved via `package-lock.json`).
- Project location decision (`handbook/`) and rejected alternatives (`publish/astro/`).
- Files created.
- Commit list (`git log --oneline main..HEAD`).
- Build output summary (file count, dist size, build time).
- Any Astro 5 syntax adjustments made vs. the plan (the plan was written against training-data syntax; Context7 may have surfaced differences).
- Open follow-ups (e.g., URL scheme refinement in PUBLISH-02; production wiring against the diocese's policy repo in PUBLISH-06).

- [ ] **Step 5: Handoff to code review**

Do not merge. Hand the branch + self-report back to the dispatching session for `superpowers:requesting-code-review`.

---

## Definition of Done

- `handbook/` directory exists at repo top level with the file structure described above.
- `cd handbook && npm install && npm run build && npm run verify` runs clean from a fresh clone (no errors, exit 0).
- `dist/index.html`, `dist/policies/onboarding/index.html`, `dist/policies/code-of-conduct/index.html`, `dist/policies/retention/index.html` all exist and are non-empty.
- The index page lists all 3 policies with `(foundational)` annotation on the retention bundle.
- The retention bundle's page renders, declares "Foundational policy provides: classifications, retention-schedule", and includes the policy.md body content.
- `package.json` uses `^` ranges (not exact pins); `package-lock.json` is committed for reproducibility.
- Zod schema's `.refine()` correctly fails the build if a `foundational: true` policy omits `provides:` (proof: optionally, the implementer can briefly add `foundational: true` to `onboarding.md` and run `npm run build` to confirm the build fails with the schema error, then revert; this is a manual sanity check, not committed).
- No PT-specific tokens (`pensacola`, `tallahassee`, `pt-policy`) anywhere in `handbook/`.
- No em dashes in any file under `handbook/`.
- Python test suite remains at the BASE green count (116).
- 4 commits since BASE `d9da925`: scaffold, content config, layouts/pages, sample content.
- Self-report calls out any Astro syntax differences from the plan, the resolved Astro version, and the build output size/time.
