# PolicyCodex Sprint Plan: Week 4

**Dates:** Monday, May 25, 2026 through Friday, May 29, 2026 (5 working days)
**Operating model:** Agent-led (per `internal/superpowers/specs/2026-05-05-agent-led-execution-design.md`)
**Sprint Goal:** Close the foundational-policy data integration loop (APP-20 + REPO-09 + AI-12-revised + AI-13), wire the handbook deploy pipeline (PUBLISH-06), kick off the wizard (APP-08 skeleton + APP-09 GitHub-repo screen), ship the `_resolve_repo` hygiene refactor (new APP-22), and add the source manifest data model (INGEST-04) as the foundation for incremental re-runs in Week 5. Downstream demo target: by EOD Friday, a merge to PT main triggers an Actions build that publishes the handbook artifact, and the app refuses to delete or break foundational policies at all four protection layers (L0 + L1 + L2 + L3).

*Week 3 closed six calendar days ahead of plan (Sat May 16 EOD vs. Fri May 22 freeze) with 10/10 Committed tickets merged and 265 tests passing on main. Week 4 starts from a clean main at `789476c`; carry-forwards from Week 3's Stretch (5 untouched) are folded into this plan's Committed and Stretch lists.*

*Week-4 Wave-1 progress (2026-05-24, dispatched Sunday ahead of the Monday start): 4 of 7 Wave-1 Committed tickets merged: APP-20 (`7493be1`), REPO-09 (`2f36986`), AI-12-revised (`507eb1b`), APP-08 (`fb20b78`). Suite 265 -> 322 (+57). New tickets filed: APP-22 (`_resolve_repo` refactor), APP-23 (detail view + L1 gate), REPO-11 (pin Python). AI-07 scope resolved (separate audit-file producer per spec line 99, no UI). AI-12 eval-drift risk closed (PT data.yaml payload == seed). Remaining Wave-1, all small: AI-07, INGEST-04, APP-22. Full detail in CLAUDE.md and the daily log.*

## Roles

Same as Week 3. See `internal/superpowers/specs/2026-05-05-agent-led-execution-design.md`.

| Role | Responsibility |
|---|---|
| Chuck | Product owner. Decides org questions, runs PT-side actions (OQ-08 corpus export, REPO-08 budget conversation, OQ-05 David Schmitt outreach), reviews risky-ticket diffs at merge. |
| Scarlet | Project lead. Drafts a writing-plans plan per ticket at each Wave's dispatch time (matching Week 3 cadence), dispatches subagents, code-reviews via spawned reviewer pairs (spec + quality), merges code-only tickets, files new tickets in `PolicyWonk-v0.1-Tickets.md` as scope shifts. |
| Subagents | Execute one ticket each from its writing-plans plan, in worktree isolation via Agent tool's `isolation: "worktree"`, with pre-merge two-stage code review. |

## Per-Ticket Plans (writing-plans artifacts)

Per Week-3 pattern: each Committed ticket gets its own writing-plans plan saved under `internal/superpowers/plans/2026-05-DD-<ticket-slug>.md`, drafted at its Wave's dispatch time, not upfront. The sprint backlog below is the scope index; the per-ticket plans are where file paths, TDD steps, and exact dispatch commands live.

## Monday Morning Decisions (block dispatch)

