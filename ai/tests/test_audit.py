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
