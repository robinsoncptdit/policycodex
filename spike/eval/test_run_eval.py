"""Smoke tests for the eval harness."""
import json
from pathlib import Path

from run_eval import EVAL_DIR, run_eval

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
            assert row["human_score"] == 1.0
        else:
            assert row["label_status"] == "needs_review"
            assert row["ground_truth_category"] is None
            assert row["human_score"] < 1.0


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
