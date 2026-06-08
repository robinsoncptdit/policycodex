"""Generic per-policy inventory extraction (AI-10).

The shipping counterpart to spike/extract.py's single-document metadata
extraction: given one governing document's text plus the diocese's taxonomy,
return the structured per-policy metadata dict that ai/emit.py and ai/audit.py
turn into policies/<slug>.md + policies/<slug>.audit.yaml.

Diocese-agnostic ("the diocese", never a named diocese) and routed through
ai.provider.LLMProvider, so it is unit-testable without a network call and
ships generic per the project's "ship generic, never PT-flavored" rule.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from ai.provider import LLMProvider

# Output budget per policy; mirrors spike/extract.py's max_tokens.
EXTRACTION_MAX_TOKENS = 2048

# Cap injected document text so the prompt stays within budget. A very long
# policy is truncated here; chunked extraction is a post-DISC item. Held a hair
# under 50k so the injected text plus the static prompt never exceeds budget.
MAX_DOCUMENT_CHARS = 49000

_PROMPT_HEADER = """\
You are a policy librarian for a Catholic diocese. You read a single
governing document (policy, procedure, or by-law) and extract structured
metadata. Be conservative. If a field is not stated or strongly implied
in the text, leave it null and lower your confidence.

"""

_PROMPT_TAXONOMY_GUIDANCE = """\
When extracting `category` and `suggested_chapter_section_item`, PREFER
values that align with the diocese taxonomy above. Map your category
choice to one of the schema-defined category values (Finance, HR, IT,
Safe Environment, Schools, Worship, Parish Operations, Stewardship,
By-Laws, Communications, Risk, Other) but choose the one whose meaning
most closely matches the relevant classification or retention group.
For `suggested_chapter_section_item`, use a chapter.section.item address
(e.g., 5.2.8) where the chapter aligns with the classification axis or
retention group most relevant to the policy. If the policy doesn't
cleanly fit any provided category or group, use your best judgment and
note this in `notes`.

"""

_PROMPT_SCHEMA = """\
Output strictly as JSON, matching this schema:

{
  "title": "<the policy's title as best you can identify>",
  "summary": "<one sentence describing what this policy governs>",
  "category": "<one of: Finance, HR, IT, Safe Environment, Schools, Worship, Parish Operations, Stewardship, By-Laws, Communications, Risk, Other>",
  "category_confidence": "<low | medium | high>",
  "owner_role": "<best guess at the diocesan role responsible: CFO, HR Director, IT Director, Vicar General, Chancellor, Superintendent of Schools, Director of Safe Environment, etc.>",
  "owner_role_confidence": "<low | medium | high>",
  "effective_date": "<ISO date if stated, else null>",
  "effective_date_confidence": "<low | medium | high>",
  "last_review_date": "<ISO date if stated, else null>",
  "last_review_date_confidence": "<low | medium | high>",
  "next_review_date": "<ISO date if stated, or computed from effective date plus implied cadence, else null>",
  "next_review_date_confidence": "<low | medium | high>",
  "retention_period_years": "<integer years if stated or inferable from records-management norms, else null>",
  "retention_period_confidence": "<low | medium | high>",
  "suggested_chapter_section_item": "<chapter.section.item address using chapter.section.item numbering, e.g., 5.2.8>",
  "address_confidence": "<low | medium | high>",
  "version_stamp": "1.0",
  "notes": "<anything ambiguous, missing, or concerning that a human reviewer should know>"
}

Document text follows. Output only the JSON object.
---
"""


class InventoryExtractionError(ValueError):
    """The model output could not be read as a per-policy extraction."""


def build_taxonomy_section(taxonomy: dict[str, Any]) -> str:
    """Render the diocese taxonomy into a prompt section.

    Lists all top-level classifications and one example retention row per
    (group, sub_group) pair, in YAML order, keeping the prompt budget bounded
    while covering every department. Diocese-agnostic: no diocese name.
    """
    lines = ["## Diocese taxonomy reference", ""]
    lines.append("Top-level data classifications:")
    for entry in taxonomy.get("classifications", []):
        lines.append(f"- {entry['id']}: {entry['name']}")
    lines.append("")
    lines.append("Retention schedule (one example per group/sub-group):")
    seen: set[tuple[str, str | None]] = set()
    for row in taxonomy.get("retention_schedule", []):
        pair = (row["group"], row.get("sub_group"))
        if pair in seen:
            continue
        seen.add(pair)
        label = row["group"]
        if row.get("sub_group"):
            label = f"{label} / {row['sub_group']}"
        lines.append(f"- {label}: {row['type']} -> {row['retention']}")
    lines.append("")
    return "\n".join(lines)


def build_inventory_prompt(taxonomy: dict[str, Any] | None) -> str:
    """Assemble the full extraction prompt.

    When `taxonomy` is None (no foundational bundle present), the taxonomy
    section and its guidance paragraph are omitted; extraction still runs but
    without retention/address grounding.
    """
    if taxonomy:
        return (
            _PROMPT_HEADER
            + build_taxonomy_section(taxonomy)
            + "\n"
            + _PROMPT_TAXONOMY_GUIDANCE
            + _PROMPT_SCHEMA
        )
    return _PROMPT_HEADER + _PROMPT_SCHEMA


def parse_inventory_response(raw: str) -> dict[str, Any]:
    """Parse the model's text into an extraction dict, or raise InventoryExtractionError."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip().rstrip("`").strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise InventoryExtractionError(f"model did not return JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise InventoryExtractionError("model JSON was not an object")
    if not parsed.get("title"):
        raise InventoryExtractionError("model JSON missing required 'title'")
    return parsed


def extract_policy_metadata(
    provider: LLMProvider, document_text: str, taxonomy: dict[str, Any] | None
) -> dict[str, Any]:
    """Run the extraction prompt against a single document's text.

    Attaches the call's usage telemetry as the private ``_usage`` key (a plain
    dict), mirroring the ``_source_file`` convention: stripped from the policy
    markdown by ai/emit.py, surfaced in the audit sidecar by ai/audit.py.
    """
    prompt = build_inventory_prompt(taxonomy) + document_text[:MAX_DOCUMENT_CHARS]
    result = provider.complete(prompt, EXTRACTION_MAX_TOKENS)
    metadata = parse_inventory_response(result.text)
    metadata["_usage"] = asdict(result.usage)
    return metadata