| OQ / Action | Decision needed | Blocks | Status |
|---|---|---|---|
| OQ-08 | PT policy corpus exported beyond the 19 spike PDFs | INGEST-06 (Week 5) | **Resolved 2026-05-24.** Scope decision: v0.1 ingest is local-folder only; the corpus is the 19 spike PDFs. No bulk export, no cloud connectors in v0.1. No Monday action. |
| REPO-08 | PT GitHub org upgrade to Team tier (~$4/user/month) | Branch protection enforcement (PRD G3 audit trail). REPO-09 (L2 CI guard) lands in this sprint and benefits from real protection. | **Resolved 2026-05-24.** Org on Team (1 seat); `main` ruleset now enforcing (verified via API). REPO-09 lands on a protected repo. No Monday action. |
| OQ-06 | PT diocesan leadership sign-off for the handbook subdomain | PUBLISH-07 live-subdomain deploy (Week 5). | **Resolved 2026-05-23.** Go. Subdomain `handbook.ptdiocese.org`, DNS owner Chuck. Feeds PUBLISH-07 (Week 5). No Monday action. |
| OQ-05 | LA contact's role in README | (closed) | **Resolved 2026-05-23.** David Schmitt credited as reviewer and Marcus Madsen (Director of IT, Archdiocese of Baltimore) added as design reviewer in the README; OQ moved to Resolved. No Monday action. |
| APP-22 ticket file entry | New hygiene ticket (`_resolve_repo` extraction) needs to land in `PolicyWonk-v0.1-Tickets.md` before subagent dispatch | APP-22 dispatch | Scarlet's first-action Monday AM. ~10 min. |

## Sprint Backlog

### Committed (10 tickets, ~7S + 3M ≈ 16 person-days across sequential implementer dispatch)

Ordered by dispatch wave. All P0 for the sprint.

| Ticket | Owner | Estimate | Depends on | Notes |
|---|---|---|---|---|
| **Wave 1 (Mon May 25)** ||||||
| APP-20 L1 UI delete-gate | subagent | 1 day | APP-06 (done), INGEST-07 (done) | Hide or disable the Delete button on foundational policies in catalog and detail views. Banner: "this policy is foundational; edit through the typed-table UI." Cheap follow-on; first protection layer (L1) per the 4-layer model. |
| REPO-09 L2 CI guard | subagent | 1 day | REPO-04 (done) | GitHub Action on the PT policy repo. Block any PR diff that (a) deletes a file declaring `foundational: true`, or (b) empties out a declared `provides:` capability. APP-15 dependency noted in the ticket file is for the wizard-scaffolded install; for v0.1 PT, the action is hand-installed once. L2 protection layer. |
| AI-12-revised Retention bundle read | subagent | 1 day | AI-05 (done), INGEST-07 (done) | Re-point AI taxonomy injection from `ai/taxonomies/pt_classification.yaml` to `policies/document-retention/data.yaml` via APP-05's local working copy and INGEST-07's `BundleAwarePolicyReader`. Closes the live-sync loop: a CFO edit to the retention bundle flows into the next AI extraction. |
| AI-07 Confidence scoring | subagent | 1 day | AI-04, AI-05, AI-06 (all done) | Plumb confidence values from extraction JSON into the markdown emit + UI display path. AI-08's emitter already filters the confidence keys; this surfaces them in the catalog detail view as a small badge per field. |
| APP-08 Wizard skeleton (7-screen flow) | subagent | 3 days | APP-01 (done) | Django FormWizard or equivalent multi-step session state. Routes only; per-screen content is APP-09..16. Establishes the wizard route conventions, session-state model, and "save and resume" pattern. Spans Wave 1 + Wave 2. |
| APP-22 Extract `_resolve_repo` into shared helper | subagent | 0.5 day | APP-04 (done), APP-17 (done) | **New ticket; add to `PolicyWonk-v0.1-Tickets.md` Monday AM.** Flagged by 3 separate Wave-3 reviewers. Extract the duplicated subprocess invocation across `clone`, `branch`, `commit`, `push`, `pull` in `app/git_provider/github_provider.py` into a single helper. Tiny refactor; no behavior change; net test count unchanged. |
| INGEST-04 Source manifest data model | subagent | 1 day | None | Path + hash + last-modified + source label per file. Pure data model + tests; sets up INGEST-05 incremental re-runs for Week 5. |
| **Wave 2 (Wed May 27)** ||||||
| PUBLISH-06 Actions deploy | subagent | 2 days | PUBLISH-01 (done), REPO-04 (done) | GitHub Actions workflow installed on PT policy repo: on push to main, build Astro handbook, publish artifact. Subdomain deployment (Caddy / Nginx / GH Pages) is PUBLISH-07 (Week 5). Closes the merge-to-handbook loop end-to-end. |
| AI-13 Gap detection | subagent | 1 day | AI-12-revised (Wave 1) | Flag any policy whose extracted type is not represented in the retention schedule. Reads from the same bundle data.yaml AI-12-revised wires. Surface a count + drill-down list in the catalog UI. |
| APP-09 Wizard screen 1: GitHub repo | subagent | 1 day | APP-08 (Wave 1), APP-04 (done) | First wizard screen content: create new repo or connect existing. Calls into `GitHubProvider.clone` + setup. Anchors the per-screen pattern for APP-10..16 in Week 5. |

