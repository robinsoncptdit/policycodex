# PolicyCodex Sprint Plan: Week 3

**Dates:** Monday, May 18, 2026 through Friday, May 22, 2026 (5 working days)
**Operating model:** Agent-led (per `internal/superpowers/specs/2026-05-05-agent-led-execution-design.md`)
**Sprint Goal:** Land the PR-backed edit flow end-to-end (APP-05 → APP-06 → APP-07 → APP-17/18/19), establish foundational-policy bundle reading + L3 startup protection (INGEST-07 + APP-21) against a pre-scaffolded PT bundle, prove Astro builds from markdown (PUBLISH-01), and deliver the formal address eval set (AI-06). Downstream demo target: by EOD Friday, an admin can edit a policy in the web UI, the change opens a PR, a reviewer approves it via the UI, and merging triggers a handbook build.

*Week 2 closed two days ahead of plan (Wed May 13 EOD) with 10/10 Committed tickets merged and 116 tests passing. Week 3 starts from a clean main at `3aef551`; carry-forwards from Week 2's Stretch (4 untouched + 1 partially absorbed) are folded into this plan's Committed list.*

## Roles

Same as Week 2. See `internal/superpowers/specs/2026-05-05-agent-led-execution-design.md`.

| Role | Responsibility |
|---|---|
| Chuck | Product owner. Decides org questions, runs PT-side actions (REPO-08 budget conversation, OQ-08 corpus export, OQ-05 LA contact), reviews risky-ticket diffs at merge. |
| Scarlet | Project lead. Dispatches subagents, code-reviews via spawned reviewer agents, merges code-only tickets, scaffolds the PT foundational-policy bundle (one-time pre-sprint action). |
| Subagents | Execute one ticket each, in worktree isolation, with pre-merge code review. |

## Monday Morning Decisions (block dispatch)

These open items need Chuck's call or one-time setup before related tickets can dispatch:

| OQ / Action | Decision needed | Blocks | Status |
|---|---|---|---|
| **Pre-sprint scaffold** | Hand-create `policies/document-retention/` bundle in PT's repo (policy.md narrative + frontmatter declaring `foundational: true`, plus `data.yaml` copied from `ai/taxonomies/pt_classification.yaml`, plus `source.pdf` archived from `internal/Document Retention Policy.pdf`). One-time setup unblocking INGEST-07, APP-21, AI-12-revised. | INGEST-07, APP-21, AI-12 | **DONE 2026-05-14** (4 days ahead of plan). Bundle live on PT main at `Diocese-of-Pensacola-Tallahassee/pt-policy@34a1671`. 8 classifications + 237 retention rows in data.yaml; policy.md frontmatter validates; source.pdf archived. INGEST-07 / APP-21 / AI-12-revised dispatches no longer blocked. |
| OQ-05 | LA contact's role in README ("design reviewer" / "design partner" / co-author?) | README polish (Week 5) and any LA-attribution in the public push | Chuck: message Patrick this week. Soft deadline EOD Week 3. |
| OQ-08 | PT policy corpus exported beyond the 19 spike PDFs | INGEST-06 (Week-4 acceptance) and AI eval scale-up | Chuck + PT IT director: pick a target date this week. Hard near-blocker if it slips past EOD Week 3. |
| OQ-12 | Worktree fresh-checkout spike-eval gap fix | Subagent verification cleanliness | **DONE 2026-05-14** (option (a), commit `ff3ac47` on main). 18 canonical extraction outputs un-gitignored and committed as eval fixtures; fresh worktrees and clones now run `spike/eval/run_eval.py --offline` cleanly. |
| REPO-08 | PT GitHub org upgrade to Team tier | Branch protection enforcement (PRD G3 audit trail) | Chuck + PT IT director: budget conversation. Must close before Week 4 lane acceptance. |

## Sprint Backlog

### Committed (10 tickets, ~6S + 4M ≈ 18 person-days across parallel subagents)

Ordered by dispatch readiness, not priority. All P0 for the sprint.

