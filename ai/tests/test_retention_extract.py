"""Unit tests for the retention-bundle extraction (APP-15 / AI-13 work)."""
import json

import pytest
import yaml

from ai.provider import CompletionResult, Usage
from ai.retention_extract import (
    EXTRACTION_MAX_TOKENS,
    RetentionExtractionError,
    build_data_yaml,
    extract_retention_bundle,
    parse_bundle_response,
)

VALID_BUNDLE = {
    "classifications": [
        {"id": "administrative", "name": "Administrative"},
        {"id": "financial", "name": "Financial"},
    ],
    "classifications_confidence": "high",
    "retention_schedule": [
        {"group": "Administrative Records", "type": "General correspondence",
         "retention": "3 years", "medium": "Paper/Elec", "retained_at": "On-site"},
        {"group": "Financial Records", "type": "Audited statements",
         "retention": "Permanent"},
    ],
    "retention_schedule_confidence": "medium",
}


class FakeProvider:
    """Stands in for ai.provider.LLMProvider. Returns canned text + usage."""
    def __init__(self, text):
        self._text = text
        self.last_prompt = None
        self.last_max_tokens = None

    def complete(self, prompt, max_tokens):
        self.last_prompt = prompt
        self.last_max_tokens = max_tokens
        return CompletionResult(
            text=self._text,
            usage=Usage("fake", "m", 1, 2, "2026-06-08T00:00:00+00:00"),
        )


def test_parse_plain_json():
    raw = json.dumps(VALID_BUNDLE)
    assert parse_bundle_response(raw) == VALID_BUNDLE


def test_parse_strips_code_fences():
    raw = "```json\n" + json.dumps(VALID_BUNDLE) + "\n```"
    assert parse_bundle_response(raw) == VALID_BUNDLE


def test_parse_rejects_non_json():
    with pytest.raises(RetentionExtractionError, match="JSON"):
        parse_bundle_response("this is not json")


def test_parse_rejects_missing_keys():
    with pytest.raises(RetentionExtractionError, match="classifications"):
        parse_bundle_response(json.dumps({"retention_schedule": []}))


def test_extract_calls_provider_and_parses():
    provider = FakeProvider(json.dumps(VALID_BUNDLE))
    result = extract_retention_bundle(provider, "PDF TEXT HERE")
    assert result == VALID_BUNDLE
    assert "PDF TEXT HERE" in provider.last_prompt
    assert provider.last_max_tokens == EXTRACTION_MAX_TOKENS


def test_build_data_yaml_round_trips():
    text = build_data_yaml(VALID_BUNDLE)
    loaded = yaml.safe_load(text)
    assert [c["id"] for c in loaded["classifications"]] == ["administrative", "financial"]
    assert loaded["retention_schedule"][0]["group"] == "Administrative Records"
    assert loaded["retention_schedule"][1]["retention"] == "Permanent"


def test_build_data_yaml_omits_blank_optional_keys():
    text = build_data_yaml(VALID_BUNDLE)
    loaded = yaml.safe_load(text)
    # Row 2 had no medium/retained_at/sub_group -> those keys are absent.
    assert set(loaded["retention_schedule"][1]) == {"group", "type", "retention"}


def test_build_data_yaml_rejects_row_missing_required_field():
    bad = {"classifications": [{"id": "x", "name": "X"}],
           "retention_schedule": [{"group": "G", "type": "T"}]}  # no retention
    with pytest.raises(RetentionExtractionError, match="retention"):
        build_data_yaml(bad)


def test_build_data_yaml_rejects_classification_missing_id():
    bad = {"classifications": [{"name": "X"}], "retention_schedule": []}
    with pytest.raises(RetentionExtractionError, match="id"):
        build_data_yaml(bad)


def test_extract_bundle_does_not_carry_usage():
    provider = FakeProvider(json.dumps(VALID_BUNDLE))
    result = extract_retention_bundle(provider, "PDF TEXT HERE")
    assert "_usage" not in result
    assert result == VALID_BUNDLE
