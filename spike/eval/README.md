# PolicyCodex Eval Harness

Regression harness for the monolithic extraction prompt. Each labeled
JSONL is a per-field eval set; offline mode scores against cached
`spike/outputs/*.json`, live mode re-runs the prompt against
`spike/inputs/*.pdf`.

## Invocation

```
python spike/eval/run_eval.py <field> [--offline | --live] [--outputs DIR]
```

Defaults to `--offline`. Exit code is 0 if `weighted_avg >= threshold`,
1 otherwise. Errored rows (fetch failed) are reported separately and do
not flip pass/fail; investigate them before trusting the result.

`--outputs DIR` overrides the offline outputs directory (default
`spike/outputs/`). Useful when scoring a fresh re-extraction run kept in
a separate folder, e.g. `spike/outputs-ai06/` for the address eval after
the AI-11 taxonomy-injection prompt change.
Also overridable via the `POLICYCODEX_EVAL_OUTPUTS` env var.

Currently scored fields (6):

- `category` (AI-04, refined by AI-15): 17 verified rows, weighted_avg 1.000 baseline.
- `owner_role` (AI-05): 10 verified, 7 needs_review.
- `effective_date` (AI-05): 16 verified, 1 needs_review.
- `last_review_date` (AI-05): 16 verified, 1 needs_review.
- `retention_period_years` (AI-05): 12 verified, 5 needs_review.
- `suggested_chapter_section_item` (AI-06): 4 verified, 13 needs_review, weighted_avg 1.000 baseline against `spike/outputs-ai06/`. The split is mechanical against the extractor's self-reported `address_confidence`: all 13 `low`-confidence rows are auto-needs_review per the plan's anti-rubber-stamp rule, and all 4 `medium`-confidence rows are verified at their extracted values. No `high`-confidence rows. The 4 verified ground truths are harness-wiring fixtures (they equal the extractor's output), which is a valid regression guard against prompt drift but is NOT an independent quality measurement of address extraction. The PT taxonomy at `ai/taxonomies/pt_classification.yaml` does not currently define a canonical chapter-axis mapping; AI-13 (gap detection) and a follow-on taxonomy revision will turn this into a real quality signal.

## Eval-set schema (one JSONL per field)

Filename: `{field}_eval.jsonl`. One JSON object per line. Required keys:

- `source_file` (string): filename in `spike/inputs/`.
- `label_status` (string): `"verified"` or `"needs_review"`. Strict;
  unknown values raise at load time.
- `ground_truth_{field}`: the human-labeled correct value, or `null`
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
