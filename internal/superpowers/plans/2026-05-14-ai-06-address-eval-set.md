# AI-06 Address Eval Set Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the formal `suggested_chapter_section_item` eval set (17 verified-or-needs_review rows under the AI-14 hardened schema, scored against post-AI-11 extraction outputs) so the harness has a regression baseline for the address field after AI-11's taxonomy-injection prompt change.

**Architecture:** New committed cache directory `spike/outputs-ai06/` holds 17 fresh extractions produced by the current post-AI-11 `spike/extract.py` (no extractor code changes). A new `spike/eval/suggested_chapter_section_item_eval.jsonl` carries ground-truth labels under the AI-14 schema (`source_file`, `label_status` strict, `ground_truth_suggested_chapter_section_item`, no extra keys). Scoring runs offline via `python spike/eval/run_eval.py suggested_chapter_section_item --outputs spike/outputs-ai06`. `FIELD_DISPATCH` is already wired (default threshold 0.85); this plan adjusts threshold only if Task 5's baseline data justifies it.

**Tech Stack:** Python 3.12, pytest, the existing `spike/extract.py` against Claude Sonnet via `anthropic` SDK; no new runtime deps.

**Ticket reference:** `PolicyWonk-v0.1-Tickets.md` AI-06 (carried forward from Week 2). Wave 1 of Week-3 plan; depends only on AI-02 (done) and AI-11 (done).

**BASE:** `main` at SHA `d9da925`.

---

## Why Option A (re-extract against post-AI-11 prompt)

Three options were on the table:

- **Option A** — Re-extract 17 PDFs (the 18 in `spike/inputs/` minus `Document Retention Policy.pdf`, which AI-15 dropped from the inventory; `Appendix 10.2 Compliance Memo June 2016.pdf` has no current eval row and stays excluded for parity with the AI-04/AI-05 eval sets) with the current post-AI-11 prompt, commit them to `spike/outputs-ai06/`, label against those.
- **Option B** — Label against pre-AI-11 outputs already in `spike/outputs/`. Free, but violates the sprint plan's "scored against post-AI-11 outputs" wording. Pre-AI-11 addresses include 11 `low` and 6 `medium` confidence values with obvious taxonomy misses (e.g., `Appendix 18 Fraud` -> `18.1.1`; `Appendix 5 Offertory` -> `5.0.0`); labeling against those would either rubber-stamp known-bad outputs or push most rows to `needs_review`, leaving the harness with too few verified rows to be a useful regression baseline.
- **Option C** — Hybrid (re-extract only the worst rows). Adds complexity (mixed-source baseline), the cost saving is negligible, and the 2026-05-13 AI-11 review specifically flagged "labeled against a gitignored re-extraction dir" as the Critical issue; Option C reintroduces that ambiguity.

**Chose A.** Justification: the cost is bounded (17 docs at Claude Sonnet 4.6 is well under $2; AI-11 already proved the extractor works against the same corpus), the post-AI-11 prompt is the artifact we actually need to regress against, and committing the outputs to a tracked directory eliminates the AI-11 review's "labeled against gitignored outputs" failure mode.

**Cost / authorization gate (Task 2):** the implementing subagent must stop at the end of Task 1 and ask Chuck to confirm authorization to spend up to $2 on Anthropic API calls before running the re-extraction in Task 2. The subagent must verify `ANTHROPIC_API_KEY` is set in `spike/.env` before invoking the extractor. No re-extraction runs without explicit go.

---

## Source-of-truth notes

- `spike/inputs/` has 19 PDFs. `Document Retention Policy.pdf` is excluded (per AI-15: it is the source-of-truth reference doc, not an inventory policy). `Appendix 10.2 Compliance Memo June 2016.pdf` is also excluded; it is absent from every existing eval JSONL (category, owner_role, effective_date, last_review_date, retention_period_years all have 17 rows), and AI-06 keeps parity with that set. Final row count: **17**.
- The pre-AI-11 outputs live at `spike/outputs/*.json` (committed per OQ-12 fix, commit `ff3ac47`). Leave them in place; do not modify or delete.
- The post-AI-11 outputs will live at `spike/outputs-ai06/*.json` (new directory created by Task 2). These are committed to git via a `.gitignore` rule extension paralleling the existing `spike/outputs/` rule.
- The PT taxonomy is at `ai/taxonomies/pt_classification.yaml`. `spike/extract.py` reads it via `_load_taxonomy()` and injects it into the prompt. Do not change either; the whole point of this eval is to baseline what the current pipeline produces.
- The address comparator is `_eq` (exact string match), wired in `FIELD_DISPATCH["suggested_chapter_section_item"]`. Threshold defaults to 0.85; Task 5 evaluates whether to keep or lower it based on observed baseline.

