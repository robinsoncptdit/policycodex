"""
PolicyCodex eval harness for the monolithic extraction prompt.

Runs a labeled eval set for a single extracted field against the
current monolithic prompt (live mode) or against cached spike outputs
(offline mode). Used to detect regressions when AI-11 (taxonomy
injection) and AI-12 (retention reference injection) modify prompt
context.

Usage:
    python run_eval.py category --offline
    python run_eval.py category --live
"""
import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable

EVAL_DIR = Path(__file__).resolve().parent
SPIKE_DIR = EVAL_DIR.parent
OUTPUTS_DIR = SPIKE_DIR / "outputs"
INPUTS_DIR = SPIKE_DIR / "inputs"

def _result_passed(weighted_avg: float, threshold: float) -> bool:
    return weighted_avg >= threshold


def _eq(expected: Any, actual: Any) -> bool:
    return expected == actual


def _int_eq(expected: Any, actual: Any) -> bool:
    if expected is None or actual is None:
        return expected == actual
    try:
        return int(expected) == int(actual)
    except (TypeError, ValueError):
        return False


def _iso_date_eq(expected: Any, actual: Any) -> bool:
    if expected is None or actual is None:
        return expected == actual
    return str(expected).strip() == str(actual).strip()


# Per-field config: the extraction key in the JSON output, the ground-truth
# key in the eval JSONL, and the comparator. AI-05 and AI-06 add rows here.
FIELD_DISPATCH: dict[str, dict[str, Any]] = {
    "category": {
        "extracted_key": "category",
        "ground_truth_key": "ground_truth_category",
        "compare": _eq,
        "threshold": 0.85,
    },
    "owner_role": {
        "extracted_key": "owner_role",
        "ground_truth_key": "ground_truth_owner_role",
        "compare": _eq,
        "threshold": 0.85,
    },
    "effective_date": {
        "extracted_key": "effective_date",
        "ground_truth_key": "ground_truth_effective_date",
        "compare": _iso_date_eq,
        "threshold": 0.85,
    },
    "last_review_date": {
        "extracted_key": "last_review_date",
        "ground_truth_key": "ground_truth_last_review_date",
        "compare": _iso_date_eq,
        "threshold": 0.85,
    },
    "retention_period_years": {
        "extracted_key": "retention_period_years",
        "ground_truth_key": "ground_truth_retention_period_years",
        "compare": _int_eq,
        "threshold": 0.85,
    },
    "suggested_chapter_section_item": {
        "extracted_key": "suggested_chapter_section_item",
        "ground_truth_key": "ground_truth_suggested_chapter_section_item",
        "compare": _eq,
        "threshold": 0.85,
    },
}


def load_eval_set(field: str) -> list[dict]:
    path = EVAL_DIR / f"{field}_eval.jsonl"
    if not path.exists():
        raise FileNotFoundError(f"No eval set found at {path}")
    rows = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def get_offline_extraction(source_file: str) -> dict:
    stem = Path(source_file).stem
    json_path = OUTPUTS_DIR / f"{stem}.json"
    if not json_path.exists():
        raise FileNotFoundError(f"No cached extraction at {json_path}")
    with json_path.open(encoding="utf-8") as fh:
        return json.load(fh)


def get_live_extraction(source_file: str) -> dict:
    # Lazy import so offline runs don't require the anthropic SDK or PDF deps.
    from anthropic import Anthropic  # noqa: F401
    sys.path.insert(0, str(SPIKE_DIR))
    from extract import extract_metadata, extract_text  # type: ignore

    pdf_path = INPUTS_DIR / source_file
    if not pdf_path.exists():
        raise FileNotFoundError(f"No input file at {pdf_path}")
    document_text = extract_text(pdf_path)
    if not document_text.strip():
        raise RuntimeError(f"No extractable text from {pdf_path}")
    client = Anthropic()
    return extract_metadata(client, document_text)


def run_eval(field: str, mode: str) -> dict:
    if field not in FIELD_DISPATCH:
        raise SystemExit(
            f"Unknown field '{field}'. Known fields: {sorted(FIELD_DISPATCH)}"
        )
    config = FIELD_DISPATCH[field]
    extracted_key: str = config["extracted_key"]
    gt_key: str = config["ground_truth_key"]
    compare: Callable[[Any, Any], bool] = config["compare"]
    threshold: float = config["threshold"]

    eval_rows = load_eval_set(field)
    fetch = get_live_extraction if mode == "live" else get_offline_extraction

    scored = 0
    skipped = 0
    total_score = 0.0
    failures: list[tuple[str, Any, Any]] = []

    for row in eval_rows:
        if row.get("label_status") != "verified":
            skipped += 1
            continue
        source_file = row["source_file"]
        extraction = fetch(source_file)
        actual = extraction.get(extracted_key)
        expected = row.get(gt_key)
        ok = compare(expected, actual)
        score = 1.0 if ok else 0.0
        total_score += score
        scored += 1
        if not ok:
            failures.append((source_file, expected, actual))

    weighted_avg = total_score / scored if scored else 0.0
    return {
        "field": field,
        "mode": mode,
        "scored": scored,
        "skipped": skipped,
        "weighted_avg": weighted_avg,
        "passed": _result_passed(weighted_avg, threshold),
        "failures": failures,
        "threshold": threshold,
    }


def print_result(result: dict) -> None:
    field = result["field"]
    mode = result["mode"]
    print(f"Field: {field}")
    print(f"Mode: {mode}")
    print(f"Scored rows: {result['scored']}")
    print(f"Skipped (needs_review) rows: {result['skipped']}")
    if result["failures"]:
        print("Failures:")
        for source_file, expected, actual in result["failures"]:
            print(f"  {source_file}: expected={expected!r} actual={actual!r} score=0.0")
    print(f"Weighted average: {result['weighted_avg']:.3f}")
    status = "PASS" if result["passed"] else "FAIL"
    print(f"Baseline threshold: {result['threshold']:.2f} -> {status}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a PolicyCodex eval set.")
    parser.add_argument("field", help="Field name (e.g. category, owner_role).")
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--offline",
        action="store_true",
        help="Score against cached spike/outputs/*.json (default).",
    )
    mode_group.add_argument(
        "--live",
        action="store_true",
        help="Re-run the monolithic prompt against spike/inputs/*.pdf.",
    )
    args = parser.parse_args(argv)
    mode = "live" if args.live else "offline"
    result = run_eval(args.field, mode)
    print_result(result)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
