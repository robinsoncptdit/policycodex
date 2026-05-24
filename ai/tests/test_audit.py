"""Tests for ai.audit.to_audit_yaml (AI-07: confidence audit sidecar emitter)."""
import json
from pathlib import Path

import pytest
import yaml

from ai.audit import CONFIDENCE_FIELD_ORDER, to_audit_yaml


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
    assert "owner_role" not in doc          # only inside confidence map
    assert "retention_period_years" not in doc
    assert "long body text" not in md
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