### Stretch (only if Committed tracks ahead; carry to Week 5 otherwise)

| Ticket | Owner | Estimate | Depends on | Notes |
|---|---|---|---|---|
| INGEST-02 Connector interface | subagent | 1 day | INGEST-01 (done) | Pure interface work for v0.2 cloud connectors (SharePoint, OneDrive, Drive, Box, Dropbox). Cheap; isolated; do if a subagent slot opens up. |
| INGEST-05 Incremental re-run | subagent | 1 day | INGEST-04 (Wave 1) | Skip unchanged files via hash comparison. Only viable if INGEST-04 lands Tue. |
| APP-10 Wizard screen 2: address scheme picker | subagent | 1 day | APP-08 (Wave 1) | Second wizard screen content. Cheap if APP-09 already landed. |
| APP-11 Wizard screen 3: versioning convention picker | subagent | 1 day | APP-08 (Wave 1) | Third wizard screen content. Cheap if APP-09 landed. |
| PUBLISH-02 Chapter-section-item URL scheme | subagent | 2 days | PUBLISH-01 (done) | Page templates per address scheme. Sets up PUBLISH-03 (default theme) for Week 6 DISC-prep. |
| Wave-2/3 review nit sweep | subagent | 0.5 day | APP-06 (done), APP-07 (done) | Semantic `<nav>` scoping, `or` to `and` assertion (APP-06); empty-import + over-permissive assertion + bogus `f""` (APP-07). Could roll into REPO-10 instead; cheap if dispatched standalone. |

### Chuck actions (out-of-band, in parallel with subagent dispatch)

| Action | Estimate | Notes |
|---|---|---|
| OQ-08 lock PT corpus export target date | done | **Resolved 2026-05-24.** v0.1 corpus is the 19 spike PDFs via local folder; cloud connectors deferred to v0.2. No action needed. |
| REPO-08 PT org Team-tier upgrade | done | **Resolved 2026-05-24.** Org upgraded to Team (1 seat); `main` ruleset enforcing (verified via API). |
| OQ-06 PT leadership subdomain sign-off | done | **Resolved 2026-05-23.** Go; subdomain `handbook.ptdiocese.org`; DNS owner Chuck. No action needed. |
| OQ-05 message David Schmitt | done | **Resolved 2026-05-23.** David + Marcus credited in the README; no action needed. |

## Discipline Rules (carried from Week 3, no changes)

