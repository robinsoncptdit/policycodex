"""Smoke tests for the eval harness."""
import json
from pathlib import Path

import pytest

from run_eval import EVAL_DIR, _eq, _int_eq, _iso_date_eq, run_eval

CATEGORY_EVAL = EVAL_DIR / "category_eval.jsonl"


def _load_rows():
    with CATEGORY_EVAL.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def test_eval_set_has_18_rows():
    rows = _load_rows()
    assert len(rows) == 18


def test_verified_rows_have_ground_truth():
    rows = _load_rows()
    for row in rows:
        if row["label_status"] == "verified":
            assert row["ground_truth_category"] is not None
        else:
            assert row["label_status"] == "needs_review"
            assert row["ground_truth_category"] is None


def test_offline_category_run_is_perfect():
    result = run_eval("category", "offline")
    # Verified rows are built from cached outputs, so offline run must score 1.0.
    # This is the harness-wiring sanity check, not a real baseline.
    assert result["scored"] > 0
    assert result["weighted_avg"] == 1.0
    assert result["failures"] == []
    assert result["passed"] is True


def test_offline_run_skips_needs_review_rows():
    result = run_eval("category", "offline")
    rows = _load_rows()
    expected_skipped = sum(1 for r in rows if r["label_status"] == "needs_review")
    assert result["skipped"] == expected_skipped
    assert result["scored"] + result["skipped"] == len(rows)


def test_per_field_threshold_used_for_pass_fail():
    from run_eval import FIELD_DISPATCH
    assert "threshold" in FIELD_DISPATCH["category"]
    assert FIELD_DISPATCH["category"]["threshold"] == 0.85


def test_threshold_boundary_passes_at_exact_value():
    from run_eval import _result_passed
    assert _result_passed(weighted_avg=0.85, threshold=0.85) is True
    assert _result_passed(weighted_avg=0.8499999, threshold=0.85) is False


def test_load_eval_set_rejects_unknown_label_status(tmp_path, monkeypatch):
    from run_eval import load_eval_set
    eval_file = tmp_path / "category_eval.jsonl"
    eval_file.write_text(
        '{"source_file": "x.pdf", "label_status": "maybe", "ground_truth_category": "HR"}\n'
    )
    monkeypatch.setattr("run_eval.EVAL_DIR", tmp_path)
    with pytest.raises(ValueError, match="label_status"):
        load_eval_set("category")


def test_load_eval_set_rejects_missing_required_keys(tmp_path, monkeypatch):
    from run_eval import load_eval_set
    eval_file = tmp_path / "category_eval.jsonl"
    eval_file.write_text('{"label_status": "verified", "ground_truth_category": "HR"}\n')
    monkeypatch.setattr("run_eval.EVAL_DIR", tmp_path)
    with pytest.raises(ValueError, match="source_file"):
        load_eval_set("category")


def test_load_eval_set_distinguishes_missing_vs_null_ground_truth(tmp_path, monkeypatch):
    from run_eval import load_eval_set
    eval_file = tmp_path / "category_eval.jsonl"
    eval_file.write_text('{"source_file": "x.pdf", "label_status": "needs_review"}\n')
    monkeypatch.setattr("run_eval.EVAL_DIR", tmp_path)
    with pytest.raises(ValueError, match="ground_truth_category"):
        load_eval_set("category")


def test_run_eval_isolates_per_row_fetch_failures(tmp_path, monkeypatch):
    """A single bad row must not discard the rest of the run."""
    from run_eval import run_eval
    eval_file = tmp_path / "category_eval.jsonl"
    eval_file.write_text(
        '{"source_file": "good.pdf", "label_status": "verified", "ground_truth_category": "HR"}\n'
        '{"source_file": "missing.pdf", "label_status": "verified", "ground_truth_category": "HR"}\n'
        '{"source_file": "good2.pdf", "label_status": "verified", "ground_truth_category": "HR"}\n'
    )
    monkeypatch.setattr("run_eval.EVAL_DIR", tmp_path)

    def fake_fetch(source_file):
        if source_file == "missing.pdf":
            raise FileNotFoundError(source_file)
        return {"category": "HR"}

    monkeypatch.setattr("run_eval.get_offline_extraction", fake_fetch)

    result = run_eval("category", "offline")
    assert result["scored"] == 2
    assert result["errored"] == 1
    assert result["weighted_avg"] == 1.0
    assert len(result["errors"]) == 1
    assert result["errors"][0][0] == "missing.pdf"


def test_eq_happy_unhappy_null():
    assert _eq("HR", "HR") is True
    assert _eq("HR", "Finance") is False
    assert _eq(None, None) is True
    assert _eq(None, "HR") is False
    assert _eq("HR", None) is False


def test_int_eq_happy_unhappy_null():
    assert _int_eq(7, 7) is True
    assert _int_eq(7, "7") is True
    assert _int_eq(7, 8) is False
    assert _int_eq(None, None) is True
    assert _int_eq(None, 7) is False
    assert _int_eq(7, None) is False
    assert _int_eq("seven", 7) is False


def test_iso_date_eq_happy_unhappy_null():
    assert _iso_date_eq("2024-01-01", "2024-01-01") is True
    assert _iso_date_eq("2024-01-01", " 2024-01-01 ") is True
    assert _iso_date_eq("2024-01-01", "2024-01-02") is False
    assert _iso_date_eq(None, None) is True
    assert _iso_date_eq(None, "2024-01-01") is False
    assert _iso_date_eq("2024-01-01", None) is False
