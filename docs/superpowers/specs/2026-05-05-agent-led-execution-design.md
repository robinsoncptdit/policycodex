# PolicyCodex Agent-Led Execution: Design

**Date:** 2026-05-05
**Status:** Approved (by Chuck Robinson, in conversation)
**Author:** Scarlet (Claude Code, Opus 4.7, this session)
**Supersedes:** the human-team owners listed in `PolicyWonk-Week-1-Sprint-Plan.md`

## Context

PolicyCodex's six-week sprint to DISC was originally scoped for one human lead (Chuck) plus three coder friends, with four parallel lanes (Ingest, AI, App, Publish) and roughly 50 tickets between May 5 and June 16, 2026.

On Day 1 of Week 1, the human owner decided to run the project with AI agents in place of the human team. This document specifies the operating model for that shift. It does not change the PRD, the architecture, or the schedule.

## Goals

1. Translate the four-lane sprint structure into an agent-dispatch model that ships v0.1 by DISC mid-June 2026.
2. Preserve the existing PRD, tickets, and sprint plan as the project's source-of-truth artifacts. Minimize re-planning cost.
3. Keep the human in the loop for irreversible and external-service decisions. Default to autonomy on internal code work.
4. Continue using the Cowork `product-management` plugin to own and maintain the PRD.

## Non-Goals

1. Replacing the PRD or relitigating settled architecture decisions.
2. Building custom orchestration. The Agent tool plus existing superpowers skills (`subagent-driven-development`, `dispatching-parallel-agents`) are sufficient.
3. Persistent long-running lane agents. Subagents are fresh per ticket.
4. Multi-tenant agent management. One project, one operator, one repo.

## Design

### 1. Roles and ownership

| Role | Owner | Writes | Reads |
|---|---|---|---|
| Product owner / human in the loop | Chuck Robinson | (informally, in chat) | everything |
| Cowork `product-management` plugin | external (Cowork web mode) | `PolicyWonk-v0.1-Spec.md` (the PRD) | the PRD |
| Project lead | Scarlet (this Claude Code session) | tickets, sprint plans, weekly demo notes, daily log, open-questions log, design specs | the PRD plus everything Scarlet writes |
| Lane subagents | per-ticket Agent invocations | code in `<lane>-<id>-<slug>` worktrees | the ticket-specific subset of the repo |

The human is the source of truth for organizational decisions: license, name, trademark, PT credentials, GitHub org access, partner sign-offs, and any irreversible action. The PM plugin is the source of truth for product requirements. Scarlet is the source of truth for execution.

### 2. Lane mapping and execution model

Five workstreams, mirroring `PolicyWonk-v0.1-Tickets.md`:

- Cross-Cutting (`REPO-01..07`)
- Ingest (`INGEST-01..06`)
- AI (`AI-01..13`)
- App (`APP-01..19`)
- Publish (`PUBLISH-01..08`)

Within a lane, tickets are mostly sequential. Across lanes, parallel where dependencies allow.

**Per-ticket execution loop:**

1. Scarlet claims the next ready ticket (priority and dependencies met).
2. Scarlet drafts a subagent prompt: ticket title, the PRD's verbatim acceptance criteria for that ticket, files to read, constraints.
3. Scarlet dispatches an `Agent` call with `isolation: "worktree"` so the subagent works in its own git worktree branched off `main`. Subagent type:
   - `general-purpose` for code (most tickets)
   - `Explore` for read-only research (e.g., `PUBLISH-01` SSG selection)
   - `Plan` only when a ticket needs architectural design before code
4. The subagent works the ticket, commits to its branch, returns a summary.
5. Scarlet reads the diff, runs acceptance commands (tests, build, lint), then:
   - **Accept** → squash-merge to `main`, drop the worktree.
   - **Revise** → `SendMessage` with feedback, iterate.
   - **Reject** → close the worktree, re-dispatch with an adjusted prompt.

**Parallel dispatch when safe.** When two or more ready tickets do not share state (typically across lanes, different files), Scarlet dispatches them in a single message with multiple Agent calls. Conflicts surface at merge time, not at dispatch.

**Acceptance is verbatim from the PRD.** Every subagent prompt includes the literal acceptance criteria for its ticket. No interpretation by Scarlet.

**Existing spike code is reference material for prompt content, not a starting codebase.** The schema in `spike/extract.py`, the prompt phrasing for the fields the spike validated as strong (category 0.900, owner_role 0.906, last_review_date 0.889), and the 11-category taxonomy carry forward. The script structure (one monolithic prompt, direct Anthropic SDK use, JSON output) does not. AI-01/02/04/05/06/08 build new code against the v0.1 architecture.

**Open question to resolve before AI-04 dispatch:** the spike's monolithic prompt hit 70.9% on PT corpus. The tickets split into per-field-family prompts. Splitting can regress quality before improving it. Decide Week 1: keep monolithic and layer in AI-11 (taxonomy) and AI-12 (retention) grounding, or commit to the split.

