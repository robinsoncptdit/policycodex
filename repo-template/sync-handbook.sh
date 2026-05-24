#!/usr/bin/env bash
# Re-vendor the app repo's handbook/ into repo-template/handbook/.
# Excludes build dirs and sample content; leaves an empty, tracked
# content/policies dir. Run this whenever the app handbook/ changes
# (PUBLISH-02..05 will).
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
SRC="$HERE/../handbook"
DST="$HERE/handbook"

rm -rf "$DST"
mkdir -p "$DST"

# Copy the tracked project files (skip node_modules/dist/.astro entirely).
for item in .gitignore astro.config.mjs package.json package-lock.json \
            README.md tsconfig.json scripts src; do
  cp -R "$SRC/$item" "$DST/"
done

# Strip sample policy content; keep the dir tracked for the build copy step.
rm -rf "${DST:?}/src/content/policies/"*
touch "$DST/src/content/policies/.gitkeep"

# Replace the dev README (which describes sample content) with one that
# describes the vendored state, so the diocese's installed copy is accurate.
cat > "$DST/README.md" <<'EOF'
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
EOF

echo "Vendored handbook -> $DST"
