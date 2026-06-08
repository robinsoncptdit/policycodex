"""Unit tests for the generic per-policy inventory extraction (AI-10)."""
import json
from dataclasses import asdict

import pytest

from ai.inventory_extract import (
    EXTRACTION_MAX_TOKENS,
    MAX_DOCUMENT_CHARS,
    InventoryExtractionError,
    build_inventory_prompt,
    build_taxonomy_section,
    extract_policy_metadata,
    parse_inventory_response,
)
from ai.provider import CompletionResult, Usage

USAGE = Usage("fake", "m", 11, 22, "2026-06-08T00:00:00+00:00")

VALID_EXTRACTION = {
    "title": "IT Acceptable Use Policy",
    "summary": "Governs staff use of diocesan computing resources.",
    "category": "IT",
    "category_confidence": "high",
    "owner_role": "IT Director",
    "owner_role_confidence": "high",
    "effective_date": "2021-01-01",
    "retention_period_years": 7,
    "suggested_chapter_section_item": "5.2.8",
    "address_confidence": "medium",
    "version_stamp": "1.0",
    "notes": "",
}

TAXONOMY = {
    "classifications": [
        {"id": "finance", "name": "Finance"},
        {"id": "it", "name": "Information Technology"},
    ],
    "retention_schedule": [
        {"group": "Financial Records", "type": "Audited statements", "retention": "Permanent"},
        {"group": "IT Records", "sub_group": "Access logs", "type": "Auth logs", "retention": "1 year"},
    ],
}


class FakeProvider:
    """Stands in for ai.provider.LLMProvider. Returns canned text + usage."""
    def __init__(self, text, usage=USAGE):
        self._text = text
        self._usage = usage
        self.last_prompt = None
        self.last_max_tokens = None

    def complete(self, prompt, max_tokens):
        self.last_prompt = prompt
        self.last_max_tokens = max_tokens
        return CompletionResult(text=self._text, usage=self._usage)


def test_parse_plain_json():
    assert parse_inventory_response(json.dumps(VALID_EXTRACTION)) == VALID_EXTRACTION


def test_parse_strips_code_fences():
    raw = "```json\n" + json.dumps(VALID_EXTRACTION) + "\n```"
    assert parse_inventory_response(raw) == VALID_EXTRACTION


def test_parse_rejects_non_json():
    with pytest.raises(InventoryExtractionError, match="JSON"):
        parse_inventory_response("this is not json")


def test_parse_rejects_non_object():
    with pytest.raises(InventoryExtractionError, match="object"):
        parse_inventory_response(json.dumps(["a", "b"]))


def test_parse_requires_title():
    no_title = {k: v for k, v in VALID_EXTRACTION.items() if k != "title"}
    with pytest.raises(InventoryExtractionError, match="title"):
        parse_inventory_response(json.dumps(no_title))


def test_taxonomy_section_is_generic():
    section = build_taxonomy_section(TAXONOMY)
    # Ship-generic: no diocese name leaks into the prompt.
    assert "Pensacola" not in section
    assert "PT" not in section
    assert "finance: Finance" in section
    assert "Financial Records: Audited statements -> Permanent" in section
    # sub_group rows render "group / sub_group".
    assert "IT Records / Access logs: Auth logs -> 1 year" in section


def test_taxonomy_section_dedupes_group_pairs():
    taxonomy = {
        "classifications": [],
        "retention_schedule": [
            {"group": "G", "type": "A", "retention": "1 year"},
            {"group": "G", "type": "B", "retention": "2 years"},
        ],
    }
    section = build_taxonomy_section(taxonomy)
    # One example per (group, sub_group) pair: only the first row of group G appears.
    assert section.count("G: ") == 1


def test_taxonomy_section_keeps_distinct_sub_groups():
    # The dedup key is (group, sub_group): a sub_group row is a DIFFERENT pair
    # from the bare-group row, so both must survive.
    taxonomy = {
        "classifications": [],
        "retention_schedule": [
            {"group": "G", "type": "A", "retention": "1 year"},
            {"group": "G", "sub_group": "S", "type": "B", "retention": "2 years"},
        ],
    }
    section = build_taxonomy_section(taxonomy)
    assert "G: A -> 1 year" in section
    assert "G / S: B -> 2 years" in section


def test_build_prompt_without_taxonomy_omits_section():
    prompt = build_inventory_prompt(None)
    assert "taxonomy reference" not in prompt
    assert "Output strictly as JSON" in prompt


def test_build_prompt_with_taxonomy_includes_section():
    prompt = build_inventory_prompt(TAXONOMY)
    assert "taxonomy reference" in prompt
    assert "Output strictly as JSON" in prompt


def test_extract_policy_metadata_calls_provider_and_parses():
    provider = FakeProvider(json.dumps(VALID_EXTRACTION))
    result = extract_policy_metadata(provider, "document body text", TAXONOMY)
    # All parsed fields survive; _usage is attached on top.
    assert {k: v for k, v in result.items() if k != "_usage"} == VALID_EXTRACTION
    assert provider.last_max_tokens == EXTRACTION_MAX_TOKENS
    assert "document body text" in provider.last_prompt
    assert "taxonomy reference" in provider.last_prompt


def test_extract_policy_metadata_attaches_usage():
    provider = FakeProvider(json.dumps(VALID_EXTRACTION))
    result = extract_policy_metadata(provider, "body", TAXONOMY)
    assert result["_usage"] == asdict(USAGE)


def test_extract_truncates_long_document():
    provider = FakeProvider(json.dumps(VALID_EXTRACTION))
    static_x = build_inventory_prompt(None).count("x")
    extract_policy_metadata(provider, "x" * 100000, None)
    # The 100k-char document is truncated to exactly MAX_DOCUMENT_CHARS; the
    # only other "x" chars come from the static prompt scaffold.
    assert provider.last_prompt.count("x") == MAX_DOCUMENT_CHARS + static_x
