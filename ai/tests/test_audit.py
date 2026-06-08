"""Tests for ai.audit.to_audit_yaml (AI-07: confidence audit sidecar emitter)."""
import json
from pathlib import Path

import pytest
import yaml

from ai.audit import CONFIDENCE_FIELD_ORDER, USAGE_FIELD_ORDER, to_audit_yaml


SPIKE_OUTPUTS = Path(__file__).resolve().parents[2] / "spike" / "outputs"


def _load(md: str) -> dict:
    return yaml.safe_load(md)


def test_canonical_confidence_fields_collected():
    extraction = {
        "title": "T",
        "category": "Finance",
        "category_confidence": "high",
        "owner_role_confidence": "medium",
        "effective_date_confidence": "low",
        "last_review_date_confidence": "high",
        "next_review_date_confidence": "low",
        "retention_period_confidence": "medium",
        "address_confidence": "high",
    }
    doc = _load(to_audit_yaml(extraction))
    assert doc["confidence"] == {
        "category": "high",
        "owner_role": "medium",
        "effective_date": "low",
        "last_review_date": "high",
        "next_review_date": "low",
        "retention_period": "medium",
        "address": "high",
    }


def test_missing_confidence_emits_null():
    extraction = {"title": "T", "category_confidence": "high"}
    doc = _load(to_audit_yaml(extraction))
    # every canonical field is present; the absent ones are null
    for base in CONFIDENCE_FIELD_ORDER:
        assert base in doc["confidence"]
    assert doc["confidence"]["category"] == "high"
    assert doc["confidence"]["owner_role"] is None


def test_title_and_source_file_top_level():
    extraction = {
        "title": "Internal Controls Policy",
        "_source_file": "101 Internal Controls.pdf",
        "category_confidence": "high",
    }
    doc = _load(to_audit_yaml(extraction))
    assert doc["title"] == "Internal Controls Policy"
    assert doc["source_file"] == "101 Internal Controls.pdf"


def test_title_and_source_file_null_when_absent():
    doc = _load(to_audit_yaml({"category_confidence": "high"}))
    assert doc["title"] is None
    assert doc["source_file"] is None


def test_non_confidence_fields_excluded():
    extraction = {
        "title": "T",
        "category": "Finance",
        "owner_role": "CFO",
        "summary": "long body text",
        "retention_period_years": 7,
        "category_confidence": "high",
    }
    md = to_audit_yaml(extraction)
    doc = _load(md)
    # No policy content leaks anywhere in the audit document.
    assert "summary" not in doc
    # owner_role is absent at top level; it appears in the confidence map only
    # as null here, because no owner_role_confidence key was supplied.
    assert "owner_role" not in doc
    assert doc["confidence"]["owner_role"] is None
    assert "retention_period_years" not in doc
    # Value fields must not leak into the rendered audit text at all.
    assert "long body text" not in md
    assert "CFO" not in md
    assert doc["confidence"]["category"] == "high"


def test_extra_confidence_keys_appended_alphabetized():
    extraction = {
        "category_confidence": "high",
        "zeta_confidence": "low",
        "alpha_confidence": "medium",
    }
    doc = _load(to_audit_yaml(extraction))
    keys = list(doc["confidence"].keys())
    # canonical order first, then extras alphabetized
    assert keys[: len(CONFIDENCE_FIELD_ORDER)] == list(CONFIDENCE_FIELD_ORDER)
    assert keys[len(CONFIDENCE_FIELD_ORDER):] == ["alpha", "zeta"]


def test_block_style_not_inline():
    md = to_audit_yaml({"title": "T", "category_confidence": "high"})
    assert "{" not in md          # block style, not inline {a: b}
    assert "\n" in md


def test_round_trip_spike_output():
    path = SPIKE_OUTPUTS / "101 Internal Controls.json"
    if not path.exists():
        pytest.skip("Spike output not present in this worktree")
    extraction = json.loads(path.read_text())
    doc = _load(to_audit_yaml(extraction))
    assert doc["title"] == extraction["title"]
    assert doc["source_file"] == extraction["_source_file"]
    assert doc["confidence"]["category"] == extraction["category_confidence"]
    assert doc["confidence"]["address"] == extraction["address_confidence"]


def test_empty_extraction_emits_all_nulls():
    """An empty dict still yields the full canonical schema, all null."""
    doc = _load(to_audit_yaml({}))
    assert doc["title"] is None
    assert doc["source_file"] is None
    assert list(doc["confidence"].keys()) == list(CONFIDENCE_FIELD_ORDER)
    assert all(v is None for v in doc["confidence"].values())


def test_non_string_confidence_value_passes_through():
    """Numeric confidence scores survive to YAML unchanged (provider may switch
    from low/medium/high strings to numbers)."""
    doc = _load(to_audit_yaml({"category_confidence": 0.95}))
    assert doc["confidence"]["category"] == 0.95


# ---------------------------------------------------------------------------
# AI-16: usage block tests
# ---------------------------------------------------------------------------

def test_usage_block_rendered_from_private_key():
    extraction = {
        "title": "T",
        "category_confidence": "high",
        "_usage": {
            "provider": "claude",
            "model": "claude-opus-4-8",
            "input_tokens": 4123,
            "output_tokens": 512,
            "timestamp": "2026-06-08T18:03:00+00:00",
        },
    }
    doc = _load(to_audit_yaml(extraction))
    assert doc["usage"] == {
        "provider": "claude",
        "model": "claude-opus-4-8",
        "input_tokens": 4123,
        "output_tokens": 512,
        "timestamp": "2026-06-08T18:03:00+00:00",
    }


def test_usage_block_all_null_when_absent():
    doc = _load(to_audit_yaml({"title": "T", "category_confidence": "high"}))
    assert list(doc["usage"].keys()) == list(USAGE_FIELD_ORDER)
    assert all(v is None for v in doc["usage"].values())


def test_usage_key_not_leaked_as_top_level_underscore():
    doc = _load(to_audit_yaml({"_usage": {"provider": "claude"}}))
    # The private key itself never appears; only the rendered usage block.
    assert "_usage" not in doc
    assert doc["usage"]["provider"] == "claude"