---

## File Structure

- Create: `spike/outputs-ai06/` (directory) with 17 `*.json` files; one per input PDF, produced by the current post-AI-11 `spike/extract.py`.
- Create: `spike/eval/suggested_chapter_section_item_eval.jsonl`; 17 rows under the AI-14 hardened schema.
- Modify: `.gitignore`; add a `!spike/outputs-ai06/*.json` allow rule parallel to the existing `spike/outputs/` pair (and a `spike/outputs-ai06/*` deny rule above it for non-JSON noise like `results.csv`).
- Modify: `spike/eval/test_run_eval.py`; add a row-count test, a needs-review-has-null test, and an exactly-three-keys schema-discipline test.
- Modify: `spike/eval/README.md`; flip `suggested_chapter_section_item` from "awaiting" to "scored" in the field-status block; note the AI-06 outputs directory convention; update the existing prose that mentions `spike/outputs-ai11/` as a hypothetical to instead point at the real `spike/outputs-ai06/`.

**Schema (strict, per AI-14):**
- `source_file` (string): filename in `spike/inputs/`.
- `label_status` (string): `"verified"` or `"needs_review"` only.
- `ground_truth_suggested_chapter_section_item` (string or null): the human-checked correct address, or `null` for needs_review rows. No other keys.

---

## Task 1: Worktree setup + pre-flight checks

**Files:**
- None modified.

- [ ] **Step 1: Confirm worktree base SHA**

Run:

```bash
git rev-parse HEAD
```

Expected: `d9da925...` (or a descendant if the implementing harness rebased; in that case, surface to Chuck before continuing).

- [ ] **Step 2: Confirm input corpus**

Run:

```bash
ls spike/inputs/ | wc -l
ls spike/outputs/ | grep -c '\.json$'
```

Expected: `19` PDFs in inputs, `18` JSONs in outputs (pre-AI-11 cache).

- [ ] **Step 3: Confirm test suite is green from BASE**

Run:

```bash
cd spike/eval && python -m pytest test_run_eval.py -v
```

Expected: all tests pass (the AI-14 hardened harness baseline). Capture the green count.

- [ ] **Step 4: Confirm ANTHROPIC_API_KEY is present**

Run:

```bash
test -f spike/.env && grep -q ANTHROPIC_API_KEY spike/.env && echo OK || echo MISSING
```

Expected: `OK`. If `MISSING`, stop and ask Chuck to populate `spike/.env` per the credentials-stay-local convention. Do not proceed.

- [ ] **Step 5: Authorization checkpoint; STOP**

Report to Chuck:
- BASE SHA confirmed.
- 17 PDFs will be re-extracted (19 in inputs minus `Document Retention Policy.pdf` minus `Appendix 10.2 Compliance Memo June 2016.pdf`).
- Model is `claude-sonnet-4-6` per `spike/extract.py` default (override via `POLICYWONK_MODEL` env var; do not change unless Chuck instructs).
- Estimated cost: under $2 at Sonnet pricing.
- Estimated wall time: ~2-3 minutes.

Ask: "Authorized to run the re-extraction?" Wait for explicit yes before Task 2.

- [ ] **Step 6: Commit (none yet)**

No commit at end of Task 1.

---

## Task 2: Re-extract 17 PDFs into spike/outputs-ai06/

**Files:**
- Create: `spike/outputs-ai06/*.json` (17 files)
- Modify: `.gitignore`

- [ ] **Step 1: Stage a clean inputs directory**

The current `spike/extract.py` processes every file in the input dir. To exclude `Document Retention Policy.pdf` and `Appendix 10.2 Compliance Memo June 2016.pdf` without modifying `extract.py`, stage a temp dir:

