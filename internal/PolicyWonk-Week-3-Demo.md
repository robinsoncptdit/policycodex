# PolicyCodex Week 3 Demo

**Sprint dates planned:** Monday, May 18, 2026 through Friday, May 22, 2026
**Actual execution window:** Thursday, May 14 through Saturday, May 16 (closed 6 calendar days early, 4 working days)
**Operating model:** Agent-led (per `internal/superpowers/specs/2026-05-05-agent-led-execution-design.md`)

## Summary

Week 3 closed all 10 Committed tickets in three sequential waves over three calendar days, six days before the planned Friday EOD freeze. The headline deliverable is the PR-backed edit flow end-to-end: a CFO opens `/policies/<slug>/edit/` in the web UI, fills the form, and the submit opens a PR on the diocesan policy repo; the catalog row immediately reflects Drafted; a reviewer clicks Approve and the gate flips to Reviewed; a publisher clicks Publish and the PR squash-merges to main, flipping to Published. Every gate transition is a real GitHub PR state, just like the architecture spec calls for.

Two structural commitments locked the day before the sprint and shaped every dispatch:

- **Ship generic, never PT-flavored.** v0.1 codebase ships diocese-agnostic; all PT-specific scaffolding is development-time only. Tracked as REPO-10 for the Week-5 audit pass.
- **Boxed-ship Docker container profile.** v0.1 supports two install paths: clone-and-build (Profile A) and pre-built container pull (Profile B). REPO-05 grew to dual-Compose scope.

Subagent dispatch is now a verified, repeatable recipe. The Agent tool's `isolation: "worktree"` parameter handles worktree creation and branching; implementer subagents go sequential, reviewer subagents go parallel in spec+quality pairs. The recipe worked end-to-end across Wave-2 and Wave-3 without any sandbox surprises that hadn't been seen before.

Test suite went from 116 on main at sprint start to 265 on main at sprint close (+149).

## Tickets Merged

### Wave 1 (Thursday May 14, plan: Monday)

| Ticket | Merge SHA | Notes |
|---|---|---|
| APP-05 Local working copy management | `e9a41cc` | `GitHubProvider.pull()` mirroring `push` pattern, `WorkingCopyManager.sync()`, `pull_working_copy` management command for cron cadence. 4 commits, 18 new tests, zero PT hardcoding. Reviewer APPROVE (nits only). |
| INGEST-07 Bundle-aware reader | `7035946` | `BundleAwarePolicyReader` + `LogicalPolicy` dataclass + `BundleError` in new `ingest/policy_reader.py`. 4 commits, 19 tests (16 initial + 3 added post-review). Live PT-bundle smoke passes. Reviewer APPROVE WITH FIXES (resolved in `ce12812`). |
| PUBLISH-01 Astro proof | `7427ffc` | Astro 5.18.1 at `handbook/`, Content Collections with Zod `.refine()` enforcing the foundational + provides invariant at build time. 4 pages built, `verify-build.mjs` green. Generic "Diocese of Anytown" content. Reviewer APPROVE (Astro 5 syntax Context7-verified). |
| AI-06 Address eval set | `282b2d7` | 17-row `suggested_chapter_section_item_eval.jsonl` under AI-14 strict schema. 4 verified + 13 `needs_review` (11 low-conf auto-needs_review per anti-rubber-stamp rule + 2 medium-conf with chapter/format ambiguity). Re-extracted 17 PDFs against post-AI-11 prompt at Claude Sonnet 4.6 (~$1.50 actual API spend; pre-authorized). Honest harness-wiring baseline. |
| OQ-12 fix (eval fixtures un-gitignored) | `ff3ac47` | 18 canonical `spike/outputs/*.json` extraction outputs committed as fixtures so fresh worktrees and clones run `spike/eval/run_eval.py --offline` cleanly. |
| Pre-sprint PT bundle scaffold | `pt-policy@34a1671` | Hand-created `policies/document-retention/` on PT repo: `policy.md` (foundational + provides frontmatter, owner Chancellor), `data.yaml` (8 classifications + 237 retention rows), archived `source.pdf`. INGEST-07 / APP-21 / AI-12-revised dispatches no longer blocked. |

### Wave 2 (Friday May 15, plan: Tuesday-Wednesday)

| Ticket | Merge SHA | Notes |
|---|---|---|
| APP-21 L3 startup self-check | `9aabce8` | Django system-check via `@register()` in `app/working_copy/checks.py`, wired through new `WorkingCopyAppConfig`. New `POLICYCODEX_ONBOARDING_COMPLETE` setting gates severity (W001/W002 onboarding-mode infra failures vs E004/E005 post-onboarding); bundle-validity always Error (E001/E002/E003). 6 commits (5 plan + 1 review-fix), 15 new tests. Reviewer APPROVE WITH FIXES applied in-branch (Path import load-bearing, `manage.py check` assertion strengthened). |
| APP-06 Catalog list view | `a681d0f` | Function-based `catalog` view with `@login_required`, reads from local working copy, renders foundational bundles + flat policies in one list with kind badges and `(foundational)` marker. Establishes `core/templates/base.html` as project's first base layout; `/` redirects to `/catalog/`. 3 commits, 9 new tests. Reviewer APPROVE; 2 nits noted as Week-5 follow-ups (semantic `<nav>` scoping, `or` to `and` assertion). |

