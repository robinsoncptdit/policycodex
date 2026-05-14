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
