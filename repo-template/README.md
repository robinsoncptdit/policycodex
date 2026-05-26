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

## Handbook build and deploy (PUBLISH-06 + PUBLISH-07)

`handbook/` is a vendored copy of the PolicyCodex Astro handbook, and
`.github/workflows/build-handbook.yml` builds and deploys it. On every push
to `main` that touches `policies/**` or `handbook/**`, the workflow runs
three jobs:

1. `preflight` calls the GitHub Pages API for the repo and outputs
   `pages_configured` (whether you have enabled Pages) plus `site_url`
   (your custom-domain URL if set, otherwise the default `<org>.github.io`).
2. `build` copies your `policies/` into the handbook content directory,
   runs `npm ci && npm run build`, verifies the output, and uploads a
   `github-pages` artifact. The Astro `site:` URL is set from
   `preflight.site_url` so canonical URLs use your real domain.
3. `deploy` publishes the artifact to GitHub Pages. It is skipped (gray,
   not red) when `pages_configured` is `false`, so a fresh policy repo
   without Pages enabled does not red-flag its merges. Pinned to
   `actions/deploy-pages@v5`.

To turn on serving at your subdomain, follow Part 4 of
`HOWTO-GitHub-Team-Setup.md` (DNS CNAME, org-level apex verification,
repo Pages settings = GitHub Actions source + custom domain). After the
one-time setup, every merge to `main` re-deploys the handbook.

To update the vendored handbook after the upstream Astro project changes,
run `./sync-handbook.sh` from this directory and commit the result.

## Tests

The script's tests live in `repo-template/tests/` in the PolicyCodex repo
and run as part of the PolicyCodex suite. They are not copied into the
policy repo.