### Wave 3 (Saturday May 16, plan: Wednesday-Friday)

| Ticket | Merge SHA | Notes |
|---|---|---|
| APP-07 Edit form opens PR | `1a8e626` | Function-based `policy_edit` view at `/policies/<slug>/edit/` with `@login_required`. Form fields: title + body + summary (other frontmatter preserved lossless via `_render_policy_md` helper). Foundational gate returns HTTP 403 with custom template. Branch naming `policycodex/edit-<slug>-<uuid>`. 7 commits (6 plan + 1 review-fix), 21 new tests. Reviewer APPROVE WITH FIXES (empty-frontmatter round-trip + TOCTOU note). |
| APP-17 PR-state-to-gate mapping | `02739b3` | `GitHubProvider.list_open_prs` batches one `repo.get_pulls(state="open")` call returning `list[dict]`. `_pr_to_gate` refactored into module-level helper at `app/git_provider/states.py` shared with `read_pr_state`. Branch-to-slug parser supports both `policycodex/draft-` and `policycodex/edit-<slug>-<hex>`. Catalog template gains gate-badge per row; graceful degradation to "Published" on provider failure. 5 commits, 21 new tests. Reviewer APPROVE WITH FIXES (narrowed exception). |
| APP-18 Approve action | `3674997` | `GitHubProvider.approve_pr` calls PyGithub `create_review(event="APPROVE")`. View at `/policies/approve/` gate-guards on `read_pr_state == "drafted"`. Permission model v0.1: any authenticated user. 6 commits (5 plan + 1 review-fix), 21 new tests. Reviewer APPROVE WITH FIXES (named URL + positive pr_number guard). |
| APP-19 Publish action | `0125323` | `GitHubProvider.merge_pr(merge_method="squash")` wraps PyGithub merge. View at `/policies/<slug>/publish/` locates PR via `list_open_prs` + `branch_to_slug` (no sidecar; **pivoted from plan's policymeta pattern mid-review** after the reviewer caught that APP-07 doesn't produce a sidecar). Gate-guards on `read_pr_state == "reviewed"`. Catalog renders Publish button only on Reviewed rows. 6 commits (5 plan + 1 review-fix), 21 new tests. End-to-end edit-flow demo-ready. |

## Architectural and Process Commitments Locked This Sprint

- **Subagent dispatch recipe verified end-to-end.** Agent tool's `isolation: "worktree"` parameter, sequential implementer dispatch, parallel reviewer pairs (spec + quality). The recipe ran four implementer + eight reviewer subagents across Wave-2 and Wave-3 without manual worktree management. Saved as the `feedback_subagent_sandbox.md` auto-memory; codified in CLAUDE.md.
- **Two-stage pre-merge review per ticket: spec reviewer first, quality reviewer second.** Spec reviewer verifies plan adherence (catches design drift); quality reviewer catches craft issues an auto-generated implementer misses. The split surfaced complementary issues on every Wave-2 and Wave-3 ticket; keep both lanes.
- **Ship generic, never PT-flavored.** v0.1 codebase ships diocese-agnostic. All PT scaffolding (taxonomy YAML, retention PDF, "Diocese of Pensacola-Tallahassee" in code) is development-time only. Install-N onboards via clone + wizard with no code edits. REPO-10 (Week-5) audits the polish-pass.
- **Boxed-ship Docker container profile.** v0.1 supports two install paths: clone-and-build for developer dioceses (Profile A) and pre-built container pull for non-developer dioceses (Profile B). REPO-05 grew to dual-Compose scope. AGPL compliance for Profile B is a one-line "View Source" footer link.
- **Foundational-policy data flow has working L3 protection.** APP-21 refuses to start the app with a missing or malformed `data.yaml`; L1 (UI gate, APP-20) and L2 (CI guard, REPO-09) carry to Week 4.

## Decisions Made (in-sprint)

| Decision | Resolution | Notes |
|---|---|---|
| APP-19 sidecar pattern (`.policymeta.yaml`) | **Abandoned mid-review.** Pivoted to `list_open_prs() + branch_to_slug` lookup, same code path APP-17 uses for catalog gate badges. | APP-07 doesn't write the sidecar; the producer/consumer pair would have shipped broken. Three commits and the `policymeta.py` module deleted as dead code. Caught at quality-review stage. |
| OQ-05 LA contact role | **Resolved.** David Schmitt (IT Director, Archdiocese of Los Angeles) is the contact; OQ-05 in `internal/PolicyWonk-Open-Questions.md` updated; phone + email saved to memory (not committed to the public repo). | Replaces a stale "Patrick" name-on-file. |
| Wave-3 implementer "Critical Operational Note" | **Added to dispatch brief.** Explicit forbid on `cd /Users/chuck/PolicyWonk` for git ops inside an isolated worktree. | APP-17 implementer accidentally landed commits on parent main; rolled back via `git update-ref` with authorization. Did not recur on APP-18/APP-19. |

