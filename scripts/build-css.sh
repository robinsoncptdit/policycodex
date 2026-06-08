#!/usr/bin/env bash
# Regenerate static/css/policycodex.css from styles/input.css using the
# Tailwind standalone CLI + DaisyUI. The toolchain lives in a gitignored
# .tools/ dir and is fetched on demand; only the compiled CSS is committed.
# Run from the repo root: scripts/build-css.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TOOLS="$ROOT/.tools"
mkdir -p "$TOOLS"

# 1. Tailwind standalone CLI binary (platform-detected).
case "$(uname -s)-$(uname -m)" in
  Darwin-arm64)  TW="tailwindcss-macos-arm64" ;;
  Darwin-x86_64) TW="tailwindcss-macos-x64" ;;
  Linux-aarch64) TW="tailwindcss-linux-arm64" ;;
  Linux-x86_64)  TW="tailwindcss-linux-x64" ;;
  *) echo "Unsupported platform: $(uname -s)-$(uname -m)" >&2; exit 1 ;;
esac
if [ ! -x "$TOOLS/tailwindcss" ]; then
  echo "Downloading Tailwind standalone CLI ($TW)..."
  curl -fsSLo "$TOOLS/tailwindcss" \
    "https://github.com/tailwindlabs/tailwindcss/releases/latest/download/$TW"
  chmod +x "$TOOLS/tailwindcss"
fi

# 2. DaisyUI plugin bundles (Node-free .mjs).
for f in daisyui.mjs daisyui-theme.mjs; do
  if [ ! -f "$TOOLS/$f" ]; then
    echo "Downloading $f..."
    curl -fsSLo "$TOOLS/$f" \
      "https://github.com/saadeghi/daisyui/releases/latest/download/$f"
  fi
done

# 3. Compile (minified).
echo "Compiling static/css/policycodex.css..."
"$TOOLS/tailwindcss" \
  -i "$ROOT/styles/input.css" \
  -o "$ROOT/static/css/policycodex.css" \
  --minify
echo "Done."