### 3. Approval gates by risk

Hybrid by risk, per the human's preference.

**Per-ticket review (the human signs off before merge):**
- External services and third parties: `REPO-03` (GitHub App registration), `REPO-04` (PT policy repo creation)
- Irreversible decisions: `REPO-01` (license), public repo creation, subdomain DNS
- Anything touching secrets or credentials
- Public artifacts: README publication, repo public-visibility flip, handbook subdomain deploy
- Lane-acceptance milestones (one per lane, weekly)

**Demo-only (the human sees at Friday demo):**
- Code-only tickets in AI, App, and Publish lanes
- Internal refactors, tests, scaffolding
- In-flight docs that have not shipped externally

**Override and default.** The human can switch any ticket between buckets at any time. When the boundary is unclear, Scarlet defaults to per-ticket review.

**At per-ticket review:** Scarlet shows the diff plus acceptance-check output and waits for approve/revise. No merge until the human says yes.

**At demo-only:** Scarlet dispatches, reviews, merges, and keeps a running log. Friday demo summarizes all merges since the previous Friday.

### 4. Working tree and branching

**Initial setup (executed when this design is approved):**

1. `git init` in `/Users/chuck/PolicyWonk` (this folder).
2. Create root `.gitignore` covering:
   - `.obsidian/` (Obsidian vault config)
   - `.DS_Store`, `__pycache__/`, `*.pyc`, `venv/`
   - `spike/.env`, `spike/outputs/`
3. First commit: all existing markdown, the `spike/` directory, this design doc, the new `.gitignore`. CLAUDE.md, the PRD, tickets, sprint plan, README draft, and the historical Notes-1..9 all enter the repo history.
4. Push to GitHub later in Week 1 as a Friday milestone, gated on `REPO-01` (license) and the trademark check.

**Branching model:**

- `main` is the integration branch.
- Each ticket gets a feature branch named `<lane>-<id>-<slug>`, e.g., `ingest-01-graph-auth`, `app-04-github-provider`.
- Subagents work in **git worktrees**, created automatically by the Agent tool's `isolation: "worktree"` parameter. Each worktree branches off `main` at dispatch time.
- After acceptance, Scarlet squash-merges the worktree branch to `main` and drops the worktree.

**Two repos in scope, kept distinct:**

1. **PolicyCodex app repo** = this folder. Open source eventually. Contains application code, tickets, sprint plans, PRD, spike, demo notes, design specs.
2. **PT diocesan policy repo** = separate, created at `REPO-04` in PT's GitHub org. Private. Contains PT's actual policies as markdown. The app code talks to it via the GitHub App.

The app repo never contains diocese-specific data.

**Where the Cowork PRD lives:** in this app repo, at `PolicyWonk-v0.1-Spec.md`. The plugin writes it from Cowork; Scarlet reads it from the same file on disk. Two processes share the file system, not memory. Git history is the PRD audit log.

**Source code layout** is an `APP-01` decision (web framework + project skeleton). This design does not pre-commit to a structure.

### 5. Communication and reporting cadence

**While the human is in front of the terminal:**
- Scarlet announces a subagent dispatch in one sentence.
- For a risky-ticket review: show diff plus acceptance output, then pause.
- For a code-only ticket: dispatch, review, merge inline; narrate the merge in one line.

**While the human is offline (Scarlet keeps working):**
- Append to `PolicyWonk-Daily-Log.md` — one timestamped line per merge.
- If a blocker requires human input, **stop** that ticket and write the question to `PolicyWonk-Open-Questions.md`. No inventing answers to organizational questions.
- A risky ticket awaiting the human's review holds at the merge step; its branch sits open. Other ready tickets continue to be dispatched and merged.

**Friday weekly demo:**
- Scarlet writes `PolicyWonk-Week-N-Demo.md`: tickets merged, lane status against PRD acceptance, risks raised, decisions waiting on the human, next-week plan.
- Demo file links commit SHAs for anything non-trivial the human has not already seen.

**End-of-week sprint plan refresh:**
- Scarlet updates `PolicyWonk-Week-N+1-Sprint-Plan.md` with carryover, re-estimated load, scope adjustments. The sprint plan evolves as a versioned doc in git.

**One-shot directives** ("Go", "ship it", "kill that lane") are scope-bounded to the immediately preceding plan or proposal. Authorization does not extend beyond what was just discussed.

**Two artifact systems, distinct:**
- Project tickets and plans live as **markdown in the repo** (canonical, durable, versioned).
- TaskCreate / TaskList in this CLI session is for **transient session-level tracking only**. It is not the ticket board.

### 6. First-week sequencing

Today is Tuesday May 5, 2026. Original sprint plan covers May 5–8 (~3.5 working days). Existing Week-1 ticket scope holds. Owners change from Chuck/Friend A/B/C to **the human** (when human input is required) or **subagent** (dispatchable code work).

