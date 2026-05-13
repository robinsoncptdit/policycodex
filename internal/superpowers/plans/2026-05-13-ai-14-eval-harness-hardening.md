# AI-14 Eval Harness Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden the eval harness shipped in AI-04 so AI-05 can extend it without retro-fixing schema or error-handling under time pressure.

**Architecture:** Single-file CLI (`spike/eval/run_eval.py`) with a per-field dispatch table. Hardening adds (1) strict row-shape and label_status validation at load time, (2) per-row try/except in both `--offline` and `--live` modes so one bad row does not discard the run, (3) per-field `BASELINE_THRESHOLD` in the dispatch table, (4) comparator unit tests, and (5) a `README.md` documenting invocation and how to add rows.

**Tech Stack:** Python 3.12, pytest, stdlib only (no new runtime deps).

**Ticket reference:** `PolicyWonk-v0.1-Tickets.md` AI-14 (the 6 Important issues raised in the AI-04 post-merge review). Must land before AI-05 starts.

---

## File Structure

- Modify: `spike/eval/run_eval.py` — strict validation, per-row try/except, per-field threshold, schema decision codified.
- Modify: `spike/eval/test_run_eval.py` — comparator + validation + threshold-boundary tests.
- Modify: `spike/eval/category_eval.jsonl` — drop dead `extracted_category` / `human_score` columns.
- Create: `spike/eval/README.md` — invocation + how to add rows.

**Schema decision (codify in README + validator):** label_status is **per-row**, one JSONL per field (`{field}_eval.jsonl`). AI-05 adds `owner_role_eval.jsonl`, `effective_date_eval.jsonl`, etc. — each independently labeled. Rejected: per-field label_status inside a unified multi-field JSONL (more complex, no payoff for v0.1).

---

## Task 1: Per-field BASELINE_THRESHOLD in dispatch table

**Files:**
- Modify: `spike/eval/run_eval.py`
- Test: `spike/eval/test_run_eval.py`

- [ ] **Step 1: Write the failing test**

Append to `spike/eval/test_run_eval.py`:

```python
def test_per_field_threshold_used_for_pass_fail():
    from run_eval import FIELD_DISPATCH
    assert "threshold" in FIELD_DISPATCH["category"]
    assert FIELD_DISPATCH["category"]["threshold"] == 0.85


def test_threshold_boundary_passes_at_exact_value():
    from run_eval import _result_passed
    assert _result_passed(weighted_avg=0.85, threshold=0.85) is True
    assert _result_passed(weighted_avg=0.8499999, threshold=0.85) is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd spike/eval && python -m pytest test_run_eval.py::test_per_field_threshold_used_for_pass_fail test_run_eval.py::test_threshold_boundary_passes_at_exact_value -v
```

Expected: 2 failures (missing key, missing function).

- [ ] **Step 3: Update FIELD_DISPATCH and add `_result_passed` helper**

In `spike/eval/run_eval.py`, add `"threshold": 0.85` to every entry in `FIELD_DISPATCH`. Remove the module-level `BASELINE_THRESHOLD` constant. Replace `result["passed"] = weighted_avg >= BASELINE_THRESHOLD` with `_result_passed(weighted_avg, threshold)`:

```python
def _result_passed(weighted_avg: float, threshold: float) -> bool:
    return weighted_avg >= threshold
```

In `run_eval()`, read `threshold = config["threshold"]` and use it for the pass check + the result dict.

- [ ] **Step 4: Run tests to verify pass**

```bash
cd spike/eval && python -m pytest test_run_eval.py -v
```

Expected: all tests pass, including the existing offline/category tests.

- [ ] **Step 5: Commit**

```bash
git add spike/eval/run_eval.py spike/eval/test_run_eval.py
git commit -m "refactor(AI-14): move BASELINE_THRESHOLD into per-field dispatch table"
```

---

## Task 2: Strict label_status + row-shape validation at load time

**Files:**
- Modify: `spike/eval/run_eval.py` (`load_eval_set`)
- Test: `spike/eval/test_run_eval.py`

- [ ] **Step 1: Write the failing tests**

Append to `spike/eval/test_run_eval.py`:

```python
import pytest


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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd spike/eval && python -m pytest test_run_eval.py -k "load_eval_set" -v
```

Expected: 3 failures.

- [ ] **Step 3: Implement strict validation**

In `spike/eval/run_eval.py`, define `VALID_LABEL_STATUSES = frozenset({"verified", "needs_review"})` at module top. Replace `load_eval_set` with a validating version that:
1. Loads each row as JSON.
2. Asserts `"source_file"` and `"label_status"` keys are present (raise `ValueError(f"Row {n}: missing 'source_file'")`).
3. Asserts `label_status in VALID_LABEL_STATUSES`.
4. Looks up `gt_key` from `FIELD_DISPATCH[field]["ground_truth_key"]` and asserts it is present as a key in the row (None is allowed; missing is not — `ValueError(f"Row {n}: missing '{gt_key}' key (use null for needs_review rows)")`).

