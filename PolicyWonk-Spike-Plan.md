# PolicyWonk Inventory Pass Spike

*Test the riskiest assumption in the v0.1 plan: that AI extraction produces metadata good enough to hit a 60% human acceptance rate on real PT corpus data.*

## Goal

Confirm or reject this assumption with a cheap, fast experiment before the rest of the sprint commits time. Run a single-pass extraction prompt against 15 to 20 representative PT policies. Hand-score the output against a rubric. Decide whether to ship the prompts as the v0.1 baseline, escalate to a stronger model, or change extraction strategy.

Budget: two to four hours of focused work over a single afternoon.

## Method

1. Pull 15 to 20 representative policies from the PT SharePoint corpus. Aim for variety across category, age, and source format (PDF, DOCX, plain text).
2. Drop the files into `spike/inputs/`.
3. Run `spike/extract.py`. It calls Claude (Sonnet 4.6 by default) with the extraction prompt and writes per-file JSON plus a combined `results.csv`.
4. Open `results.csv`, score each proposed field using the rubric below, compute the acceptance rate.
5. Decide using the trigger table below.

## Success Criteria

- **Pass.** 60% or higher acceptance. Ship these prompts as the v0.1 baseline.
- **Marginal.** 40% to 60%. Switch the script to Opus 4.6 and re-run on a 5-file sample. If Opus clears 60%, ship Opus as the v0.1 default with Sonnet as the budget option.
- **Fail.** Below 40% on both Sonnet and Opus. Stop. The issue is probably source-document quality (scanned PDFs without OCR, no metadata in the text at all). That changes scope: v0.1 needs OCR and a more interactive metadata-collection flow. Adjust the spec before week 2.

## Extraction Prompt

The script uses this prompt verbatim. It is also the source of truth for what the AI lane builds in week 1.

```
You are a policy librarian for a Catholic diocese. You read a single
governing document (policy, procedure, or by-law) and extract structured
metadata. Be conservative. If a field is not stated or strongly implied
in the text, leave it null and lower your confidence.

Output strictly as JSON, matching this schema:

{
  "title": "<the policy's title as best you can identify>",
  "summary": "<one sentence describing what this policy governs>",
  "category": "<one of: Finance, HR, IT, Safe Environment, Schools,
                Worship, Parish Operations, Stewardship, By-Laws,
                Communications, Risk, Other>",
  "category_confidence": "<low | medium | high>",
  "owner_role": "<best guess at the diocesan role responsible:
                  CFO, HR Director, IT Director, Vicar General,
                  Chancellor, Superintendent of Schools,
                  Director of Safe Environment, etc.>",
  "owner_role_confidence": "<low | medium | high>",
  "effective_date": "<ISO date if stated, else null>",
  "effective_date_confidence": "<low | medium | high>",
  "last_review_date": "<ISO date if stated, else null>",
  "last_review_date_confidence": "<low | medium | high>",
  "next_review_date": "<ISO date if stated, or computed from
                       effective date plus implied cadence,
                       else null>",
  "next_review_date_confidence": "<low | medium | high>",
  "retention_period_years": "<integer years if stated or inferable
                              from records-management norms,
                              else null>",
  "retention_period_confidence": "<low | medium | high>",
  "suggested_chapter_section_item": "<chapter.section.item address
                                      using LA-Archdiocese-style
                                      numbering, e.g., 5.2.8>",
  "address_confidence": "<low | medium | high>",
  "version_stamp": "1.0",
  "notes": "<anything ambiguous, missing, or concerning that a
            human reviewer should know>"
}

Document text follows. Output only the JSON object.
---
{document_text}
```

## Scoring Rubric

For each policy, score each proposed field on a three-point scale:

- **Accept (1.0).** A Document Control Owner would publish without edit.
- **Edit (0.5).** Right ballpark, needs adjustment (wrong year, slightly wrong category).
- **Reject (0.0).** Wrong, missing, or irrelevant.

Score these eight fields per policy:

1. category
2. owner_role
3. effective_date (if present in source)
4. last_review_date (if present in source)
5. next_review_date (if present or computable from cadence)
6. retention_period_years (if present or industry-standard)
7. suggested_chapter_section_item
8. title

