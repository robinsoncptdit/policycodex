# PolicyCodex Sprint Plan: Week 2

**Dates:** Monday, May 11, 2026 through Friday, May 15, 2026 (5 working days)
**Operating model:** Agent-led (per `internal/superpowers/specs/2026-05-05-agent-led-execution-design.md`)
**Sprint Goal:** Land the Week 1 carryover, get APP-04 (the GitHub provider) to a working PR flow, harden the eval harness (AI-14), establish AI-05's multi-field baseline, and hit hard scope freeze by EOD Friday.

**Replan note (2026-05-12):** This plan was drafted 05-08 with an overcommitted ~13S+6M backlog. After AI-04 landed Tue morning, Chuck stopped to recalibrate. Scope is now tightened to a Committed/Stretch cutline (`/Users/chuck/.claude/plans/gleaming-exploring-pumpkin.md`). The Monday Morning Decisions table below remains accurate; the Sprint Backlog and Key Dates sections have been replaced to reflect the Tue replan.

## Roles

Same as Week 1. See `internal/superpowers/specs/2026-05-05-agent-led-execution-design.md`.

| Role | Responsibility |
|---|---|
| Chuck | Product owner. Decides org questions, reviews risky-ticket diffs at merge, runs REPO-03/04 actions in the GitHub UI. |
| Scarlet | Project lead. Dispatches subagents, reviews diffs, merges code-only tickets. |
| Subagents | Execute one ticket each. Where worktree isolation works, in worktrees; otherwise sequential on main. |

## Monday Morning Decisions (block dispatch)

These OQs need Chuck's call before related tickets can dispatch:

