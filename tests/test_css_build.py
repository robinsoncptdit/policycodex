"""APP-28a: guard the committed Tailwind/DaisyUI CSS.

Structural assertions run everywhere (offline). The drift guard regenerates
the CSS and diffs it; it is env-gated (mirrors INGEST-06's POLICYCODEX_CORPUS_DIR
pattern) so the offline suite stays green and CI/local with the toolchain wired
runs the real check.
"""
import os
import subprocess
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_CSS = _ROOT / "static" / "css" / "policycodex.css"


def test_compiled_css_is_committed_and_nontrivial():
    assert _CSS.is_file(), "static/css/policycodex.css must be committed"
    assert _CSS.stat().st_size > 10_000, "compiled CSS looks empty/truncated"


def test_compiled_css_carries_brand_and_component_sentinels():
    text = _CSS.read_text(encoding="utf-8")
    # Brand color (from the daisyui-theme @plugin) and a DaisyUI component rule
    # both survive the build. If the plain-Tailwind fallback was taken, the
    # .btn sentinel below must be updated to the chosen utility recipe.
    assert "#4a5f8a" in text or "74 95 138" in text or "4a5f8a" in text.lower()
    assert ".btn" in text


@pytest.mark.skipif(
    os.environ.get("POLICYCODEX_BUILD_CSS") != "1",
    reason="set POLICYCODEX_BUILD_CSS=1 to run the CSS drift guard (needs the toolchain)",
)
def test_committed_css_matches_a_fresh_build():
    subprocess.run([str(_ROOT / "scripts" / "build-css.sh")], check=True, cwd=_ROOT)
    diff = subprocess.run(
        ["git", "diff", "--exit-code", "static/css/policycodex.css"],
        cwd=_ROOT, capture_output=True, text=True,
    )
    assert diff.returncode == 0, (
        "Committed policycodex.css is stale. Run scripts/build-css.sh and commit:\n"
        + diff.stdout
    )
