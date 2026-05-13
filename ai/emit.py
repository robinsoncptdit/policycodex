"""Markdown + YAML front-matter emitter for AI-extracted policy metadata.

Given a single AI-extraction dict (the per-PDF JSON shape produced by the
inventory pass, see ``spike/outputs/*.json``), produce a markdown string with a
stable YAML front-matter block followed by a human-readable body. The caller
decides where to write the result.

Design notes:

- Front-matter keys emit in a fixed canonical order (see
  ``FRONTMATTER_KEY_ORDER``). Any extra non-canonical keys appear after the
  canonical ones, alphabetized, so downstream diffs stay stable across runs.
- Confidence fields (``*_confidence`` and ``address_confidence``) are stripped:
  per the v0.1 spec, confidence scores live in a separate audit file, not in
  the human-readable markdown.
- Body-only fields (``summary``, ``notes``) and spike-internal metadata
  (``_source_file``) are excluded from the front matter.
- Missing canonical keys still appear in the output, with value ``null``, so
  consumers can rely on key presence regardless of upstream gaps.
- YAML is emitted with ``yaml.safe_dump`` and ``default_flow_style=False`` for
  block-style, exploit-safe output.
"""
from __future__ import annotations

from typing import Any

import yaml


# Canonical order of front-matter keys. Any other (non-confidence, non-body,
# non-private) keys are appended alphabetically.
FRONTMATTER_KEY_ORDER: tuple[str, ...] = (
    "title",
    "category",
    "owner_role",
    "effective_date",
    "last_review_date",
    "next_review_date",
    "retention_period_years",
    "suggested_chapter_section_item",
    "version_stamp",
)

# Fields that belong in the body, not the front matter.
_BODY_FIELDS: frozenset[str] = frozenset({"summary", "notes"})

# Spike-internal / private fields excluded from output entirely.
_PRIVATE_FIELDS: frozenset[str] = frozenset({"_source_file"})

# Confidence fields whose names don't end in "_confidence" but still belong to
# the audit file, not the policy markdown.
_EXTRA_CONFIDENCE_FIELDS: frozenset[str] = frozenset({"address_confidence"})

# Front-matter values that should always emit as quoted strings (so values like
# "1.0" don't round-trip into floats).
_FORCE_QUOTED_STRING: frozenset[str] = frozenset(
    {"version_stamp", "suggested_chapter_section_item"}
)


def _is_confidence_key(key: str) -> bool:
    return key.endswith("_confidence") or key in _EXTRA_CONFIDENCE_FIELDS


def _build_frontmatter(extraction: dict[str, Any]) -> dict[str, Any]:
    """Return a dict shaped for YAML emission (canonical keys first, extras after)."""
    # Filter out anything that doesn't belong in the front matter.
    filtered: dict[str, Any] = {
        k: v
        for k, v in extraction.items()
        if k not in _BODY_FIELDS
        and k not in _PRIVATE_FIELDS
        and not _is_confidence_key(k)
    }

    # Build the canonical-first dict.
    ordered: dict[str, Any] = {}
    for key in FRONTMATTER_KEY_ORDER:
        ordered[key] = filtered.pop(key, None)

    # Any remaining keys: append alphabetized for stability.
    for key in sorted(filtered):
        ordered[key] = filtered[key]

    return ordered


def _dump_yaml(frontmatter: dict[str, Any]) -> str:
    """Emit the frontmatter dict as YAML in canonical order, with safe defaults."""
    # Force-quote selected values so they don't round-trip through YAML as
    # numbers (e.g. version_stamp "1.0" must stay a string).
    coerced: dict[str, Any] = {}
    for key, value in frontmatter.items():
        if key in _FORCE_QUOTED_STRING and value is not None:
            coerced[key] = _QuotedString(str(value))
        else:
            coerced[key] = value

    # sort_keys=False preserves our explicit canonical ordering.
    return yaml.safe_dump(
        coerced,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
    )


class _QuotedString(str):
    """Marker subclass of str used to request single-quoted YAML emission."""


def _quoted_string_representer(dumper: yaml.SafeDumper, data: _QuotedString):
    return dumper.represent_scalar("tag:yaml.org,2002:str", str(data), style="'")


yaml.SafeDumper.add_representer(_QuotedString, _quoted_string_representer)


def _build_body(extraction: dict[str, Any]) -> str:
    """Render the human-readable body from summary (+ optional notes)."""
    parts: list[str] = []
    title = extraction.get("title")
    if title:
        parts.append(f"# {title}\n")

    summary = extraction.get("summary")
    if summary:
        parts.append(str(summary).strip() + "\n")

    notes = extraction.get("notes")
    if notes:
        parts.append("## Notes\n")
        parts.append(str(notes).strip() + "\n")

    return "\n".join(parts)


def to_markdown(extraction: dict[str, Any]) -> str:
    """Convert an AI-extraction dict to a markdown file body with YAML front matter.

    The output begins with a ``---`` delimiter, contains a YAML front-matter
    block emitting the canonical schema (with ``null`` for missing keys), is
    closed by another ``---`` delimiter, and is followed by a markdown body
    rendered from the ``summary`` and optional ``notes`` fields.

    Confidence fields are stripped (they belong in a separate audit file per
    the v0.1 spec). The full canonical schema always appears, so downstream
    consumers can rely on key presence.
    """
    frontmatter = _build_frontmatter(extraction)
    yaml_text = _dump_yaml(frontmatter)
    body = _build_body(extraction)

    # yaml.safe_dump already terminates with a newline.
    return f"---\n{yaml_text}---\n\n{body}"