```python
def load_eval_set(field: str) -> list[dict]:
    if field not in FIELD_DISPATCH:
        raise ValueError(f"Unknown field '{field}'")
    gt_key = FIELD_DISPATCH[field]["ground_truth_key"]
    path = EVAL_DIR / f"{field}_eval.jsonl"
    if not path.exists():
        raise FileNotFoundError(f"No eval set found at {path}")
    rows = []
    with path.open(encoding="utf-8") as fh:
        for n, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if "source_file" not in row:
                raise ValueError(f"Row {n}: missing 'source_file'")
            if "label_status" not in row:
                raise ValueError(f"Row {n}: missing 'label_status'")
            if row["label_status"] not in VALID_LABEL_STATUSES:
                raise ValueError(
                    f"Row {n}: label_status={row['label_status']!r}, expected one of {sorted(VALID_LABEL_STATUSES)}"
                )
            if gt_key not in row:
                raise ValueError(
                    f"Row {n}: missing '{gt_key}' key (use null for needs_review rows)"
                )
            rows.append(row)
    return rows
```

- [ ] **Step 4: Run tests to verify pass**

```bash
cd spike/eval && python -m pytest test_run_eval.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add spike/eval/run_eval.py spike/eval/test_run_eval.py
git commit -m "feat(AI-14): strict label_status + row-shape validation in load_eval_set"
```

---

## Task 3: Per-row try/except in offline and live modes

**Files:**
- Modify: `spike/eval/run_eval.py` (`run_eval`)
- Test: `spike/eval/test_run_eval.py`

- [ ] **Step 1: Write the failing test**

Append to `spike/eval/test_run_eval.py`:

```python
def test_run_eval_isolates_per_row_fetch_failures(tmp_path, monkeypatch):
    """A single bad row must not discard the rest of the run."""
    from run_eval import FIELD_DISPATCH, run_eval
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd spike/eval && python -m pytest test_run_eval.py::test_run_eval_isolates_per_row_fetch_failures -v
```

Expected: FAIL (no `errored` key, exception escapes).

- [ ] **Step 3: Wrap per-row fetch in try/except**

In `run_eval()` in `spike/eval/run_eval.py`, replace the per-row body with:

```python
errors: list[tuple[str, str]] = []
for row in eval_rows:
    if row.get("label_status") != "verified":
        skipped += 1
        continue
    source_file = row["source_file"]
    try:
        extraction = fetch(source_file)
    except Exception as exc:
        errors.append((source_file, f"{type(exc).__name__}: {exc}"))
        continue
    actual = extraction.get(extracted_key)
    expected = row.get(gt_key)
    ok = compare(expected, actual)
    score = 1.0 if ok else 0.0
    total_score += score
    scored += 1
    if not ok:
        failures.append((source_file, expected, actual))
```