```bash
mkdir -p /tmp/ai06-inputs
for f in spike/inputs/*.pdf; do
  base=$(basename "$f")
  if [ "$base" = "Document Retention Policy.pdf" ]; then continue; fi
  if [ "$base" = "Appendix 10.2 Compliance Memo June 2016.pdf" ]; then continue; fi
  cp "$f" /tmp/ai06-inputs/
done
ls /tmp/ai06-inputs/ | wc -l
```

Expected: `17`.

- [ ] **Step 2: Run the post-AI-11 extractor**

```bash
mkdir -p spike/outputs-ai06
cd spike && python extract.py /tmp/ai06-inputs outputs-ai06
```

Expected: console reports `Processing 17 files with claude-sonnet-4-6...`, ends with `Done. 17 extractions in outputs-ai06`. The script writes one JSON per PDF plus `results.csv` and (if openpyxl is present) `results.xlsx`.

- [ ] **Step 3: Sanity-check the outputs**

```bash
ls spike/outputs-ai06/*.json | wc -l
grep -l '"suggested_chapter_section_item"' spike/outputs-ai06/*.json | wc -l
```

Expected: `17` files; `17` containing the address key.

- [ ] **Step 4: Clean up the temp inputs directory**

```bash
rm -rf /tmp/ai06-inputs
```

- [ ] **Step 5: Extend .gitignore to track outputs-ai06 JSONs**

Edit `.gitignore`. Add two lines immediately after the existing `!spike/outputs/*.json` line (line 13):

```
spike/outputs-ai06/*
!spike/outputs-ai06/*.json
```

This parallels the existing `spike/outputs/` rule: ignore everything in the dir except `.json` files. Verify:

```bash
git check-ignore -v spike/outputs-ai06/results.csv
git check-ignore -v spike/outputs-ai06/'Acceptable_Use_Policy.json' || echo 'not ignored (good)'
```

Expected: `results.csv` is ignored; `Acceptable_Use_Policy.json` is NOT ignored.

- [ ] **Step 6: Commit**

```bash
git add .gitignore spike/outputs-ai06/*.json
git commit -m "feat(AI-06): re-extract 17 PDFs against post-AI-11 prompt into spike/outputs-ai06/"
```

Verify with `git log --oneline -1` and `git status` (should be clean).

---

## Task 3: Survey baseline + draft eval rows (no commit yet)

