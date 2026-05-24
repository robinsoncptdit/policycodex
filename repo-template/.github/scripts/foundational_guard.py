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
