# Handbook (vendored)

This is the PolicyCodex Astro handbook, vendored into your policy repo.

`.github/workflows/build-handbook.yml` builds it: on every push to `main`
that touches `policies/**`, the workflow copies your repo's `policies/`
into `src/content/policies/` and runs the Astro build. That directory
therefore ships empty here (only a `.gitkeep`); do not add policy files to
it by hand. Edit policies through PolicyCodex, not in this directory.

The build uploads a GitHub Pages artifact. Serving it at your subdomain is
handled separately (PUBLISH-07).

Maintainers re-vendor this directory by running `sync-handbook.sh` in the
PolicyCodex repo after the upstream handbook changes.
