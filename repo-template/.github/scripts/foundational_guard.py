#!/usr/bin/env python3
"""Foundational-policy CI guard (L2 protection layer).

Blocks a pull request whose diff either:
  (a) deletes a policy file that declares `foundational: true` in its
      YAML frontmatter, or
  (b) empties the `provides:` capability list of a still-foundational
      policy file.

Runs as a GitHub Actions check inside a diocese policy repo. It is
vendored into that repo (copied from the PolicyCodex `repo-template/`), so
it stays dependency-light and self-contained: it does NOT import any
PolicyCodex package. The only third-party dependency is PyYAML, installed
by the workflow.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass

import yaml

_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def parse_frontmatter(text):
    """Return a markdown document's YAML frontmatter as a dict.

    Returns {} when text is None, has no frontmatter block, or the block
    is not a YAML mapping. The guard fails open on unparseable frontmatter
    rather than crashing the CI run; the app's L3 startup check is the
    backstop for invalid bundles.
    """
    if not text:
        return {}
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}
    try:
        fm = yaml.safe_load(m.group(1))
    except yaml.YAMLError:
        return {}
    return fm if isinstance(fm, dict) else {}


def is_foundational(fm):
    return bool(fm.get("foundational"))


def provides_of(fm):
    value = fm.get("provides")
    return value if isinstance(value, list) else []


@dataclass(frozen=True)
class Change:
    path: str
    change_type: str  # "added" | "modified" | "deleted" | "renamed"
    base_frontmatter: dict
    head_frontmatter: dict


def find_violations(changes):
    """Return human-readable violation messages for a list of Change. Empty = OK."""
    violations = []
    for ch in changes:
        if ch.change_type == "deleted" and is_foundational(ch.base_frontmatter):
            violations.append(
                f"PR deletes foundational policy file: {ch.path}. Foundational "
                f"policies supply app configuration and cannot be deleted through "
                f"a PR. Soft-deprecate the affected entries instead."
            )
        elif ch.change_type == "modified" and is_foundational(ch.base_frontmatter):
            if provides_of(ch.base_frontmatter) and not provides_of(ch.head_frontmatter):
                violations.append(
                    f"PR empties the 'provides:' list of foundational policy: "
                    f"{ch.path}. Removing a declared capability breaks dependents."
                )
    return violations


def _show(ref, path):
    """Return file content at ref:path, or None if it does not exist there."""
    try:
        return subprocess.run(
            ["git", "show", f"{ref}:{path}"],
            check=True, capture_output=True, text=True,
        ).stdout
    except subprocess.CalledProcessError:
        return None


_STATUS = {"A": "added", "M": "modified", "D": "deleted", "R": "renamed"}
# T (type-change) and U (unmerged) fall through to "modified", which is safe:
# the guard still reads both base and head frontmatter and evaluates correctly.
# C (copy) cannot appear because the diff uses -M only (no -C).


def collect_changes(base_sha, head_sha):
    """Build the Change list for every changed markdown file in base..head."""
    diff = subprocess.run(
        ["git", "diff", "--name-status", "-M", base_sha, head_sha],
        check=True, capture_output=True, text=True,
    ).stdout
    changes = []
    for line in diff.splitlines():
        parts = line.split("\t")
        code = parts[0][0]  # first char: A / M / D / R
        change_type = _STATUS.get(code, "modified")
        old_path = parts[1]
        new_path = parts[-1]  # same as old_path except for renames
        if not new_path.endswith(".md"):
            continue
        base_text = None if code == "A" else _show(base_sha, old_path)
        head_text = None if code == "D" else _show(head_sha, new_path)
        changes.append(Change(
            path=new_path,
            change_type=change_type,
            base_frontmatter=parse_frontmatter(base_text),
            head_frontmatter=parse_frontmatter(head_text),
        ))
    return changes


def main():
    base = os.environ.get("BASE_SHA")
    head = os.environ.get("HEAD_SHA")
    if not base or not head:
        print("foundational-guard: BASE_SHA and HEAD_SHA must be set.", file=sys.stderr)
        return 2
    violations = find_violations(collect_changes(base, head))
    if violations:
        print("Foundational-policy guard FAILED:", file=sys.stderr)
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        return 1
    print("Foundational-policy guard passed: no protected deletions or emptied capabilities.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
