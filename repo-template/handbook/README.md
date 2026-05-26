# Handbook (vendored)

This is the PolicyCodex Astro handbook, vendored into your policy repo.

`.github/workflows/build-handbook.yml` builds it: on every push to `main`
that touches `policies/**`, the workflow copies your repo's `policies/`
into `src/content/policies/` and runs the Astro build. That directory
therefore ships empty here (only a `.gitkeep`); do not add policy files to
it by hand. Edit policies through PolicyCodex, not in this directory.

The build uploads a GitHub Pages artifact; the same workflow's `deploy`
job then publishes it via `actions/deploy-pages@v5` (skipped gracefully
when Pages is not enabled on the repo). See "Part 4: Publish the handbook
at a public custom subdomain" in `HOWTO-GitHub-Team-Setup.md` for the
one-time DNS + Pages setup.

Maintainers re-vendor this directory by running `sync-handbook.sh` in the
PolicyCodex repo after the upstream handbook changes.
