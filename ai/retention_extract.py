"""Extract a foundational retention bundle (classifications + retention
schedule) from a diocese's retention-policy document.

Distinct from spike/extract.py's single-policy metadata extraction: this
reads ONE source-of-truth document and returns the structured data that
becomes policies/document-retention/data.yaml (APP-15). Provider-agnostic
via ai.provider.LLMProvider, so it is unit-testable without a network call.
"""
from __future__ import annotations

import json
from typing import Any

import yaml

from ai.provider import LLMProvider

# Generous output budget: a real schedule can run to a few hundred rows.
# A single completion may still truncate; that is a known v0.1 limitation.
EXTRACTION_MAX_TOKENS = 8192

RETENTION_BUNDLE_PROMPT = """\
You are a records-management archivist for a Catholic diocese. You are given
the full text of the diocese's Document Retention Policy. Extract two
independent structures:

1. classifications: the top-level data classifications the policy defines
   (often a "Section 3.0" or similar). Each has a stable lowercase slug `id`
   (ascii, words joined by hyphens) and a human `name`.
2. retention_schedule: every row of the record-retention schedule (often an
   "Appendix A"). Each row has a `group`, a record `type`, and a `retention`
   value. `retention` is free text, copied verbatim (e.g. "Permanent",
   "7 years", "Termination + 4 years"). Optional per row: `sub_group`,
   `medium`, `retained_at`.

Be faithful to the document. Do not invent rows or classifications. Copy
retention values verbatim. Output STRICTLY one JSON object, no prose:

{
  "classifications": [{"id": "<slug>", "name": "<name>"}],
  "classifications_confidence": "<low | medium | high>",
  "retention_schedule": [
    {"group": "<group>", "sub_group": "<or omit>", "type": "<record type>",
     "retention": "<verbatim>", "medium": "<or omit>", "retained_at": "<or omit>"}
  ],
  "retention_schedule_confidence": "<low | medium | high>"
}

Document text follows. Output only the JSON object.
---
"""

_REQUIRED_KEYS = ("classifications", "retention_schedule")


class RetentionExtractionError(ValueError):
    """The model output could not be read as a retention bundle."""


def parse_bundle_response(raw: str) -> dict[str, Any]:
    """Parse the model's text into a bundle dict, or raise RetentionExtractionError."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip().rstrip("`").strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RetentionExtractionError(f"model did not return JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise RetentionExtractionError("model JSON was not an object")
    for key in _REQUIRED_KEYS:
        if key not in parsed:
            raise RetentionExtractionError(f"model JSON missing required key: {key}")
    return parsed


def extract_retention_bundle(provider: LLMProvider, document_text: str) -> dict[str, Any]:
    """Run the extraction prompt against the retention document text."""
    prompt = RETENTION_BUNDLE_PROMPT + document_text[:50000]
    raw = provider.complete(prompt, EXTRACTION_MAX_TOKENS)
    return parse_bundle_response(raw)
