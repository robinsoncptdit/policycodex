# PolicyWonk AI Prompt Architecture Decision (AI-04/05/06)

**Date:** 2026-05-08
**Author:** Plan subagent (Claude, Friday-night Phase 2 dispatch)
**Status:** Recommendation; awaiting Chuck's sign-off (OQ-04)

## Recommendation: KEEP MONOLITHIC

The spike's monolithic prompt cleared the 60% pass threshold (62.0% all-fields, 70.9% excluding always-null `next_review_date`). AI-11 (taxonomy injection) and AI-12 (retention reference grounding) bolt onto the existing prompt as additive context — they fix the medium and weak tiers without restructuring.

## Per-field tiers from the spike

- **Strong (~0.90):** `category`, `owner_role`, `last_review_date`
- **Medium (0.70–0.72):** `effective_date`, `address`, `title`
- **Weak (0.144):** `retention` — context problem (missing reference doc), not a prompt-architecture problem
- **N/A (0.000):** `next_review_date` — source documents do not state cadence

## Why monolithic wins

- Already passes the spec's 60% acceptance bar; we are at 70.9%.
- One Claude call per document. Splitting triples that to ~150 calls for a 50-document corpus.
- Cross-field signal stays in one context: the strong tier scored ~0.90 partly *because* the model sees one page of evidence and decides multiple fields jointly.
- AI-11/AI-12 are low-risk additive injections.
- Calendar fit: scope freeze is end of Week 2; reworking a passing prompt into three is not on the critical path.

## Reframe AI-04 / AI-05 / AI-06

These tickets stop being "prompt files" and become **eval-set tickets against the monolithic prompt**. Per-field eval sets are how we detect regressions when AI-11/AI-12 land, and how we'll know if retention is fixed or if Plan B (a retention-only split prompt) is needed.

## Concrete next steps for Week 2

1. **Reframe AI-04 / AI-05 / AI-06 ticket titles:** "{field} extraction eval set against monolithic prompt." Deliverable shifts from "prompt file" to "labeled eval set + scoring harness + regression baseline."
2. **Lock the eval set.** Promote the 18 scored rows in `spike/outputs/results.csv` to `spike/eval/<field>_eval.jsonl`. Aim for 25–30 labeled rows by end of Week 2 as more PT corpus documents land.
3. **Build the harness in `spike/eval/run_eval.py`.** Loads eval set, runs current monolithic prompt, parses each field, computes weighted-average accept score, prints pass/fail vs 0.85 baseline (above the spike's 0.90 to leave noise headroom).
4. **Establish baseline numbers this week.** Run the harness on the unmodified prompt and record. This is the floor that AI-11 and AI-12 must not regress.
5. **Confirm category taxonomy.** Validate the 12 spike categories against the LA handbook chapter structure during Week 2 alongside AI-04 eval-set work. Taxonomy change → eval labels change.
6. **Sequence AI-11 → AI-12 → re-run all three eval sets.** AI-11 first (small, unblocks AI-06 baseline). AI-12 second (load-bearing for retention). If retention moves from 0.14 to 0.70+, the monolithic decision is vindicated. If not, split out a retention-only sub-prompt as targeted Plan B — but only then.
7. **Update the PRD Open Question entry** to record "Decided: monolithic + injected context. AI-04/05/06 are eval-set tickets."

## Plan B trigger

If after AI-11 + AI-12 the retention score remains below 0.70 on a 25-row eval set, split out a retention-only sub-prompt. Do not pre-emptively split.
