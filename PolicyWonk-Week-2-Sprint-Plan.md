# PolicyCodex Sprint Plan: Week 2

**Dates:** Monday, May 11, 2026 through Friday, May 15, 2026 (5 working days)
**Operating model:** Agent-led (per `docs/superpowers/specs/2026-05-05-agent-led-execution-design.md`)
**Sprint Goal:** Land the carryover from Week 1, get APP-04 (the GitHub provider) to a working PR flow, run the AI-11 prompt enhancement, and hit hard scope freeze by EOD Friday.

## Roles

Same as Week 1. See `docs/superpowers/specs/2026-05-05-agent-led-execution-design.md`.

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
| OQ-04 | Sign off on **KEEP MONOLITHIC** prompt (or commit to split) | AI-04 eval-set ticket | Awaiting Chuck |
| OQ-09 | Static-site generator (PUBLISH-01) | PUBLISH-01 build-it work, PUBLISH-02 | **Resolved 2026-05-11: Astro** (overrode subagent's Hugo recommendation) |
| OQ-07 | PT GitHub org status | REPO-04 execution | **Resolved 2026-05-11: `Diocese-of-Pensacola-Tallahassee`** |
| OQ-02 | TESS trademark check on "PolicyCodex" (classes 9 and 42) | Public push to GitHub | Awaiting Chuck |

Remaining Monday-morning blockers: OQ-04 (prompt architecture) and OQ-02 (TESS trademark). Everything else is unblocked.

## Sprint Backlog

Tickets ordered by priority and dependency. The "Owner" column reflects who actually does the work.

### Carryover from Week 1

| Priority | Ticket | Owner | Estimate | Depends on |
|---|---|---|---|---|
| P0 | INGEST-01 Local folder reader (recursive walk) | subagent | 1 day | None |
| P0 | AI-02 Claude implementation of LLMProvider | subagent | 1 day | AI-01 (merged) |
| P0 | APP-01 Project skeleton (Django) | subagent | 1 day | OQ-03 sign-off |
| P0 | APP-02 Local user auth + identity-to-Git-author mapping | subagent | 1 day | APP-01 |
| P1 | INGEST-02 Connector interface (LocalFolderConnector + v0.2 plug points) | subagent | 1 day | INGEST-01 |
| P1 | INGEST-03 File extraction (PDF, DOCX, MD, TXT) | subagent | 2 days | None |
| P1 | AI-04 Category extraction eval set against monolithic prompt | subagent | 1 day | OQ-04 sign-off |
| P1 | AI-11 Inject diocese's chosen address taxonomy into prompt context | subagent | 1 day | AI-04 |
| P1 | PUBLISH-01 Prove the SSG builds from a sample markdown directory | subagent | 1 day | OQ-09 sign-off |

### Week-2-Native Tickets

| Priority | Ticket | Owner | Estimate | Depends on |
|---|---|---|---|---|
| P0 | REPO-04 Create PT policy repo + branch protection | Chuck (action) | 0.5 day | OQ-07, REPO-03 done |
| P0 | APP-04 GitHub provider implementation (clone, branch, commit, push, open_pr, read_pr_state) | subagent | 3 days | APP-03 (merged), APP-01, REPO-03 done, REPO-04 done |
| P0 | APP-05 Local working copy management | subagent | 1 day | APP-04 |
| P0 | APP-06 Catalog list view reading from working copy | subagent | 2 days | APP-01, APP-05 |
| P1 | AI-08 Markdown + YAML front matter emitter | subagent | 1 day | AI-04 |
| P1 | AI-12 Inject the diocese's retention policy as reference doc | subagent | 2 days | AI-05 work (deferred) |
| P1 | PUBLISH-02 Chapter-section-item URL scheme + page templates | subagent | 2 days | PUBLISH-01 |

### Public Push (gated)

| Priority | Ticket | Owner | Estimate | Depends on |
|---|---|---|---|---|
| P0 | REPO-01 LICENSE file | Chuck + subagent | 0.5 day | OQ-01 sign-off |
| P0 | First public push of PolicyCodex repo to GitHub | Chuck (action) + Scarlet | 0.5 day | REPO-01, OQ-02, OQ-03 |

### Stretch (P2; carry to Week 3 if not landed)

| Priority | Ticket | Owner | Estimate | Depends on |
|---|---|---|---|---|
| P2 | APP-07 Edit form opens PR | subagent | 2 days | APP-04, APP-06 |
| P2 | INGEST-04 Source manifest data model | subagent | 1 day | None |
| P2 | AI-13 Gap-detection pass on retention schedule | subagent | 1 day | AI-12 |
| P2 | PUBLISH-03 Default theme modeled on LA handbook | subagent | 3 days | PUBLISH-02 |

## Capacity

Capacity is no longer measured in person-days. The throughput limit is Scarlet's coordination plus Chuck's review on risky tickets. The week-2 backlog is large but most tickets are small (S/M) and parallelizable across subagents.

Realistic landing if Monday-morning decisions arrive on time:
- All P0 carryover (4 tickets)
- INGEST-02, INGEST-03, AI-04, AI-11, PUBLISH-01 (5 P1 tickets)
- APP-04 if REPO-03 + REPO-04 land Monday/Tuesday
- AI-08, AI-12, PUBLISH-02
- REPO-01 + first public push if OQ-01/02 resolved

If Monday-morning decisions slip to Tuesday, the framework-dependent App-lane tickets (APP-01/02/04) compress into 4 days; expect some to slip to Week 3.

## Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Chuck's Monday-morning decisions slip | App-lane and Public-push tickets cascade into Week 3 | Scarlet drafts a one-page decision summary Sunday evening from `PolicyWonk-Open-Questions.md`; Chuck signs off in chat first thing Monday. |
| APP-04 (GitHub provider) is the largest single ticket of v0.1 and is the central bottleneck | If it slips, eight downstream tickets stall | Pair Scarlet with a Plan subagent on Monday afternoon if the design feels non-trivial. Decompose into clone/branch/commit/push/open_pr/read_pr_state if needed. |
| Subagent worktree isolation still failing | Sequential dispatch limits throughput | Either get the harness to refresh git-repo detection at session start, or accept sequential dispatch as the operating norm. Both work for v0.1 calendar. |
| PT corpus export not landed by Friday | INGEST-06 (full-corpus run) can't prove acceptance | The 19 spike PDFs are enough to develop against. INGEST-06 runs Week 4. |
| Hard scope freeze at Friday EOD | Week 3 work must already be defined | Scarlet writes Week 3 plan Friday afternoon based on what landed Week 2. Anything reframed after Friday is Plan B for v0.1, deferred to v0.2. |

## Definition of Done (Week 2)

- All carryover P0s closed.
- APP-04 (GitHub provider) merged with at least the clone/branch/commit/push round trip working against the PT repo.
- AI-11 lifted at least the address field's eval score above its 0.700 baseline.
- PUBLISH-01 builds a sample markdown directory to a static site (no theme yet).
- REPO-03 GitHub App registered (Chuck's action).
- REPO-04 PT repo created with branch protection (Chuck's action).
- LICENSE file committed (REPO-01).
- Public push to GitHub completed (gated, but ideally landed).
- Week 3 plan written.

## Key Dates

| Date | Event |
|---|---|
| Mon May 11 AM | Chuck signs off on OQ-01/03/04/09. Scarlet dispatches AI-02, INGEST-01, APP-01, AI-04 in parallel. |
| Mon May 11 PM | Chuck runs REPO-03 and (if PT org ready) REPO-04. Scarlet dispatches PUBLISH-01 and AI-11. |
| Tue May 12 | APP-04 design + dispatch. APP-02 + AI-08 + INGEST-02. |
| Wed May 13 | APP-04 lands. INGEST-03, PUBLISH-02, AI-12. |
| Thu May 14 | APP-05 + APP-06. Stretch tickets dispatched. |
| Fri May 15 | Hard scope freeze EOD. Week 2 demo. Week 3 plan written. Public push if gates clear. |

## What This Plan Does Not Cover

- Week 3+ work. Plan those at the end of each week's demo.
- DISC presentation prep (Week 6 work).
- Pricing, brand, and naming (out of scope per `PolicyWonk-Project-Summary.md`).
