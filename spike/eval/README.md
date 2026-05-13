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
