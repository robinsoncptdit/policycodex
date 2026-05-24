"""Retention gap detection for the policy catalog (AI-13).

A policy is a "retention gap" when its type (the `category` frontmatter
field) is not represented in the diocese's foundational retention bundle.
"Represented" means the category matches one of the bundle's
`classifications` by `id` or `name`, case-insensitive. The free-text
`retention_schedule` rows are not used for matching in v0.1 (see the
AI-13 design doc).

Django-free, mirroring ai/taxonomy_loader.py, so the catalog view and any
future batch pass can share it.
"""
from __future__ import annotations

from typing import Iterable


def known_types(classifications) -> set[str]:
    """Return the casefolded set of classification ids and names.

    Accepts the `classifications` list from a bundle data.yaml (a list of
    {id, name} mappings). Non-mapping entries and falsy values are skipped.
    Deprecated classifications are included: a deprecated id stays valid for
    existing references per the foundational-policy design.
    """
    known: set[str] = set()
    for entry in classifications or []:
        if not isinstance(entry, dict):
            continue
        for key in ("id", "name"):
            value = entry.get(key)
            if value:
                known.add(str(value).strip().casefold())
    return known


def is_gap(category, known: set[str]) -> bool:
    """True when `category` is missing/blank or not in `known`."""
    if not category or not str(category).strip():
        return True
    return str(category).strip().casefold() not in known


def find_gaps(items: Iterable[tuple], classifications) -> list:
    """Return the keys from `items` whose category is a gap.

    `items` is an iterable of (key, category) pairs; order is preserved.
    """
    known = known_types(classifications)
    return [key for key, category in items if is_gap(category, known)]