**Files:**
- None modified in this task (the survey output is captured in the plan's task log only; the eval JSONL lands in Task 4).

- [ ] **Step 1: Print address + confidence for each re-extracted row**

```bash
cd spike && python -c "
import json, glob, os
for p in sorted(glob.glob('outputs-ai06/*.json')):
    with open(p) as f: d = json.load(f)
    name = os.path.basename(p).replace('.json','')
    print(f'{name}: addr={d.get(\"suggested_chapter_section_item\")!r} conf={d.get(\"address_confidence\")!r} cat={d.get(\"category\")!r}')
"
```

Record the output. The implementer will use it as the working table for Step 2.

- [ ] **Step 2: Draft a working ground-truth table**

For each of the 17 rows, draft a `label_status` + `ground_truth_*` decision using these rules (apply them in order; stop at the first one that fires):

1. **Auto-`needs_review` (ground truth null) if any of:**
   - `address_confidence == "low"`.
   - The extracted address's chapter digit does not correspond to any classification in `ai/taxonomies/pt_classification.yaml` under a reasonable mapping (Finance/HR/IT/Safe Environment/Schools/Worship/Parish Operations/Stewardship/By-Laws/Communications/Risk/Other -> a chapter number you can defend; bare format violations like `5.0.0` or `2.1` instead of `chapter.section.item` also trigger this).
   - The `category` and the address chapter axis disagree (e.g., an `IT` policy with chapter `3` for a non-IT classification).

2. **`verified` only if all of:**
   - `address_confidence` is `medium` or `high`.
   - The address is well-formed `chapter.section.item` (three numeric components separated by dots).
   - The chapter corresponds plausibly to the policy's category and the diocese taxonomy: in the v0.1 PT scheme the chapter axis aligns with the 8 top-level classifications (administrative, personnel, financial, legal, property, cemetery, publications, sacramental); there is no canonical chapter-number mapping committed yet, so use defensible judgment and record it in your task log; AI-06 establishes the baseline, not the canonical mapping.
   - The address is plausibly unique to the policy's subject matter (it is not the generic `7.1.1` fallback that the model emits when uncertain; `7.1.1` appeared on 5+ rows in the pre-AI-11 sample; treat any post-AI-11 `7.1.1` as a `needs_review` candidate unless the policy genuinely concerns property records).

3. **Otherwise `needs_review`.**

**Anti-rubber-stamp rule (from the 2026-05-13 AI-11 review):** if you find yourself accepting the extracted address as ground truth without independently checking the PDF's actual title/subject, STOP. The extracted address IS the value under test; setting `ground_truth_*` to whatever the extractor returned proves nothing. Either (a) you can read the PDF title from the filename and confirm the chapter alignment from the taxonomy YAML, in which case it's a real `verified`, or (b) you cannot, and it's `needs_review`.

For each `verified` row, write a one-line justification in your task log:

```
Acceptable_Use_Policy.pdf -> verified -> 7.1.1
  Reason: IT category, "property/IT systems" axis, address well-formed, confidence medium-or-better.
```

Expect roughly 5-10 `verified` rows and 7-12 `needs_review` rows in the baseline (the pre-AI-11 sample skewed `low`; even after taxonomy injection, the 11-of-18 low-confidence skew is unlikely to flip entirely). Anything claiming 17/17 verified is rubber-stamping; stop and re-read this section.

- [ ] **Step 3: Sanity-check coverage**

Confirm every PDF in the temp inputs directory that was extracted has exactly one drafted row. Confirm `Document Retention Policy.pdf` and `Appendix 10.2 Compliance Memo June 2016.pdf` are NOT in your draft.

- [ ] **Step 4: Commit (none yet)**

No commit at end of Task 3.

---

## Task 4: Write the eval JSONL + row-count test (TDD)

**Files:**
- Test: `spike/eval/test_run_eval.py`
- Create: `spike/eval/suggested_chapter_section_item_eval.jsonl`

- [ ] **Step 1: Write the failing tests**

Append to `spike/eval/test_run_eval.py`:

```python
ADDRESS_EVAL = EVAL_DIR / "suggested_chapter_section_item_eval.jsonl"


def _load_address_rows():
    with ADDRESS_EVAL.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def test_address_eval_set_has_17_rows():
    rows = _load_address_rows()
    assert len(rows) == 17


def test_address_verified_rows_have_ground_truth():
    rows = _load_address_rows()
    for row in rows:
        if row["label_status"] == "verified":
            assert row["ground_truth_suggested_chapter_section_item"] is not None
        else:
            assert row["label_status"] == "needs_review"
            assert row["ground_truth_suggested_chapter_section_item"] is None


def test_address_eval_rows_have_exactly_three_keys():
    """AI-14 schema discipline: no stray columns. See 2026-05-13 AI-11 review."""
    rows = _load_address_rows()
    allowed = {"source_file", "label_status", "ground_truth_suggested_chapter_section_item"}
    for row in rows:
        assert set(row.keys()) == allowed, f"row {row} has unexpected keys"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd spike/eval && python -m pytest test_run_eval.py::test_address_eval_set_has_17_rows test_run_eval.py::test_address_verified_rows_have_ground_truth test_run_eval.py::test_address_eval_rows_have_exactly_three_keys -v
```

Expected: 3 failures (FileNotFoundError; the eval JSONL doesn't exist yet).

- [ ] **Step 3: Write the eval JSONL**

Create `spike/eval/suggested_chapter_section_item_eval.jsonl`. One JSON object per line, one line per input PDF (17 rows total). Use the draft table from Task 3 Step 2. Rows must be in alphabetical order by `source_file` to match the convention in the existing eval JSONLs.

**Strict schema, three keys per row, no others. Example (do not copy the values verbatim; they come from your Task 3 survey):**

```jsonl
{"source_file": "101 Internal Controls.pdf", "label_status": "verified", "ground_truth_suggested_chapter_section_item": "10.1.1"}
{"source_file": "201 Financial Planning-3.pdf", "label_status": "needs_review", "ground_truth_suggested_chapter_section_item": null}
```

Notes:
- No em dashes anywhere in the file (the AI-11 review caught em dashes leaking into the YAML; same rule for JSONL).
- `null` is the JSON null literal, not the string `"null"`.
- File must end with a single newline.

Verify with:

```bash
python -c "
import json
with open('spike/eval/suggested_chapter_section_item_eval.jsonl') as fh:
    rows = [json.loads(line) for line in fh if line.strip()]
print(f'{len(rows)} rows')
for r in rows:
    extra = set(r) - {'source_file','label_status','ground_truth_suggested_chapter_section_item'}
    if extra: print(f'EXTRA KEYS in {r[\"source_file\"]}: {extra}')
verified = [r for r in rows if r['label_status']=='verified']
needs = [r for r in rows if r['label_status']=='needs_review']
print(f'verified: {len(verified)}, needs_review: {len(needs)}')
"
```

Expected: `17 rows`, no `EXTRA KEYS` lines, verified + needs_review sums to 17.

- [ ] **Step 4: Run tests to verify pass**

```bash
cd spike/eval && python -m pytest test_run_eval.py -v
```

Expected: all tests pass (the 3 new ones plus all existing ones).

- [ ] **Step 5: Commit**

```bash
git add spike/eval/suggested_chapter_section_item_eval.jsonl spike/eval/test_run_eval.py
git commit -m "feat(AI-06): suggested_chapter_section_item eval set (17 rows, AI-14 schema)"
```

---

## Task 5: Run the scorer + decide threshold

**Files:**
- Modify (possibly): `spike/eval/run_eval.py` (only if Task 5 Step 2 justifies a threshold adjustment).
- Modify: `spike/eval/README.md`.

- [ ] **Step 1: Score against the post-AI-11 outputs**

```bash
python spike/eval/run_eval.py suggested_chapter_section_item --outputs spike/outputs-ai06
echo "exit=$?"
```

Capture the full output (Scored, Skipped, Failures if any, Weighted average, threshold, PASS/FAIL). The harness exit code is 0 if `weighted_avg >= 0.85`, 1 otherwise.

- [ ] **Step 2: Decide threshold**

Three cases:

1. **`weighted_avg >= 0.85` and the implementer judges the result is real (verified rows are defensible, not rubber-stamped):** keep `FIELD_DISPATCH["suggested_chapter_section_item"]["threshold"] = 0.85`. No code change.

2. **`weighted_avg < 0.85` but the implementer judges the eval set is well-labeled and the gap is genuine prompt-quality limitation:** lower the threshold to `0.70` (the rubric-defensible v0.1 baseline; AI-06 ships a measurable baseline, not a target). Do NOT lower below 0.70 without flagging to Chuck; anything weaker than that means the harness is not protecting against regressions in any meaningful sense and we need a re-extraction strategy or prompt fix, not a threshold drop. Edit `spike/eval/run_eval.py`:

   ```python
   "suggested_chapter_section_item": {
       "extracted_key": "suggested_chapter_section_item",
       "ground_truth_key": "ground_truth_suggested_chapter_section_item",
       "compare": _eq,
       "threshold": 0.70,
   },
   ```

3. **`weighted_avg < 0.70`:** stop. Report to Chuck. Likely one of: (a) ground-truth labels are wrong, (b) the post-AI-11 prompt regressed against pre-AI-11 baseline, or (c) the address task is harder than the v0.1 plan assumed and the threshold needs spec-level revision. Do not commit a sub-0.70 threshold.

- [ ] **Step 3: Re-run if threshold changed**

If Task 5 Step 2 case 2 fired, re-run:

```bash
python spike/eval/run_eval.py suggested_chapter_section_item --outputs spike/outputs-ai06
echo "exit=$?"
```

Expected: exit code 0.

- [ ] **Step 4: Update README**

Edit `spike/eval/README.md`:

(a) In the "Currently scored fields" block, add a new bullet (place after `retention_period_years`):

```
- `suggested_chapter_section_item` (AI-06) - N verified, M needs_review, weighted_avg X.XXX baseline against spike/outputs-ai06/.
```

(b) Remove the entire "Fields wired into `FIELD_DISPATCH` but awaiting an eval JSONL" block (now empty).

(c) In the `--outputs DIR` paragraph, change the example from `spike/outputs-ai11/` (hypothetical, never existed) to `spike/outputs-ai06/` (real, this ticket created it):

```
`--outputs DIR` overrides the offline outputs directory (default
`spike/outputs/`). Useful when scoring a re-extraction run kept in a
separate folder, e.g. `spike/outputs-ai06/` for the address eval after
the AI-11 taxonomy-injection prompt change.
```

- [ ] **Step 5: Run the full test suite + the eval one more time**

```bash
cd spike/eval && python -m pytest test_run_eval.py -v
python spike/eval/run_eval.py suggested_chapter_section_item --outputs spike/outputs-ai06
echo "exit=$?"
```

Expected: all tests pass; eval exits 0.

- [ ] **Step 6: Commit**

If the threshold did NOT change:

```bash
git add spike/eval/README.md
git commit -m "docs(AI-06): README - suggested_chapter_section_item now scored"
```

If the threshold did change:

```bash
git add spike/eval/run_eval.py spike/eval/README.md
git commit -m "feat(AI-06): suggested_chapter_section_item baseline + threshold 0.70"
```

---

## Task 6: Final verification + handoff

**Files:**
- None modified.

- [ ] **Step 1: Confirm clean tree**

```bash
git status
git log --oneline main..HEAD
```

Expected: clean working tree; 3 commits since BASE (`feat(AI-06): re-extract...`, `feat(AI-06): suggested_chapter_section_item eval set...`, `docs(AI-06): README...` OR `feat(AI-06): ...baseline + threshold...`).

- [ ] **Step 2: Run the full repo test suite from main repo cwd**

```bash
cd /Users/chuck/PolicyWonk && python -m pytest -v
```

Expected: same green count as the pre-AI-06 baseline plus the 3 new tests added in Task 4. Capture the count.

- [ ] **Step 3: Re-run the eval one final time**

```bash
python spike/eval/run_eval.py suggested_chapter_section_item --outputs spike/outputs-ai06
echo "exit=$?"
```

Expected: exit 0.

- [ ] **Step 4: Compose the self-report**

Self-report covers:
- Goal in one sentence.
- Files created / modified (paths only).
- Commit list (`git log --oneline main..HEAD`).
- Final eval result: weighted_avg, verified/needs_review counts, threshold, PASS/FAIL.
- Test count before / after.
- Any threshold change (and the reasoning if so).
- Any rows the implementer flagged as judgment-calls during Task 3, so the reviewer can spot-check.
- Open follow-ups (e.g., "the v0.1 chapter-axis mapping is not canonical yet; AI-13 / gap detection will sharpen the rubric").

- [ ] **Step 5: Handoff to code review**

The Week-3 sprint discipline is: code review (`superpowers:requesting-code-review`) BEFORE merge to main. Do not merge. Hand the branch + self-report back to the dispatching session and let Chuck route to a reviewer subagent.

---

## Definition of Done

- `spike/outputs-ai06/` exists with exactly 17 `*.json` files (one per non-excluded input PDF), tracked in git.
- `.gitignore` has the parallel `spike/outputs-ai06/*` + `!spike/outputs-ai06/*.json` rules.
- `spike/eval/suggested_chapter_section_item_eval.jsonl` has 17 rows, each with exactly the three required keys, label_status strictly `verified` or `needs_review`, ground-truth string or null per the schema.
- `python spike/eval/run_eval.py suggested_chapter_section_item --outputs spike/outputs-ai06` exits 0.
- `cd spike/eval && python -m pytest test_run_eval.py -v` is all green; the 3 new AI-06 tests pass.
- `spike/eval/README.md` lists `suggested_chapter_section_item` under "Currently scored fields"; the "awaiting" block is removed.
- Three commits on the branch since BASE `d9da925`, all with `AI-06` in the message.
- No code edits outside the files listed in **File Structure**. In particular: `spike/extract.py` is unchanged, `ai/taxonomies/pt_classification.yaml` is unchanged, the existing 5 eval JSONLs and `spike/outputs/` are unchanged.
- No em dashes anywhere in new content.
- No `extracted_*` / `human_score` / other stray columns in the new JSONL (AI-14 schema discipline).
- The implementer's self-report calls out at least one row they explicitly judged (not rubber-stamped), and the reasoning.