| Ticket | Owner | Estimate | Depends on | Notes |
|---|---|---|---|---|
| APP-05 Local working copy management | subagent | 1 day | APP-04 (done) | **DONE 2026-05-14** (4 days ahead of plan; merge `e9a41cc`). `GitHubProvider.pull()` mirroring `push` pattern + `WorkingCopyManager.sync()` + `pull_working_copy` management command for cron cadence. 4 commits, 18 new tests, 0 PT hardcoding. Reviewer APPROVE (nits only). Unblocks APP-06, APP-21, INGEST-07. |
| INGEST-07 Bundle-aware reader | subagent | 1 day | INGEST-03 (done), pre-sprint scaffold | **DONE 2026-05-14** (merge `7035946`). `BundleAwarePolicyReader` + `LogicalPolicy` dataclass + `BundleError` exception; new `ingest/policy_reader.py` module. 4 commits, 19 tests (16 initial + 3 added post-review for frontmatter edge cases). Live PT-bundle smoke passes. Reviewer APPROVE WITH FIXES (resolved in `ce12812`). |
| PUBLISH-01 Astro proof | subagent | 2 days | OQ-09 (done) | **DONE 2026-05-14** (merge `7427ffc`). Astro 5.18.1 at `handbook/`, Content Collections with Zod `.refine()` enforcing foundational+provides invariant at build time. 2 commits (deviation from plan's 4-commit shape; bundled content+layouts+samples for build-pass coherence — defensible per reviewer). 4 pages built, verify-build.mjs green. Generic `Diocese of Anytown` content; no PT leakage. Reviewer APPROVE (Astro 5 syntax Context7-verified). |
| AI-06 Address eval set | subagent | 1 day | AI-02 (done), AI-11 (done) | **DONE 2026-05-14** (merge `282b2d7`). 17-row `suggested_chapter_section_item_eval.jsonl` under AI-14 strict schema. 4 verified + 13 needs_review (11 low-conf auto-needs_review per anti-rubber-stamp rule + 2 medium-conf with chapter/format ambiguity). Re-extracted 17 PDFs against post-AI-11 prompt at Claude Sonnet 4.6 (~$1.50 actual spend; Chuck pre-authorized). Outputs committed at `spike/outputs-ai06/` parallel to OQ-12 pattern. 3 commits + 1 review-fix commit (`077fc85` narrative + em-dash sweep). Reviewer APPROVE with narrative + em-dash fixes. Honest harness-wiring baseline; real quality signal pending canonical chapter-axis mapping (AI-13). |
| APP-06 Catalog list view | subagent | 2 days | APP-01 (done), APP-05 | Reads from local working copy. Renders foundational bundles AND flat policies in one inventory list. Dispatch Tue AM after APP-05 lands. Gates APP-07, APP-20. |
| APP-21 L3 startup self-check | subagent | 1 day | APP-05, INGEST-07 | At Django boot, validate every declared `provides:` capability is satisfied by exactly one published foundational policy. Fail-fast with clear error on miss. Dispatch Tue AM. |
| APP-07 Edit form opens PR | subagent | 2 days | APP-04 (done), APP-06 | Form for a single policy; on submit, opens a branch, commits, opens a PR. Wires `core.git_identity.get_git_author` into the commit call. Dispatch Wed after APP-06 lands. |
| APP-17 PR-state-to-gate mapping | subagent | 1 day | APP-04 (done), APP-07 | Map GitHub PR states (open / approved / merged) onto the three gates (Drafted / Reviewed / Published). Dispatch Thu after APP-07. |
| APP-18 Approve action | subagent | 1 day | APP-04 (done) | UI button calls GitHub's review API on behalf of the authenticated reviewer. Dispatch Thu in parallel with APP-17. |
| APP-19 Publish action | subagent | 1 day | APP-04 (done), APP-17 | UI button merges the PR (requires merge permission). Completes the edit-flow end-to-end. Dispatch Fri. |

### Stretch (only if Committed tracks ahead; carry to Week 4 otherwise)

| Ticket | Owner | Estimate | Depends on | Notes |
|---|---|---|---|---|
| APP-20 L1 UI gate (hide Delete on foundational) | subagent | 1 day | APP-06 | Cheap follow-on to APP-06 once it lands. |
| AI-12-revised Retention bundle read | subagent | 1 day | AI-05 (done), INGEST-07 | Wire AI extraction to read from `policies/document-retention/data.yaml` via the bundle-aware reader. Shrunk from M→S after the brainstorm. Land Thu/Fri if INGEST-07 lands Tue. |
| AI-07 Confidence scoring on extractions | subagent | 1 day | AI-04 (done), AI-05 (done), AI-06 | Plumb confidence values from the extraction JSON into the markdown emit + UI display path. |
| APP-08 Wizard skeleton (7-screen flow) | subagent | 3 days | APP-01 (done) | Week-3 theme deliverable per the sprint calendar. M ticket; only viable if 2+ Committed slots evaporate. Otherwise slides to Week 4 alongside APP-09..15. |
| INGEST-02 Connector interface | subagent | 1 day | INGEST-01 (done) | Pure interface work for v0.2 cloud connectors. Cheap; isolated; do if any agent has spare cycles. |
| REPO-09 L2 CI guard for foundational deletion | subagent | 1 day | REPO-04 (done), pre-sprint scaffold | Tiny GitHub Action on the PT policy repo. Defers cleanly to Week 4 if it doesn't fit here. |
| AI-13 Gap-detection pass | subagent | 1 day | AI-12-revised | Flag policies whose type is not represented in the retention schedule. Only viable if AI-12-revised lands Thu. |

### Chuck actions (out-of-band, in parallel with subagent dispatch)

| Action | Estimate | Notes |
|---|---|---|
| OQ-05 message Patrick | 15 min | Confirm role/attribution language. Loops back via async chat. |
| OQ-08 pick PT corpus export target date | 30 min | Conversation with PT IT director. Aim for end of Week 3 if export is feasible; otherwise pre-commit to a Week 4 date. |
| REPO-08 PT org Team-tier upgrade | 1 hr conversation + admin steps | Budget conversation with PT IT director, then GitHub org settings change. |

## Discipline Rules (carried from Week 2)

- Each subagent dispatch goes through `superpowers:using-git-worktrees` + `superpowers:verification-before-completion`. No "looks good without running" claims.
- Code review (`superpowers:requesting-code-review`) on every subagent's output **before** merge to main. Pre-merge review caught AI-11's two Critical issues in Week 2; keep that discipline.
- Each reviewer gets a self-contained brief (description, requirements, BASE/HEAD SHAs, what-to-check). Reviewer subagents don't inherit Scarlet's conversation context.
- `>=` floor pins in `requirements.txt`, not exact pins. Subagent training data has stale exact pins that fail on current PyPI.
- Eager commits: each subagent commits per logical unit, not batched at the end. Scarlet commits docs/log/scaffold updates eagerly too.
- Subagent prompts use the spike output JSON keys verbatim unless an explicit field-name mapping is approved at dispatch time.

## Risks

| Risk | Impact | Mitigation | Status |
|---|---|---|---|
| APP-05 → APP-06 → APP-07 critical path slips | Edit-flow end-to-end demo doesn't ship Friday; cascades into Week 4 | Dispatch APP-05 + INGEST-07 + PUBLISH-01 + AI-06 in parallel Mon AM. Thu-noon checkpoint: if APP-07 isn't at "form renders + commit lands" by then, replan Thu PM. | Active |
| Pre-sprint bundle scaffold not done | INGEST-07 and APP-21 have nothing to read against; tests pass on synthetic fixtures but never see real layout | Scarlet's Sun-Mon AM action. ~30 min. Block dispatch of INGEST-07/APP-21/AI-12 until done. | Active |
| OQ-08 (PT corpus export) keeps slipping | INGEST-06 (Week-4 acceptance) has no data; demo at DISC may be on synthetic corpus | Hard nag this week. The 19 spike PDFs are enough for everything else; only INGEST-06 needs the full corpus. | Active |
| REPO-08 (PT org tier) slips past Week 3 | Branch protection unenforced; PRD G3 audit-trail claim at risk for Week-4 acceptance | Track separately as a ticket-graduated OQ; Chuck owns. Surface to PT IT director early in the week. | Active |
| Subagent worktree isolation regression | Sequential dispatch limits throughput; Week 2's parallelism collapses | Week 2 ran ~7 successful parallel worktree dispatches, zero failures. Accept as low risk. | Retired (was Week-2 risk) |
| AI-11 eval-set debt | AI-06 must actually deliver the formal address eval set this week; if it slips, the "regression baseline for AI-11 changes" gap persists into Week 4 | AI-06 is Committed and S-sized. Dispatch Mon AM in parallel. | Active |

## Definition of Done (Week 3)

- All 10 Committed tickets merged on `main` with passing tests.
- Each subagent dispatch was reviewed via `superpowers:requesting-code-review` before merge. No Critical / Important issues unresolved at merge time.
- Edit-flow end-to-end demoable: open the app, pick a policy, edit a field, submit → PR opens on the PT repo. Reviewer approves in the app UI → GitHub PR shows approved. Publish in the app UI → PR merges. (Astro build via Actions is PUBLISH-06's Week-3 add or Week-4 carry; verify the merge fires whatever Action is wired.)
- Foundational-policy bundle reading and L3 startup protection demoable: app refuses to start with a malformed `data.yaml` and starts cleanly with a valid one.
- AI-06 closed: 18-row `suggested_chapter_section_item_eval.jsonl` under AI-14 schema, scored against post-AI-11 outputs.
- PUBLISH-01 closed: Astro builds a multi-page site from a markdown directory matching the bundle layout. Sets up PUBLISH-06 (Actions deploy) for Week 4.
- OQ-05, OQ-08, OQ-12, REPO-08 each have either a resolution or a concrete next step with a date.
- Week 4 plan written before EOD Friday.

## Key Dates

| Date | Event |
|---|---|
| Sun May 17 / Mon AM | Scarlet scaffolds the PT `policies/document-retention/` bundle (one-time pre-sprint setup). Resolves OQ-12 (canonical eval outputs un-gitignored). |
| Mon May 18 | Wave 1 dispatch: APP-05, INGEST-07, PUBLISH-01, AI-06 in parallel. Chuck starts OQ-05/OQ-08/REPO-08 conversations. |
| Tue May 19 | Wave 1 reviews + merges. Wave 2 dispatch: APP-06, APP-21 (both need APP-05 / INGEST-07 to have landed). |
| Wed May 20 | Wave 2 reviews + merges. APP-07 dispatch (depends on APP-06). |
| Thu May 21 | APP-07 review + merge. APP-17 + APP-18 dispatch in parallel. **Thu-noon checkpoint:** if edit flow isn't at "form opens PR" by then, replan Thu PM. |
| Fri May 22 | APP-17/APP-18 reviews + merges. APP-19 dispatch + merge. End-to-end demo. Week 4 plan written. Stretch tickets that landed get noted in the daily log. |

## What This Plan Does Not Cover

- Week 4+ work. Plan those at end of week.
- Full wizard build (APP-08..16). Week 3 may start APP-08 if capacity opens; the per-screen tickets are Week 4.
- PUBLISH-06 (Actions deploy). PUBLISH-01 (Astro proof) unblocks PUBLISH-06 for Week 4.
- INGEST-04 (manifest), INGEST-05 (incremental), INGEST-06 (full PT corpus run) — all Week 4 / dependent on OQ-08.
- DISC presentation prep (Week 6).
- Public-push polish, README work, pricing, brand decisions — out of v0.1 scope per `PolicyWonk-v0.1-Spec.md`.