- **Each Committed ticket gets a writing-plans plan drafted at its Wave's dispatch time**, saved under `internal/superpowers/plans/2026-05-DD-<ticket-slug>.md`. The sprint backlog above is the scope index; the per-ticket plans are where file paths, TDD steps, and exact dispatch commands live.
- **Implementer subagent dispatch uses the Agent tool's `isolation: "worktree"` parameter.** Do not manually `git worktree add` ahead of dispatch. Verified end-to-end across Wave-2 + Wave-3 in Week 3.
- **Implementer dispatches are sequential**, not parallel. Reviewers, planners, and research-only subagents can still parallel-dispatch.
- **Implementer brief includes the "Critical Operational Note"** forbidding `cd /Users/chuck/PolicyWonk` for git ops inside an isolated worktree. APP-17 (Wave-3) landed commits on parent main without this; APP-18/APP-19 with the note did not recur.
- **Brief implementer subagents to first `git merge main` into their auto-branch.** Auto-worktree may branch from session-start, not current main.
- **Two-stage pre-merge code review per ticket: spec reviewer first, then quality reviewer.** Both run in parallel as paired subagent dispatch. The split surfaces complementary issues; keep it.
- **Code review (`superpowers:requesting-code-review`) on every subagent's output before merge to main.** No exceptions for "small" tickets; APP-22 hygiene ticket gets reviewed too.
- `superpowers:verification-before-completion` on every subagent's self-report.
- `>=` floor pins in `requirements.txt`, not exact pins.
- Eager commits: each subagent commits per logical unit, not batched at the end. Scarlet commits docs/log/scaffold updates eagerly too.
- Subagent prompts use the spike output JSON keys verbatim unless an explicit field-name mapping is approved at dispatch time.
- **No em dashes** in any committed content (code, comments, docstrings, YAML, JSONL, READMEs, commit messages).
- **If Edit/Write silent-fails inside `.claude/worktrees/<id>/`** (seen once on APP-18 in Week 3), fall back to Python heredocs through Bash and flag in the self-report.

## Risks

| Risk | Impact | Mitigation | Status |
|---|---|---|---|
| APP-08 wizard skeleton spans Wave 1 + Wave 2 (3-day M) and gates APP-09..16 | Wizard work for Weeks 4 + 5 cascades if APP-08 slips | Dispatch APP-08 in Wave 1 alongside the smaller Wave-1 tickets so it has the full week. Wed-noon checkpoint: if APP-08 isn't at "routes + session state working" by then, replan Wed PM and slide APP-09 to Week 5. | Active |
| OQ-08 PT corpus export keeps slipping (was slipping 3 weeks) | INGEST-06 had no data; Week 5 acceptance at risk; DISC demo corpus uncertain | **Closed 2026-05-24** by descoping: v0.1 is local-folder only and the corpus is the 19 spike PDFs (real PT documents, not synthetic). Residual: AI eval ground-truth stays at ~19 docs for v0.1. | Closed |
| REPO-08 PT org Team-tier slips past Week 4 | Branch protection unenforced; PRD G3 audit-trail claim at risk for Week-5 lane acceptance; REPO-09 (L2 CI guard) lands but operates on an unprotected repo | **Closed 2026-05-24.** Org on Team; `main` ruleset enforcing (verified via API). REPO-09 now lands on a protected repo. | Closed |
| AI-12-revised re-points taxonomy read away from `ai/taxonomies/pt_classification.yaml`; existing eval sets target those outputs | Eval regressions across category + the 4 AI-05 fields if the bundle data.yaml differs from the seed | Verify `policies/document-retention/data.yaml` in PT repo (committed 2026-05-14 at `34a1671`) is byte-equal to the seed YAML before dispatching AI-12-revised. If diff, fix the YAML in PT, re-extract baseline, and update eval seeds in the same sprint. | **Closed 2026-05-24.** PT `data.yaml` (`34a1671`) fetched via `gh`; parsed-YAML payload is identical to the seed (8 classifications + 237 retention rows). Only the header comment differs (~69 bytes), which YAML parsing drops and the prompt never sees, so the literal byte-equal test was the wrong test; payload-equality is what matters and it holds. No eval drift expected; AI-12-revised can re-point the read safely. |
| `_resolve_repo` refactor (APP-22) touches 5 provider methods that the entire app stack depends on | Regression in the PR-backed edit flow if the helper is wrong | Pre-merge code review is mandatory; full Python test suite (265 tests) must pass on the worktree branch and after merge. Reviewer must verify zero behavior change at the call-site level. | Active |
| New ticket APP-22 doesn't exist in `PolicyWonk-v0.1-Tickets.md` yet | Subagent dispatch references a ticket the brief can't link to | Scarlet adds the entry first-thing Monday AM as a Cross-Cutting / App-lane hygiene ticket; ~10 min. | Active |
| Wizard work scope creep | APP-08..16 is the bulk of remaining v0.1 app surface; if any one screen blows up, Week 5 polish window compresses | Each per-screen ticket stays S-sized. If APP-09 reveals shared widgets that need their own ticket, file them as Stretch and accept the Week-5 push-out for that screen only. | Active |