**Blocked on the human, queued in `PolicyWonk-Open-Questions.md`:**
- `REPO-01` license decision (Friday EOD; fallback AGPL)
- `REPO-03` GitHub App registration (human acts in GitHub UI; Scarlet drafts the permissions checklist)
- `REPO-04` PT policy repo creation (human acts in PT GitHub org; Scarlet drafts branch-protection settings)
- PT policy corpus export to a local folder (INGEST-06 dependency by Week 4; spike's 19 PDFs cover Week 1 development)
- Trademark check on "PolicyCodex"
- LA contact's role in README
- PT diocesan leadership approval for handbook subdomain (Week 4 dependency, raised now)

**Dispatchable as soon as design is approved and the repo is initialized:**
- `REPO-02` README skeleton (low risk, code-only)
- `AI-01` LLM provider abstraction
- `AI-02` Claude implementation (after AI-01)
- `APP-03` Git provider abstraction interface
- `PUBLISH-01` SSG selection (Explore subagent for research)

**Decisions before dispatch (Scarlet proposes, human approves):**
- **`APP-01` web framework**: Plan subagent evaluates Python-Django, Node-Next, Go-HTMX against the PRD; returns recommendation; human decides.
- **`AI-04/05/06` monolithic-vs-split prompt**: Plan subagent argues both sides against spike data; returns recommendation; human decides.

**Risky tickets (per-ticket review when ready):**
- `REPO-01` (human decides)
- `REPO-03` / `REPO-04` (human executes; Scarlet drafts inputs)
- First public push to GitHub (gated on license and name)

**Friday-EOD realistic targets:**
- Git repo initialized; first commit; `.gitignore` in place
- License decided; LICENSE file committed
- README skeleton on `main`
- `AI-01`, `AI-02`, `APP-03` merged
- `REPO-02` merged
- Web framework decision made (ideally Wednesday)
- Monolithic-vs-split decision made (ideally Wednesday)
- Open-Questions log live and triaged
- Repo pushed to GitHub if license and name are resolved

**Stretch (carry to Week 2 if not landed):**
- `AI-04` / `AI-11` (depends on monolithic-vs-split)
- `APP-01` skeleton (depends on framework decision)
- `INGEST-03` (file-content extraction; depends only on `INGEST-01` landing)

## Open questions to resolve in Week 1

| ID | Question | Owner | Deadline |
|---|---|---|---|
| OQ-01 | License: MIT, Apache 2.0, or AGPL? Fallback AGPL. | Human | Friday May 8 EOD |
| OQ-02 | "PolicyCodex" trademark availability | Human | Friday May 8 EOD |
| OQ-03 | Web framework choice (`APP-01`) | Human, after Plan subagent recommends | Wednesday May 6 EOD |
| OQ-04 | Monolithic vs split prompt (`AI-04/05/06`) | Human, after Plan subagent recommends | Wednesday May 6 EOD |
| OQ-05 | LA contact's role in README (advisor / reviewer / co-author) | Human | Friday May 15 (Week 2) |
| OQ-06 | PT diocesan leadership sign-off for handbook subdomain | Human | Week 4 (raised Week 1) |
| OQ-07 | PT GitHub org availability or creation | Human | Wednesday May 6 EOD |
| OQ-08 | PT policy corpus exported to a local folder (full inventory beyond the spike's 19 PDFs) | Human | Week 4 (raised Week 1) |

## Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Subagent diff is plausible but wrong | Bad code merged into `main` | Verbatim acceptance criteria in every prompt; Scarlet runs acceptance commands before merging; risky-ticket review for irreversible work |
| Subagents conflict on shared files when dispatched in parallel | Merge conflicts | Detect at merge time; serialize ticket dispatch when files overlap |
| The Cowork PM plugin and Scarlet write the same file | Lost edits | The PRD is owned by PM only. Scarlet only reads. Git history surfaces any accidental write |
| The human is offline when a blocker arrives | Lane stalls | Blocker queued in `PolicyWonk-Open-Questions.md`; Scarlet redirects to other ready tickets |
| `APP-04` (GitHub provider) bottleneck | Eight downstream tickets stall | Track in Week 1 risk register; pair Scarlet with a Plan subagent if the design is non-trivial |

## References

- `CLAUDE.md` — standing project context
- `PolicyWonk-Project-Summary.md` — product spirit
- `PolicyWonk-v0.1-Spec.md` — PRD; product-management owns
- `PolicyWonk-v0.1-Tickets.md` — engineering tickets; this design owns
- `PolicyWonk-Week-1-Sprint-Plan.md` — current sprint plan; will be revised post-design
- `PolicyWonk-Spike-Plan.md` — riskiest-assumption spike, with results
- `PolicyWonk-README-Draft.md` — public README draft
- superpowers skills used: `brainstorming`, `subagent-driven-development`, `dispatching-parallel-agents`, `using-git-worktrees`, `verification-before-completion`
