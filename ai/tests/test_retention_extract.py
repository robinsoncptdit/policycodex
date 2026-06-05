"""Unit tests for the retention-bundle extraction (APP-15 / AI-13 work)."""
import json

import pytest

from ai.retention_extract import (
    RetentionExtractionError,
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
    """Stands in for ai.provider.LLMProvider. Returns canned text."""
    def __init__(self, text):
        self._text = text
        self.last_prompt = None
        self.last_max_tokens = None

    def complete(self, prompt, max_tokens):
        self.last_prompt = prompt
        self.last_max_tokens = max_tokens
        return self._text


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
    assert provider.last_max_tokens >= 8192
