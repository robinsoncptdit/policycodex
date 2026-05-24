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
2. After it merges, add the `foundational-guard` check to the policy repo's
   `main` branch protection as a required status check (Settings -> Rules,
   or the repo ruleset). This makes the guard blocking rather than advisory.

## Tests

The script's tests live in `repo-template/tests/` in the PolicyCodex repo
and run as part of the PolicyCodex suite. They are not copied into the
policy repo.
