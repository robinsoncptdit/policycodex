"""Step registry and navigation helpers for the onboarding wizard (APP-08).

This is the single source of step identity and order. Views and templates
read it; APP-09 through APP-16 add per-screen content keyed by slug without
touching navigation.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Step:
    slug: str
    title: str


STEPS: tuple[Step, ...] = (
    Step("github-repo", "GitHub repository"),
    Step("address-scheme", "Address scheme"),
    Step("versioning", "Versioning convention"),
    Step("reviewer-roles", "Reviewer roles"),
    Step("retention", "Retention defaults"),
    Step("llm-provider", "LLM provider"),
    Step("retention-policy", "Retention policy"),
)

_BY_SLUG = {s.slug: s for s in STEPS}


def first_step() -> Step:
    return STEPS[0]


def get_step(slug: str) -> Step | None:
    return _BY_SLUG.get(slug)


def index_of(slug: str) -> int | None:
    step = _BY_SLUG.get(slug)
    return None if step is None else STEPS.index(step)


def next_step(slug: str) -> Step | None:
    idx = index_of(slug)
    if idx is None or idx + 1 >= len(STEPS):
        return None
    return STEPS[idx + 1]


def prev_step(slug: str) -> Step | None:
    idx = index_of(slug)
    if idx is None or idx == 0:
        return None
    return STEPS[idx - 1]


def is_last(slug: str) -> bool:
    return index_of(slug) == len(STEPS) - 1