| OQ | Decision | Blocks | Status |
|---|---|---|---|
| OQ-01 | License (MIT/Apache 2.0/AGPL) | Public push to GitHub | **Resolved 2026-05-11: AGPL-3.0** |
| OQ-03 | Web framework (APP-01) | APP-01 skeleton, APP-02 | **Resolved 2026-05-11: Python + Django** |
| OQ-04 | Sign off on **KEEP MONOLITHIC** prompt (or commit to split) | AI-04 eval-set ticket | **Resolved 2026-05-12: KEEP MONOLITHIC** |
| OQ-09 | Static-site generator (PUBLISH-01) | PUBLISH-01 build-it work, PUBLISH-02 | **Resolved 2026-05-11: Astro** (overrode subagent's Hugo recommendation) |
| OQ-07 | PT GitHub org status | REPO-04 execution | **Resolved 2026-05-11: `Diocese-of-Pensacola-Tallahassee`** |
| OQ-02 | TESS trademark check on "PolicyCodex" (classes 9 and 42) | Public push to GitHub | Awaiting Chuck |

All Monday-morning OQ blockers are resolved. Week-2 dispatch is unblocked.

## Sprint Backlog

Already landed this week (closed before Tue replan):
- REPO-01 LICENSE, REPO-03 GitHub App, REPO-04 partial (gated on REPO-08), AI-04 eval set + harness, first public push live.

### Committed (10 tickets, ~6S + 4M ≈ 18 person-days across parallel subagents)

Ordered by dispatch readiness, not priority. All P0 for the sprint.

| Ticket | Owner | Estimate | Depends on | Status |
|---|---|---|---|---|
| AI-14 Eval harness hardening | subagent | 1 day | AI-04 (done) | **DONE 2026-05-13** (merged `75d8dda`, 13 tests, plus cleanup `b5e050b`). |
| APP-01 Django skeleton | subagent | 1 day | OQ-03 (done) | **DONE 2026-05-13** (merged `9f555fc`, 1 test, plus cleanup `14e2759`). |
| AI-02 Claude provider impl | subagent | 1 day | AI-01 (done) | **DONE 2026-05-13** (merged `73511b9`, 10 tests). |
| APP-04 GitHub provider (clone, branch, commit, push, open_pr, read_pr_state) | subagent | 3 days | APP-03 (done), REPO-03 (done), REPO-04 partial-ok | **DONE 2026-05-13** (merged `e0e6b41`, 36 tests, live smoke against PT succeeded; plus cleanup `7b54dc2`). Cleared Thu-noon checkpoint ~24h early. |
| INGEST-01 Local folder reader | subagent | 1 day | None | **DONE 2026-05-13** (merged `c9d6f7e`, 10 tests, OQ-11 resolved at `c0858ad`). |
| AI-05 Owner / effective-date / review-date / retention eval sets | subagent | 2 days | AI-02 (done), AI-14 (done) | **Ready for Fri.** Both deps closed. |
| AI-11 Address taxonomy injection | subagent | 1 day | AI-04 (done) | **Ready for Fri.** Success criterion: address eval >0.700. |
| INGEST-03 File content extraction (PDF, DOCX, MD, TXT) | subagent | 2 days | INGEST-01 (done) | **Ready for Fri.** |
| APP-02 Local auth + identity-to-Git-author | subagent | 1 day | APP-01 (done) | **Ready for Fri.** |
| AI-08 Markdown + YAML front-matter emitter | subagent | 1 day | AI-04 (done) | **Ready for Fri.** Fill-in when capacity opens. |

### Stretch (only if Committed tracks ahead; carry to Week 3 otherwise)

| Ticket | Owner | Estimate | Depends on | Notes |
|---|---|---|---|---|
| AI-12 Retention reference injection | subagent | 2 days | AI-05 | **Deps loosened 05-12:** uses hardcoded path to PT retention policy. APP-15 wires UI later. If AI-05 lands by Thu, AI-12 Fri. |
| AI-06 Address eval set | subagent | 1 day | AI-02 | Parallel with AI-11. |
| INGEST-02 Connector interface | subagent | 1 day | INGEST-01 | |
| PUBLISH-01 Astro proof | subagent | 2 days | OQ-09 (done) | |
| APP-05 Local working copy mgmt | subagent | 1 day | APP-04 | Only viable if APP-04 lands by Thu noon. |
| APP-06 Catalog list view | subagent | 2 days | APP-01, APP-05 | Only viable if APP-04 + APP-05 land Thu. |
| AI-15 Label AI-04 needs_review rows | Chuck (action) | 10 min | AI-04 (done) | Cheap; unblock AI-05 ground truth. |

## Discipline Rules (from 05-12 replan)

- AI-14 must merge before AI-05 starts. Hard schema/error-handling blocker.
- Each subagent dispatch goes through `superpowers:using-git-worktrees` + `superpowers:verification-before-completion`. No "looks good without running" claims.
- Code review (`superpowers:requesting-code-review`) on every subagent's output **before** merge to main. AI-04 review found 6 Important issues post-merge — we surface those before merging next time.
- If APP-04 is not at "PR opens against test repo" by Thu noon: replan Thu PM, not Fri. Stretch evaporates.

## Risks

| Risk | Impact | Mitigation | Status |
|---|---|---|---|
| APP-04 slip (M, 3-day, blocks 8+ downstream) | Week 2 stretch collapses; APP-05/APP-06 punt to Week 3 | Thu-noon checkpoint. Decompose into sub-commits so partial landing is possible. | **Retired 2026-05-13.** APP-04 landed a day early; downstream unblocked. |
| AI-12 retention injection underperforms | Retention stays <0.60 acceptance; Plan B (split retention sub-prompt) needs Week 3 schedule space | Run AI-12 against PT's actual retention policy on disk this week or early Week 3. Decision deadline: end of Week 3. | Active. AI-12 still pending (Stretch); depends on AI-05 landing Fri. |
| OQ-08 (full PT corpus) still unexported | INGEST-06 Week-4 acceptance test has no data; AI eval scale-up blocked | Chuck action this week. The 19 spike PDFs are enough to develop against now; INGEST-06 runs Week 4. | Active. Surface Fri AM in the next-step prompt. |
| Subagent worktree isolation still flaky | Sequential dispatch limits throughput | The 05-08 git-repo-caching bug appears fixed for AI-04. If it resurfaces, accept sequential and replan capacity. | **Retired 2026-05-13.** Five successful parallel worktree dispatches this week, zero isolation failures. |
| Hard scope freeze Friday EOD | Week 3 work must be defined | Scarlet writes Week 3 plan Friday based on what landed. Anything reframed after Friday is Plan B / v0.2. | Active. Friday deliverable. |

## Definition of Done (Week 2)

- All 10 Committed tickets merged on `main` with passing tests.
- Each subagent dispatch was reviewed via `superpowers:requesting-code-review` before merge.
- AI-14 merged and AI-05's harness usage matches the hardened schema (not the AI-04 schema).
- AI-12 status decided: landed (Stretch) or scheduled for Week 3 with a date.
- AI-15 closed: the 4 `needs_review` rows in `category_eval.jsonl` are labeled or dropped.
- OQ-05 (LA contact role) and OQ-08 (PT corpus export) have a date or a concrete next step.
- Week 3 plan written before EOD Friday.

## Key Dates

| Date | Event |
|---|---|
| Mon May 11 | Done. AGPL, Django, Astro, monolithic-prompt resolved. REPO-01 / REPO-03 / REPO-04 partial. First public push live. |
| Tue May 12 AM | Done. OQ-04 resolved; AI-04 landed. **Replan: Committed/Stretch cutline installed.** |
| Tue May 12 PM | (Dispatch slipped to Wed AM — session ended without firing.) |
| Wed May 13 AM | **Done.** AI-14, APP-01, AI-02 merged in parallel via worktree isolation. 35/35 tests pass. |
| Wed May 13 PM | **Done.** APP-04 + INGEST-01 dispatched a day early (Thu work pulled forward). Both merged with code-review approval. APP-04 live smoke against PT succeeded. OQ-11 raised and resolved. 73/73 tests pass. Real PR #1 on PT closed by Chuck. |
| Thu May 14 | (Open.) Slate originally planned for Thu is now Fri's: AI-05, AI-11, INGEST-03, APP-02, AI-08. Some or all dispatch Fri AM. |
| Fri May 15 | Hard scope freeze EOD. Dispatch the remaining 5 Committed tickets in parallel waves. AI-12 decision. AI-15 close-out. OQ-05 / OQ-08 next steps. Week 3 plan written. |

## What This Plan Does Not Cover

- Week 3+ work. Plan those at the end of each week's demo.
- DISC presentation prep (Week 6 work).
- Pricing, brand, and naming (out of scope per `PolicyWonk-Project-Summary.md`).
