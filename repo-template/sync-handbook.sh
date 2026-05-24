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

echo "Vendored handbook -> $DST"