## Decisions Slipped to Week 4 or Later

| OQ / Item | Reason |
|---|---|
| OQ-08 PT corpus export target date | Chuck + PT IT director conversation pending. Hard near-blocker for INGEST-06 in Week 5; needs to land in Week 4. |
| REPO-08 PT GitHub org Team-tier upgrade | Budget conversation with PT IT director pending. Must close before Week-4 lane acceptance for PRD G3 audit-trail claim. |
| Wave-2/3 review follow-up nits | Semantic `<nav>` scoping + `or` to `and` assertion (APP-06); empty-import + over-permissive assertion + bogus `f""` (APP-07). Roll into REPO-10 polish pass (Week 5). |
| `_resolve_repo` subprocess-duplication across 5 `GitHubProvider` methods | Flagged by 3 separate Wave-3 reviewers. File as APP-22 hygiene ticket in Week 4. |

## Lane Status (end of Week 3)

**Cross-Cutting (REPO):** REPO-09 (L2 CI guard) and REPO-10 (generic-ship audit) carried to Week 4 / Week 5. REPO-08 (PT org Team-tier) still gated on PT budget conversation.

**Ingest (P0.1):** INGEST-07 (bundle-aware reader) merged. INGEST-04 (manifest) and INGEST-05 (incremental) start Week 4. INGEST-06 (full PT corpus) waits on OQ-08.

**AI (P0.2):** AI-06 (address eval set) merged; the inventory-pass-extraction stack is now eval-covered on all five wired fields plus the address baseline. AI-12-revised (retention bundle read), AI-07 (confidence scoring), AI-13 (gap detection) all carry to Week 4 and are dispatch-ready.

**App (P0.3 + P0.4 + P0.6):** The PR-backed edit flow ships. APP-20 (L1 UI delete-gate) carries to Week 4 as Wave-1 (cheap follow-on to APP-06 + INGEST-07). APP-08 (wizard skeleton) and APP-09..16 (wizard screens) are the Week-4 theme.

**Publish (P0.5):** PUBLISH-01 (Astro proof) merged. PUBLISH-06 (Actions deploy on PT) ready for Week 4; closes the merge-to-handbook loop.

## Risks Surfaced This Sprint

- **Implementer subagents can land commits on parent main if they `cd` out of their worktree.** Caught on APP-17, rolled back via `git update-ref`. Mitigated by adding a "Critical Operational Note" to subsequent dispatch briefs forbidding `cd /Users/chuck/PolicyWonk` for git ops; did not recur. Discipline rule baked into Week-3 plan and carries to Week 4.
- **Edit/Write tools intermittently silent-fail inside `.claude/worktrees/<id>/`.** Observed once on APP-18 implementer (worked around via Python heredocs through Bash); did not recur on APP-19 with the same recipe. Appears classifier-sensitive to brief framing rather than a hard sandbox limit. Watch for it in Week 4; have the heredoc fallback ready.
- **Implementer's auto-worktree may branch from a session-start commit older than current main.** Wave-1 hit this; brief Week-4 implementers to first `git merge main` into their auto-branch when their work depends on prior-wave outputs. Discipline rule already in Week-3 plan, carries.
- **PR architecture has a write-side gap: APP-07 commits and pushes via the working copy, but the working copy does not pull approved-then-merged branches back.** APP-05's pull cadence covers this on the cron timer; an immediate post-merge pull is not wired. Surface for Week 4 if it becomes a demo friction.

## Decisions Waiting on Chuck (Monday morning)

1. **OQ-08 PT corpus export target date.** Conversation with PT IT director; aim for a concrete date in Week 4. Hard near-blocker for INGEST-06 (Week 5).
2. **REPO-08 PT GitHub org Team-tier upgrade.** Budget conversation with PT IT director. Must close before Week-4 lane acceptance.
3. **OQ-05 LA outreach (David Schmitt).** Resolved as identity; outreach is Chuck's next step. Soft deadline EOD Week 3 has slipped one week; aim for EOD Week 4.
4. **Confirm Week-4 sprint plan scope** (`internal/PolicyWonk-Week-4-Sprint-Plan.md`) before Wave-1 dispatches Monday AM.

## Week 4 Plan Preview

See `internal/PolicyWonk-Week-4-Sprint-Plan.md` for the forward-looking artifact. Headline: close the foundational-policy data integration loop (APP-20 + REPO-09 + AI-12-revised + AI-13), kick off the wizard (APP-08 skeleton + APP-09 first screen), wire the handbook deploy pipeline (PUBLISH-06), and ship the `_resolve_repo` hygiene refactor (new APP-22 ticket). Hard scope freeze still hits end of Week 4 (was end of Week 2; slipped intentionally as wizard work absorbed two weeks of scope post-foundational-policy design).
