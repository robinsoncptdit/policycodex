"""REPO-10 generic-ship guard.

PolicyCodex ships as a generic, diocese-agnostic codebase. No shipping
file may name the install-zero diocese (Pensacola-Tallahassee) or point at
the dev-only `internal/` document tree, because those names and paths do
not exist in an installed diocese instance. This test enforces that
invariant so a future hardcode is caught in the suite, not on a customer's
VM.

Scope mirrors the REPO-10 ticket grep: the shipping app/library dirs plus
the vendored `repo-template/`. Out of scope (and excluded): test files,
`internal/`, `archive/`, the `spike/` dev harness, `README.md` (which
intentionally credits install zero), and this file.
"""
from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent

# Dirs whose contents are part of the shipping artifact and must stay generic.
_SHIPPING_ROOTS = ("app", "core", "ai", "ingest", "policycodex_site", "repo-template", "static")

# Root-level files that ship in the public repo and must stay generic.
_SHIPPING_ROOT_FILES = (
    "Dockerfile",
    ".dockerignore",
    "docker-compose.yml",
    "docker-compose.pull.yml",
    ".env.example",
    "install.sh",
    "docker/entrypoint.sh",
)

# Text file types present in the shipping roots. This is an allowlist: a new
# shipping file type (e.g. .toml, a Dockerfile) is NOT scanned until added here.
_SCANNED_SUFFIXES = {
    ".py", ".yaml", ".yml", ".html", ".md", ".txt",
    ".cfg", ".ini", ".astro", ".mjs", ".js", ".json",
    ".sh", ".ts", ".css",  # vendored verbatim into diocese repos via repo-template/
}

# A path containing any of these parts is skipped.
_EXCLUDED_PARTS = {"tests", "__pycache__", "node_modules", "dist", ".astro", "venv"}

# Diocese-name and dev-path tokens that must never appear in a shipping file.
_FORBIDDEN = (
    re.compile(r"pensacola", re.IGNORECASE),
    re.compile(r"tallahassee", re.IGNORECASE),
    re.compile(r"pt-policy", re.IGNORECASE),
    re.compile(r"pt_classification", re.IGNORECASE),
    # Dev-only doc tree, never present in an installed instance. Narrow so the
    # bare word "internal" (e.g. "internal server error") does not trip it.
    re.compile(r"internal/(?:PolicyWonk|PolicyCodex|REPO-|Document |superpowers/)"),
)


def _is_test_file(path: Path) -> bool:
    name = path.name
    return name == "tests.py" or name.startswith("test_") or name.endswith("_test.py")


def _scanned_files():
    for root in _SHIPPING_ROOTS:
        root_dir = _REPO_ROOT / root
        if not root_dir.is_dir():
            continue
        for path in root_dir.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix not in _SCANNED_SUFFIXES:
                continue
            if _is_test_file(path):
                continue
            if any(part in _EXCLUDED_PARTS for part in path.parts):
                continue
            yield path
    # Root-level shipping files have no/uncommon suffixes (Dockerfile,
    # .env.example), so yield them directly rather than via the suffix filter.
    for rel in _SHIPPING_ROOT_FILES:
        path = _REPO_ROOT / rel
        if path.is_file():
            yield path


def test_no_pt_or_internal_path_leakage_in_shipping_code():
    leaks = []
    for path in _scanned_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        for line_no, line in enumerate(text.splitlines(), start=1):
            for pattern in _FORBIDDEN:
                if pattern.search(line):
                    rel = path.relative_to(_REPO_ROOT)
                    leaks.append(f"{rel}:{line_no}: {line.strip()}")
    assert not leaks, "Generic-ship leak(s) found:\n" + "\n".join(leaks)