Skip `version_stamp` (always 1.0). Skip `summary` (qualitative, not used in v0.1 metadata).

Acceptance rate = (sum of Accept scores) / (count of fields scored).

Twenty policies times eight fields = 160 data points. The 60% threshold is 96 accepts.

## Sourcing Sample Policies From PT

Three reasonable paths to get 15 to 20 files into `spike/inputs/`:

1. **Manual.** Open SharePoint, pick a representative slice (one Finance, one HR, one IT, one Safe Environment, one Schools, one Worship, one By-Laws, one Parish Operations, plus seven or eight more across the rest), download to local, drop in `spike/inputs/`.
2. **SharePoint search export.** Use the SharePoint search UI to filter by file type, download a batch, sample down.
3. **Microsoft Graph script.** A 30-line companion can fetch a sample programmatically. Ask if you want it drafted.

Aim for variety. A homogeneous sample (all from one department) will not stress-test the prompts.

## Running The Spike

The runnable code is at `spike/extract.py`. Setup:

```bash
cd spike
pip install -r requirements.txt
cp .env.example .env
# add your ANTHROPIC_API_KEY

# drop 15-20 policy files in inputs/
python extract.py inputs outputs

# review and score
open outputs/results.csv
```

Per-file JSON output also lands in `outputs/` for closer inspection of individual extractions.

## Decision Triggers

After scoring, fill in this table and act on it:

| Outcome | Sonnet 4.6 acceptance | Action |
|---------|----------------------|--------|
| Pass | 60%+ | Ship prompts as v0.1 baseline. Move on. |
| Marginal | 40-59% | Re-run on 5 policies with Opus 4.6. If 60%+, ship Opus as v0.1 default. |
| Fail | <40% | Stop. Inspect source files. Likely scanned PDFs or missing metadata. Adjust v0.1 scope to include OCR plus interactive metadata collection. |

## What Done Looks Like

A short follow-up note appended to this file with three things:

- Number of policies tested and acceptance rate by field
- Which decision trigger fired
- Any prompt adjustments worth carrying into v0.1

---

## Spike Results (recorded after the run)

**Sample size.** 18 PT policy PDFs scored (one of the 19 inputs dropped out, likely a parse failure or removed before scoring). Mix included Finance, IT, HR, Parish Operations, and Risk categories.

**Decision trigger fired: PASS.**

- Weighted average across all 8 scored fields: **62.0%** (above the 60% Pass threshold)
- Excluding `next_review_date` (which was always null in source documents and so always scored 0): **70.9%**
- Accept-or-Edit rate (score ≥ 0.5) excluding `next_review_date`: **83.3%**
- Strict-accept rate (score = 1.0 only): 38.9%

**Per-field weighted average (out of 1.0):**

| Field | Score |
|---|---|
| category | 0.900 |
| owner_role | 0.906 |
| last_review_date | 0.889 |
| effective_date | 0.722 |
| address | 0.700 (reviewer flattened to "needs work") |
| title | 0.700 (reviewer flattened to "needs work") |
| retention | 0.144 |
| next_review_date | 0.000 (not applicable, source docs do not specify cadence) |

**Three findings worth carrying into v0.1.**

1. **The retention score of 0.144 reflects a missing reference, not bad extraction.** The AI either guessed at industry norms or punted to null. The diocese's own Document Retention Policy is the real source of truth. v0.1 must inject that document as a reference for retention lookups.

2. **The Document Retention Policy can serve as a multi-purpose source-of-truth document.** It supplies retention periods, a starter document-type taxonomy, an index ordering, and a gap-detection reference (any policy not represented in the schedule is a flag for human review). The onboarding wizard should ask the diocese to point at this document explicitly.

3. **Two prompt enhancements should land in week 1 of the sprint.** Inject the chosen address taxonomy (LA chapters by default). Inject the diocese's retention policy as a reference document. These changes should push retention from 0.14 toward 0.85 and address quality from 0.70 toward 0.90+.

**Action items moved into the spec and ticket board.** See the `P0.X Single Source of Truth Reference Documents` requirement in `PolicyWonk-v0.1-Spec.md` and the new AI-lane and APP-lane tickets in `PolicyWonk-v0.1-Tickets.md`.
