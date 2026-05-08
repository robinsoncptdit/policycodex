# PolicyWonk Sprint Plan: Week 1

**Dates:** Tuesday, May 5, 2026 through Friday, May 8, 2026 (4 working days, soft start)
**Team:** Agent-led. Chuck (human owner) plus Scarlet (project lead) plus per-ticket subagents.
**Sprint Goal:** By end of Friday, every blocking decision is made, every lane is unblocked, and a single PT policy can be ingested and extracted end to end on a developer machine.

## Roles

The team executing this sprint is agent-led. Roles defined in `docs/superpowers/specs/2026-05-05-agent-led-execution-design.md`.

| Role | Responsibility |
|---|---|
| Chuck | Product owner. Decides org questions (license, name, GitHub org, partner sign-offs). Reviews risky-ticket diffs at merge. |
| Scarlet | Project lead. Owns tickets, sprint plans, daily log, weekly demo, risky-ticket draft material. Dispatches subagents. Reviews diffs and merges code-only tickets without Chuck. |
| Subagents (per-ticket) | Execute one ticket each in an isolated worktree against verbatim PRD acceptance criteria. Fresh per dispatch. |

## Capacity

Capacity in person-days is no longer the limiting factor; the limits are Chuck's review time on risky tickets and Scarlet's coordination throughput.

The original sprint plan (with three coder friends and 10.5 person-days of capacity over Tue-Fri) was superseded on 2026-05-05 by the agent-led pivot. The bootstrap (Phase 1 of the agent-led plan) and Phase 2 dispatches landed in a single Friday-evening push on 2026-05-08, not staged across the week. This sprint plan now reads more as a Week 1 retrospective than a forward plan; Week 2's plan is the forward-looking artifact.

## Sprint Backlog

Tickets and outcomes from the Friday-evening Week 1 push. Owners reflect the agent-led model.

| Priority | Ticket | Owner | Outcome |
|---|---|---|---|
| P0 | REPO-01 Decide license (MIT, Apache 2.0, AGPL) and add LICENSE | Chuck | Open at end of Week 1; fallback AGPL stands |
| P0 | REPO-03 Register PolicyWonk GitHub App | Chuck (Scarlet drafts checklist) | Checklist drafted; Chuck executes when ready |
| P0 | REPO-04 Create PT policy repo (private) and configure branch protection | Chuck (Scarlet drafts settings) | Settings drafted; Chuck executes when PT GitHub org confirmed |
| P0 | APP-01 Web framework choice and project skeleton | Plan subagent → Chuck | Plan subagent recommendation pending review |
| P0 | INGEST-01 Local folder reader (recursive walk, CLI/config path) | subagent | Slipped to Week 2 (not dispatched in Friday push; Ingest lane prioritized below AI/App scaffolding) |
| P0 | AI-01 LLM provider abstraction interface | subagent (general-purpose, worktree) | Dispatched Friday; outcome in demo doc |
| P0 | AI-02 Claude implementation of the provider interface | subagent | Slipped to Week 2 (depends on AI-01 landing) |
| P1 | REPO-02 README skeleton (use existing draft) | subagent (general-purpose, worktree) | Dispatched Friday |
| P1 | INGEST-02 Connector interface (LocalFolderConnector + v0.2 plug points) | subagent | Slipped to Week 2 |
| P1 | AI-04 Category extraction prompt with eval set | subagent | Blocked on OQ-04 (monolithic-vs-split decision) |
| P1 | AI-11 Inject diocese's chosen address taxonomy into prompt context | subagent | Blocked on AI-04 |
| P1 | APP-02 Basic local user auth and identity-to-Git-author mapping | subagent | Slipped to Week 2 (depends on APP-01 framework decision) |
| P1 | APP-03 Git provider abstraction interface | subagent (general-purpose, worktree) | Dispatched Friday |
| P1 | AI-04/05/06 prompt architecture | Plan subagent → Chuck | Plan subagent recommendation pending review |
| P2 | INGEST-03 File extraction for PDF, DOCX, MD, TXT | subagent | Carried to Week 2 |
| P2 | PUBLISH-01 Pick and prove a static-site generator | Explore subagent → Chuck | Dispatched Friday for evaluation; build-it work carries to Week 2 |

## Risks

The original four-person-team risks (PT credentials, framework decision drag, license debate, friend availability) were superseded on 2026-05-05. The current risk register comes from the agent-led design spec.

| Risk | Impact | Mitigation |
|---|---|---|
| Subagent diff is plausible but wrong | Bad code merged into `main` | Verbatim PRD acceptance criteria in every prompt. Scarlet runs acceptance commands before merging. Risky-ticket review for irreversible work. |
| Subagents conflict on shared files when dispatched in parallel | Merge conflicts | Detect at merge time; serialize ticket dispatch when files overlap. Friday push uses `ai/`, `app/`, and root README only — no overlap. |
| The Cowork PM plugin and Scarlet write the same file | Lost edits | The PRD is owned by PM only. Scarlet only reads. Git history surfaces accidental writes. |
| Chuck offline when a blocker arrives | Lane stalls | Blocker queued in `PolicyWonk-Open-Questions.md`. Scarlet redirects to other ready tickets. |
| `APP-04` (GitHub provider) bottleneck downstream | Eight downstream tickets stall | Tracked in Week 2 risk register. Pair Scarlet with a Plan subagent if the design is non-trivial. |
| Bootstrap deferred from Tuesday to Friday | Week 1 lands less than originally scoped | Compress into Friday push; carry the rest cleanly to Week 2 with no ceremony around the slip. |

## Definition of Done (Week 1)

- All P0 tickets either closed or explicitly carried with a Week 2 plan.
- Git repo initialized; first commit made; .gitignore in place.
- Open-Questions log live and triaged.
- License decision either made or fallback AGPL confirmed for Week 2.
- Daily Log running.
- Week-1 demo doc and Week-2 sprint plan committed.

## Key Dates

| Date | Event |
|---|---|
| Tue May 5 | Brainstorm + design + plan committed (no execution). |
| Wed May 6 – Thu May 7 | No execution. |
| Fri May 8 | Friday-night push: bootstrap + Phase 2 dispatches + Phase 3 prep + Phase 4 wrap. |
| Mon May 11 | Week 2 starts. Carryover from Week 1 picked up first. |

## Carryover

First sprint. The riskiest-assumption spike landed at 70.9% acceptance (excluding always-null fields), Pass per the rubric. Two prompt enhancements identified by the spike are scheduled: AI-11 and AI-12, both in Week 2 now. Both should push the inventory pass into the 80%+ range before the full PT corpus run in Week 4.

Carrying to Week 2:
- INGEST-01 (local folder reader)
- AI-02 (Claude provider, depends on AI-01 landing)
- INGEST-02 (connector interface)
- INGEST-03 (file extraction)
- AI-04 + AI-11 (depend on OQ-04 monolithic-vs-split decision)
- APP-01 skeleton + APP-02 (depend on OQ-03 framework decision)
- PUBLISH-01 build-it work (depends on OQ-09 SSG decision)

## What This Plan Does Not Cover

- Specific work for Weeks 2 through 6. Plan those at the end of each week's demo.
- DISC presentation prep. That's Week 6 work.
- Pricing, brand, and naming questions. Out of scope per `PolicyWonk-Project-Summary.md`.