## Definition of Done (Week 4)

- All 10 Committed tickets merged on `main` with passing tests.
- Each subagent dispatch was reviewed via the two-stage spec + quality reviewer pair before merge. No Critical / Important issues unresolved at merge time.
- **Foundational-policy 4-layer protection demoable end-to-end:** L0 branch protection (REPO-08 dependent), L1 UI hides Delete on foundational policies (APP-20), L2 CI guard blocks deletion or `provides:` emptying in PR diffs (REPO-09), L3 app refuses to start with broken bundles (APP-21 from Week 3).
- **Merge-to-handbook loop demoable:** merge a PR on PT main, Actions runs, handbook artifact published. Subdomain deployment is Week 5 (PUBLISH-07).
- **Live-sync loop demoable:** a CFO edit to `policies/document-retention/data.yaml` opens a PR, reviewer approves, merge happens, next AI extraction sees the new taxonomy (AI-12-revised). Gap-detection (AI-13) surfaces any inventory policy missing from the updated retention schedule.
- **Wizard ready for screen-by-screen build:** APP-08 skeleton + APP-09 first screen working end-to-end. APP-10..16 unblocked for Week 5.
- **`_resolve_repo` extracted, zero behavior change** (APP-22 merged).
- OQ-08, REPO-08, OQ-05 each have either a resolution or a concrete next step with a date.
- Week 5 plan written before EOD Friday.

## Key Dates

| Date | Event |
|---|---|
| Mon May 25 | Scarlet adds APP-22 ticket entry. Drafts Wave-1 ticket plans (7 plans). Wave 1 dispatch (sequential): APP-20, REPO-09, AI-12-revised, AI-07, INGEST-04, APP-22, APP-08. All Chuck-owned open questions are already resolved (OQ-05, OQ-06, OQ-08, REPO-08), so no Monday OQ conversations remain. |
| Tue May 26 | Wave 1 reviews + merges. APP-08 still in flight. |
| Wed May 27 | APP-08 review + merge. **Wed-noon checkpoint:** if APP-08 isn't at "routes + session state working," replan and slide APP-09 to Week 5. Scarlet drafts Wave-2 ticket plans (3 plans). Wave 2 dispatch: PUBLISH-06, AI-13, APP-09. |
| Thu May 28 | Wave 2 reviews + merges. Begin Stretch dispatch if calendar opens (likely candidates: INGEST-02, INGEST-05, APP-10, APP-11). |
| Fri May 29 | Stretch reviews + merges. End-to-end demo: foundational-policy 4-layer protection, merge-to-handbook loop, live-sync loop, wizard first screen. Week 5 plan written. Stretch tickets that landed get noted in the daily log. |

## What This Plan Does Not Cover

- Week 5+ work. Plan that at end of week.
- Wizard screens APP-10..16. These are Week-5 native; APP-09 lands first in this sprint as the per-screen pattern anchor.
- PUBLISH-07 (subdomain deployment): Week 5.
- REPO-10 (generic-ship audit pass): Week 5 polish week.
- INGEST-06 (PT corpus run): Week 5. OQ-08 resolved 2026-05-24 to local-folder / 19-PDF scope, so this runs against the 19-PDF local folder, not a larger export.
- DISC presentation prep: Week 6.
- Public-push polish, README final pass, pricing, brand decisions: out of v0.1 sprint scope per `PolicyWonk-v0.1-Spec.md`.
