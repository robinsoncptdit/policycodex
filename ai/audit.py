"""Confidence and usage audit-sidecar emitter for AI-extracted policy metadata.

The inverse of ``ai/emit.py``: where ``emit.py`` strips every confidence
field out of the policy markdown, this module keeps only the confidence
scores and per-call usage telemetry (plus ``title`` and ``source_file`` for
traceability) and emits the YAML body of a ``<slug>.audit.yaml`` sidecar. The
caller decides where to write the result and how to derive the slug (see AI-10).

Per the v0.1 spec (line 99), confidence scores are recorded in a separate
audit file, never in the human-readable policy markdown.

Design notes:

- Canonical confidence fields (``CONFIDENCE_FIELD_ORDER``) always appear in
  the ``confidence:`` map, with value ``null`` when the extraction omits
  them, so audit diffs stay stable across runs.
- Any extra ``*_confidence`` keys not in the canonical set are appended
  alphabetized, so a new scored field is never silently dropped.
- Canonical usage fields (``USAGE_FIELD_ORDER``) always appear in the
  ``usage:`` map, read from the private ``_usage`` key, with value ``null``
  when absent, mirroring the confidence convention (AI-16).
- ``title`` and ``source_file`` are emitted as top-level identifying
  metadata (``source_file`` is read from the spike-internal ``_source_file``
  key); both are ``null`` when absent.
"""
from __future__ import annotations

from typing import Any

import yaml


# Canonical base field names (without the "_confidence" suffix), in a fixed
# order that mirrors ai/emit.py's FRONTMATTER_KEY_ORDER where the fields
# overlap. These always appear in the confidence map, null if missing.
CONFIDENCE_FIELD_ORDER: tuple[str, ...] = (
    "category",
    "owner_role",
    "effective_date",
    "last_review_date",
    "next_review_date",
    "retention_period",
    "address",
)

_CONFIDENCE_SUFFIX = "_confidence"


# Canonical order of the per-call usage telemetry (AI-16). Always emitted as a
# top-level `usage:` block; absent fields render null, mirroring the confidence
# map, so audit diffs stay stable across runs.
USAGE_FIELD_ORDER: tuple[str, ...] = (
    "provider",
    "model",
    "input_tokens",
    "output_tokens",
    "timestamp",
)


def _confidence_map(extraction: dict[str, Any]) -> dict[str, Any]:
    """Return the confidence sub-map: canonical fields first, extras appended."""
    result: dict[str, Any] = {}
    for base in CONFIDENCE_FIELD_ORDER:
        result[base] = extraction.get(f"{base}{_CONFIDENCE_SUFFIX}")

    canonical_keys = {f"{b}{_CONFIDENCE_SUFFIX}" for b in CONFIDENCE_FIELD_ORDER}
    extras = sorted(
        k
        for k in extraction
        if k.endswith(_CONFIDENCE_SUFFIX) and k not in canonical_keys
    )
    for key in extras:
        base = key[: -len(_CONFIDENCE_SUFFIX)]
        result[base] = extraction[key]
    return result


def _usage_map(extraction: dict[str, Any]) -> dict[str, Any]:
    """Return the usage sub-map: canonical fields in order, null when absent."""
    usage = extraction.get("_usage") or {}
    return {field: usage.get(field) for field in USAGE_FIELD_ORDER}


def to_audit_yaml(extraction: dict[str, Any]) -> str:
    """Convert an AI-extraction dict to the YAML body of an audit sidecar.

    The output is a block-style YAML document with top-level ``title`` and
    ``source_file`` keys followed by a ``confidence:`` map and a ``usage:``
    map. Confidence scores and usage telemetry are the only per-field data
    carried over from the extraction; all policy content lives in the markdown
    emitted by ``ai/emit.py``.
    """
    doc: dict[str, Any] = {
        "title": extraction.get("title"),
        "source_file": extraction.get("_source_file"),
        "confidence": _confidence_map(extraction),
        "usage": _usage_map(extraction),
    }
    return yaml.safe_dump(
        doc,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
    )
