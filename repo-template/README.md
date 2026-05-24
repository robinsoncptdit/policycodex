# Diocese policy-repo template

These files are copied into a diocese's private policy repository to add
PolicyCodex's repo-side automation. They are generic: nothing here names a
specific diocese.

## What is here

- `.github/workflows/foundational-guard.yml` - the L2 protection layer. On
  every pull request that touches `policies/`, it blocks the merge if the
  diff deletes a foundational policy file (one with `foundational: true` in
  its frontmatter) or empties a foundational policy's `provides:` list.
- `.github/scripts/foundational_guard.py` - the standalone script the
  workflow runs. It depends only on PyYAML.

## Install into a policy repo

1. Copy the contents of `repo-template/.github/` into the policy repo's
   `.github/` directory and open a PR.
2. After it merges, the guard runs on pull requests that change `policies/` and
   shows a red mark on violations (advisory). To make it **blocking**, add the
   `foundational-guard` check to the policy repo's `main` ruleset as a required
   status check. Before you do, read the path-filter caveat (a naive required
   check blocks pull requests that do not touch `policies/`): see
   "Part 3 (optional): Require the foundational-policy guard" in
   `HOWTO-GitHub-Team-Setup.md`.

## Handbook build (PUBLISH-06)

`handbook/` is a vendored copy of the PolicyCodex Astro handbook, and
`.github/workflows/build-handbook.yml` builds it. On every push to `main`
that touches `policies/**`, the workflow copies your `policies/` into the
handbook content directory, runs `npm ci && npm run build`, verifies the
output, and uploads a GitHub Pages artifact named `github-pages`.

This builds and uploads the handbook; it does not serve it. Serving the
artifact at your subdomain is PUBLISH-07.

To update the vendored handbook after the upstream Astro project changes,
run `./sync-handbook.sh` from this directory and commit the result.

## Tests

The script's tests live in `repo-template/tests/` in the PolicyCodex repo
and run as part of the PolicyCodex suite. They are not copied into the
policy repo.