Return dict gains `"errored": len(errors)` and `"errors": errors`. Update `print_result` to print an `Errors:` block (parallel to `Failures:`) when `result["errors"]` is non-empty. The final exit code/pass logic stays based on `weighted_avg >= threshold`; errors are reported but do not flip pass to fail (they're a separate signal — the harness wiring tells you "N rows could not be scored").

- [ ] **Step 4: Run tests to verify pass**

```bash
cd spike/eval && python -m pytest test_run_eval.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add spike/eval/run_eval.py spike/eval/test_run_eval.py
git commit -m "feat(AI-14): per-row try/except so one fetch failure does not discard the run"
```

---

## Task 4: Comparator unit tests (happy / unhappy / null)

**Files:**
- Test: `spike/eval/test_run_eval.py`

- [ ] **Step 1: Write the tests**

Append to `spike/eval/test_run_eval.py`:

```python
from run_eval import _eq, _int_eq, _iso_date_eq


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
    assert _int_eq("seven", 7) is False  # unparseable


def test_iso_date_eq_happy_unhappy_null():
    assert _iso_date_eq("2024-01-01", "2024-01-01") is True
    assert _iso_date_eq("2024-01-01", " 2024-01-01 ") is True
    assert _iso_date_eq("2024-01-01", "2024-01-02") is False
    assert _iso_date_eq(None, None) is True
    assert _iso_date_eq(None, "2024-01-01") is False
    assert _iso_date_eq("2024-01-01", None) is False
```

- [ ] **Step 2: Run tests to verify pass**

```bash
cd spike/eval && python -m pytest test_run_eval.py -v
```

Expected: all pass (comparators are already implemented from AI-04; this is regression coverage).

- [ ] **Step 3: Commit**

```bash
git add spike/eval/test_run_eval.py
git commit -m "test(AI-14): happy/unhappy/null coverage for comparators"
```

---

## Task 5: Drop dead columns from category_eval.jsonl

**Files:**
- Modify: `spike/eval/category_eval.jsonl`
- Modify: `spike/eval/test_run_eval.py` (drop the assertion that touches `human_score`)

The `extracted_category` and `human_score` columns are unused by the harness. Confirm by `grep -nE 'extracted_category|human_score' spike/eval/run_eval.py` — should produce no hits in non-test code. The existing test `test_verified_rows_have_ground_truth` does touch `human_score`; rewrite it.

- [ ] **Step 1: Rewrite the test to remove dead-column dependency**

Replace `test_verified_rows_have_ground_truth` in `spike/eval/test_run_eval.py` with:

```python
def test_verified_rows_have_ground_truth():
    rows = _load_rows()
    for row in rows:
        if row["label_status"] == "verified":
            assert row["ground_truth_category"] is not None
        else:
            assert row["label_status"] == "needs_review"
            assert row["ground_truth_category"] is None
```

- [ ] **Step 2: Drop the dead columns from the JSONL**

For each of the 18 rows in `spike/eval/category_eval.jsonl`, remove the `"extracted_category"` and `"human_score"` keys. Use this Python script (run once, then commit the result):

```bash
cd spike/eval && python -c "
import json
rows = []
with open('category_eval.jsonl') as fh:
    for line in fh:
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        row.pop('extracted_category', None)
        row.pop('human_score', None)
        rows.append(row)
with open('category_eval.jsonl', 'w') as fh:
    for row in rows:
        fh.write(json.dumps(row) + '\n')
"
```

- [ ] **Step 3: Run tests to verify pass**

```bash
cd spike/eval && python -m pytest test_run_eval.py -v
```

Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add spike/eval/category_eval.jsonl spike/eval/test_run_eval.py
git commit -m "chore(AI-14): drop dead extracted_category and human_score columns"
```

---

## Task 6: README.md — invocation + how to add rows

**Files:**
- Create: `spike/eval/README.md`

- [ ] **Step 1: Write the README**

Create `spike/eval/README.md` with the following content (verbatim):

```markdown
# PolicyCodex Eval Harness

Regression harness for the monolithic extraction prompt. Each labeled
JSONL is a per-field eval set; offline mode scores against cached
`spike/outputs/*.json`, live mode re-runs the prompt against
`spike/inputs/*.pdf`.

## Invocation

```
python spike/eval/run_eval.py <field> [--offline | --live]
```

Defaults to `--offline`. Exit code is 0 if `weighted_avg >= threshold`,
1 otherwise. Errored rows (fetch failed) are reported separately and do
not flip pass/fail; investigate them before trusting the result.

Currently scored fields: `category`. Fields wired into `FIELD_DISPATCH`
but awaiting eval sets: `owner_role`, `effective_date`,
`last_review_date`, `retention_period_years`,
`suggested_chapter_section_item` (AI-05, AI-06).

## Eval-set schema (one JSONL per field)

Filename: `{field}_eval.jsonl`. One JSON object per line. Required keys:

- `source_file` (string) — filename in `spike/inputs/`.
- `label_status` (string) — `"verified"` or `"needs_review"`. Strict;
  unknown values raise at load time.
- `ground_truth_{field}` — the human-labeled correct value, or `null`
  for `needs_review` rows. Key must be present; missing key raises at
  load time.

Verified rows score; needs_review rows are skipped (counted, not run).

## Adding rows

1. Run the spike extractor against the new input PDF to produce a
   cached output JSON under `spike/outputs/`.
2. Review the extracted value. If it is correct, label as
   `"verified"` and copy the value into `ground_truth_{field}`. If it
   is wrong or partial, label as `"needs_review"` and set
   `ground_truth_{field}` to `null` until you've labeled it by hand.
3. Run `python run_eval.py {field} --offline` to confirm the new row
   loads cleanly.

## Per-field threshold

Each field carries its own `threshold` in `FIELD_DISPATCH` (default
0.85). Tighten or loosen it per-field as eval data matures.

## When to extend

- New field to eval → add a row to `FIELD_DISPATCH` plus a new
  `{field}_eval.jsonl`. Comparator goes in the dispatch row.
- New comparator → add `_my_eq` next to `_eq`, `_int_eq`,
  `_iso_date_eq`, plus a happy/unhappy/null test in
  `test_run_eval.py`.
```

- [ ] **Step 2: Commit**

```bash
git add spike/eval/README.md
git commit -m "docs(AI-14): README for eval harness invocation + add-rows workflow"
```

---

## Definition of Done

- All tests pass: `cd spike/eval && python -m pytest test_run_eval.py -v`
- `python spike/eval/run_eval.py category --offline` exits 0 with `Weighted average: 1.000`.
- `BASELINE_THRESHOLD` removed; `FIELD_DISPATCH` has `threshold` per field.
- `category_eval.jsonl` no longer contains `extracted_category` or `human_score`.
- `spike/eval/README.md` exists and matches the schema actually validated by `load_eval_set`.
- No new runtime deps in `spike/requirements.txt`.
