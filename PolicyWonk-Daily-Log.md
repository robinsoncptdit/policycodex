# PolicyCodex Daily Log

Append-only log of merges, dispatches, and major events. Scarlet writes; Chuck skims for situational awareness.

Format: `- HH:MM PT — short description`

## 2026-05-05 (Tue, Day 1 of Week 1)

- 11:30 PT — Brainstormed the agent-led execution model with Chuck.
- 12:30 PT — Spec saved to `docs/superpowers/specs/2026-05-05-agent-led-execution-design.md`, approved by Chuck.
- 12:45 PT — Plan saved to `docs/superpowers/plans/2026-05-05-agent-led-execution.md`.
- (No further execution Tue-Thu; bootstrap deferred to Friday push.)

## 2026-05-06 through 2026-05-07 (Wed-Thu)

- No merges. Agent-led plan sat unexecuted; Chuck working other priorities.

## 2026-05-08 (Fri, Day 4 of Week 1)

- 12:42 PT — Cowork PM plugin updated PRD: P0.1 reframed to Local Folder Ingest, SharePoint connector deferred to v0.2 per P1.2, Week 1 phasing and dependency on PT SharePoint creds removed.
- 12:55 PT — Reconciled INGEST-01..06 in tickets file, refreshed Week 1 sprint plan, updated agent-led design spec and plan to drop Microsoft Graph references. OQ-08 retargeted to PT corpus export (Week 4).
- 13:10 PT — Friday-night push approved by Chuck. Phase 1 bootstrap underway.
- 13:30 PT — Phase 1 complete: git initialized; .gitignore in place; Week 1 sprint plan refreshed to agent-led model; first commit (ca3a38a) lands 27 files including all planning markdown, the spike code, and the bootstrap operating-model artifacts.
- 13:35 PT — Phase 2 dispatch attempt: 6 subagents in parallel. 3 research subagents launched cleanly. 3 code subagents (AI-01, APP-03, REPO-02) failed with "not in a git repository" — harness cached the pre-init state at session start. Falling back to no-worktree sequential dispatch for code subagents.
- 13:40 PT — PUBLISH-01 SSG Explore subagent returned: **Hugo** (build speed + simple Actions story). `PolicyWonk-SSG-Evaluation.md` written; OQ-09 updated.
- 13:50 PT — APP-01 framework Plan subagent returned: **Python + Django** (in-process import of Friday's Python interfaces). `PolicyWonk-Framework-Evaluation.md` written; OQ-03 updated.
- 14:00 PT — AI-04/05/06 prompt-architecture Plan subagent returned: **KEEP MONOLITHIC** with AI-11/12 layered as context; reframe AI-04/05/06 as eval-set tickets. `PolicyWonk-Prompt-Architecture-Decision.md` written; OQ-04 updated.
- 14:15 PT — AI-01 dispatched (sequential, no worktree). Subagent wrote files but couldn't run pytest/git. Scarlet ran tests (4/4 passed) and committed: AI-01 merged at d837279.
- 14:20 PT — APP-03 dispatched. Same permission pattern. Scarlet ran tests (7/7 passed) and committed: APP-03 merged at cf4b6c2.
- 14:25 PT — REPO-02 dispatched. Subagent wrote README.md (149 lines, +2 over draft). Scarlet committed: REPO-02 merged at cad3fbb.
- 14:30 PT — Phase 3 prep docs written: `REPO-03-GitHub-App-Checklist.md` and `REPO-04-PT-Repo-Settings.md`.
- 14:40 PT — Phase 4 wrap: `PolicyWonk-Week-1-Demo.md` and `PolicyWonk-Week-2-Sprint-Plan.md` written. Friday push complete.

## 2026-05-11 (Mon, Day 1 of Week 2)

- 16:23 PT — Product renamed PolicyWonk → PolicyCodex. Domain `policycodex.org` registered. PM updated the PRD (global rename, header breadcrumb, OQ-02 rewrite). Scarlet swept CLAUDE.md, both READMEs, Project Summary, tickets, Week-1 + Week-2 sprint plans, this log, open-questions log, Week-1 demo, agent-led design + plan in `docs/superpowers/`, REPO-03, and REPO-04. File names and the working folder path remain `PolicyWonk-*` / `/Users/chuck/PolicyWonk/`. OQ-02 resolved for "PolicyWonk" and re-opened as a TESS search on "PolicyCodex" in classes 9 and 42.
- 16:50 PT — OQ-01 resolved: AGPL-3.0. PRD got a new Licensing section. REPO-01 landed: canonical AGPL-3.0 text (661 lines, gnu.org source) committed as `LICENSE`. README and README draft License sections updated from "decision pending" to an AGPL-3.0 statement with a one-paragraph network-use explainer. CLAUDE.md "Reconsidered and Locked" bullet flipped to the resolved status. First-public-push gate now waits only on OQ-02 (TESS trademark check) plus Chuck's confirmation that everything else in Phase 2 has landed.
- 17:05 PT — OQ-07 resolved: PT GitHub org is [`Diocese-of-Pensacola-Tallahassee`](https://github.com/Diocese-of-Pensacola-Tallahassee). REPO-04 checklist updated with the concrete org slug; `<pt-org>` placeholders and the suggested-name line are gone. REPO-04 is now unblocked for Chuck's action (~10 min in the GitHub UI). APP-04 (the central bottleneck) loses one upstream blocker.
- 17:25 PT — OQ-03 resolved: **Python + Django** (Chuck signed off on the Plan subagent's recommendation). APP-01 skeleton + APP-02 unblocked for Week 2 dispatch. OQ-09 resolved: **Astro** (Chuck overrode the Explore subagent's Hugo recommendation; driver is parish web teams forking the handbook theme, where Astro's component model beats Hugo's Go templates). PUBLISH-01 build-it work + PUBLISH-02 URL scheme unblocked. Status flipped in `PolicyWonk-Open-Questions.md`, `PolicyWonk-Framework-Evaluation.md`, `PolicyWonk-SSG-Evaluation.md`, the v0.1 tickets, and the Week-2 sprint plan. Remaining Monday-morning blockers: OQ-04 (prompt architecture) and OQ-02 (TESS).
