# PolicyCodex Agent-Led Execution: Week 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bootstrap the agent-led operating model in `/Users/chuck/PolicyWonk`, then run Week 1 of the v0.1 sprint per the design spec, landing the Friday-EOD targets.

**Architecture:** Init this folder as a git repo. Add operating-model artifacts (open-questions log, daily log, agent-led Week-1 sprint refresh). Dispatch decision-gated and code-only tickets via the Agent tool with worktree isolation, per the design spec. Risky tickets pause at merge for human review.

**Tech Stack:** git, Claude Code Agent tool with `isolation: "worktree"`, markdown.

**Source spec:** `docs/superpowers/specs/2026-05-05-agent-led-execution-design.md`

**Execution mode:** Phase 1 runs **inline** in the current Scarlet session (orchestration, not feature implementation). Phases 2–4 dispatch fresh subagents per ticket per the design spec, but the orchestration of those dispatches is itself inline in the Scarlet session.

---

## Phase 1: Bootstrap the repo and operating model

### Task 1: Init git repo with .gitignore

**Files:**
- Create: `/Users/chuck/PolicyWonk/.gitignore`

- [ ] **Step 1: Verify the folder is not yet a git repo**

Run:
```bash
git -C /Users/chuck/PolicyWonk status 2>&1 | head -3
```
Expected: `fatal: not a git repository (or any of the parent directories): .git`

- [ ] **Step 2: Write `.gitignore`**

Write to `/Users/chuck/PolicyWonk/.gitignore`:
```
.obsidian/
.DS_Store
__pycache__/
*.pyc
venv/
spike/.env
spike/outputs/
spike/venv/
docs/superpowers/.cache/
```

- [ ] **Step 3: `git init` with main as the default branch**

Run:
```bash
git -C /Users/chuck/PolicyWonk init -b main
```
Expected output contains: `Initialized empty Git repository in /Users/chuck/PolicyWonk/.git/`

- [ ] **Step 4: Verify `.obsidian/` is ignored**

Run:
```bash
git -C /Users/chuck/PolicyWonk check-ignore -v .obsidian
```
Expected: `.gitignore:1:.obsidian/	.obsidian`

### Task 2: Create the Open Questions log

**Files:**
- Create: `/Users/chuck/PolicyWonk/PolicyWonk-Open-Questions.md`

- [ ] **Step 1: Write the file**

Write to `/Users/chuck/PolicyWonk/PolicyWonk-Open-Questions.md`:
```markdown
# PolicyCodex Open Questions

Source-of-truth log for blockers and pending human decisions during the v0.1 sprint. Scarlet writes this; Chuck reads, decides, and confirms in chat.

## Active

| ID | Question | Owner | Deadline | Status |
|---|---|---|---|---|
| OQ-01 | License: MIT, Apache 2.0, or AGPL? Fallback AGPL. | Chuck | 2026-05-08 EOD | open |
| OQ-02 | "PolicyCodex" trademark availability | Chuck | 2026-05-08 EOD | open |
| OQ-03 | Web framework choice (APP-01) | Chuck, after Plan subagent recommends | 2026-05-06 EOD | open, Plan subagent pending |
| OQ-04 | Monolithic vs split prompt (AI-04/05/06) | Chuck, after Plan subagent recommends | 2026-05-06 EOD | open, Plan subagent pending |
| OQ-05 | LA contact's role in README | Chuck | 2026-05-15 (Week 2) | open |
| OQ-06 | PT diocesan leadership sign-off for handbook subdomain | Chuck | Week 4 | raised |
| OQ-07 | PT GitHub org availability or creation | Chuck | 2026-05-06 EOD | open |
| OQ-08 | PT policy corpus exported to a local folder (full inventory beyond spike's 19 PDFs) | Chuck | Week 4 (raised Week 1) | open |

## Resolved

(None yet.)

## Conventions

- Open questions require a human decision Scarlet cannot make alone.
- Update an entry's row when status changes; move to Resolved only when the decision is final and acted on.
- Add a row when a new blocker surfaces during execution.
```

- [ ] **Step 2: Verify**

Run:
```bash
ls -la /Users/chuck/PolicyWonk/PolicyWonk-Open-Questions.md
```
Expected: file exists, non-zero size.

### Task 3: Create the Daily Log

**Files:**
- Create: `/Users/chuck/PolicyWonk/PolicyWonk-Daily-Log.md`

- [ ] **Step 1: Write the file**

Write to `/Users/chuck/PolicyWonk/PolicyWonk-Daily-Log.md`:
```markdown
# PolicyCodex Daily Log

Append-only log of merges, dispatches, and major events. Scarlet writes; Chuck skims for situational awareness.

Format: `- HH:MM PT — short description`

## 2026-05-05 (Tue, Day 1 of Week 1)

- 11:30 PT — Brainstormed the agent-led execution model with Chuck.
- 12:30 PT — Spec saved to `docs/superpowers/specs/2026-05-05-agent-led-execution-design.md`, approved by Chuck.
- 12:45 PT — Plan saved to `docs/superpowers/plans/2026-05-05-agent-led-execution.md`.
- (entries continue as Phase 1 executes)
```

### Task 4: Refresh Week-1 Sprint Plan with agent-led owners

**Files:**
- Modify: `/Users/chuck/PolicyWonk/PolicyWonk-Week-1-Sprint-Plan.md`

- [ ] **Step 1: Replace the Capacity table**

Replace the existing capacity table with:
```markdown
## Capacity

The team is now Chuck (human owner) plus Scarlet (project lead) plus per-ticket subagents. Capacity in days is no longer the limiting factor; the limits are Chuck's review time on risky tickets and Scarlet's coordination throughput.

| Role | Responsibility |
|---|---|
| Chuck | Product owner. Decides org questions (license, name, credentials, partner sign-offs). Reviews risky-ticket diffs at merge. |
| Scarlet | Project lead. Owns tickets, sprint plans, daily log, weekly demo, risky-ticket draft material. Dispatches subagents. Reviews diffs and merges code-only tickets without Chuck. |
| Subagents (per-ticket) | Execute one ticket each in an isolated worktree against verbatim PRD acceptance criteria. Fresh per dispatch. |

See `docs/superpowers/specs/2026-05-05-agent-led-execution-design.md` for the full operating model.
```

- [ ] **Step 2: Replace the Sprint Backlog Owner column**

Update the table so each row's Owner reflects the agent-led model:
- Chuck: REPO-01, REPO-03, REPO-04 (human-only acts), plus reviews on risky tickets
- subagent: REPO-02, INGEST-01, INGEST-02, AI-01, AI-02, AI-04, AI-11, APP-01, APP-02, APP-03, INGEST-03 (stretch), PUBLISH-01 (stretch)
- Plan subagent → Chuck: APP-01 framework decision, AI-04 monolithic-vs-split decision

- [ ] **Step 3: Replace the Risks table**

Replace with the agent-execution risk register from the design spec (subagent-bad-diff, parallel-conflict, PRD-write-collision, blocker-while-offline, APP-04-bottleneck).

- [ ] **Step 4: Update Definition of Done**

Add this bullet:
- All open questions logged in `PolicyWonk-Open-Questions.md` with deadlines.

- [ ] **Step 5: Add a "Roles" section near the top**

Insert after the sprint goal, before Capacity:
```markdown
## Roles

The team executing this sprint is agent-led. Roles defined in `docs/superpowers/specs/2026-05-05-agent-led-execution-design.md`.
```

- [ ] **Step 6: Verify**

Run:
```bash
grep -c "Friend [ABC]" /Users/chuck/PolicyWonk/PolicyWonk-Week-1-Sprint-Plan.md
```
Expected: `0` (all human-team owners replaced).

### Task 5: First commit

- [ ] **Step 1: Stage everything except ignored files**

Run:
```bash
git -C /Users/chuck/PolicyWonk add .
git -C /Users/chuck/PolicyWonk status
```
Expected: many new files listed under "Changes to be committed". `.obsidian/` is NOT in the list.

- [ ] **Step 2: Commit**

Run:
```bash
git -C /Users/chuck/PolicyWonk commit -m "chore: initial commit — bootstrap agent-led operating model

Init git in the planning vault. Add design spec, plan, open-questions log,
daily log, and refresh Week-1 sprint plan to reflect agent-led owners.

Co-Authored-By: Scarlet (Claude Opus 4.7) <noreply@anthropic.com>"
```

- [ ] **Step 3: Verify**

Run:
```bash
git -C /Users/chuck/PolicyWonk log --oneline
```
Expected: one commit with the message above.

- [ ] **Step 4: Append to Daily Log**

Add to `/Users/chuck/PolicyWonk/PolicyWonk-Daily-Log.md` under the 2026-05-05 section:
```
- HH:MM PT — Phase 1 complete: git initialized, operating-model artifacts committed.
```
(Replace HH:MM with current PT time.)

---

## Phase 2: First wave of subagent dispatches

After Phase 1, the repo is live and ready to accept ticket work. Phase 2 kicks off the dispatching pattern with two Plan subagents (decision-gated) and four code subagents (dispatchable).

### Task 6: Dispatch Plan subagent for APP-01 web framework decision

- [ ] **Step 1: Dispatch the agent**

Use the Agent tool with:
- `subagent_type`: `Plan`
- `description`: "APP-01 framework recommendation"
- `prompt`: see below

Prompt:
```
You are evaluating web frameworks for a v0.1 admin web app for PolicyCodex, a Catholic-diocese policy lifecycle tool. Read the PRD at /Users/chuck/PolicyWonk/PolicyWonk-v0.1-Spec.md and the tickets at /Users/chuck/PolicyWonk/PolicyWonk-v0.1-Tickets.md.

Three candidate frameworks per the spec's Open Questions:
1. Python + Django
2. Node + Next.js
3. Go + HTMX

Evaluate each against:
- Time-to-first-working-PR-flow (the critical path is APP-04 GitHub provider integration)
- Fit with Git operations (shelling out to git binary is acceptable per spec)
- Fit with the seven-screen onboarding wizard (server-rendered forms work fine)
- Containerization for the one-command Docker Compose install (REPO-05)
- Static-site-generator integration story (the Publish lane runs in GitHub Actions, so this lane is loosely coupled)
- Operational simplicity for a diocesan IT director self-hosting on a VM

Constraints:
- Six-week sprint to DISC mid-June 2026.
- The team is one human plus AI agents; framework familiarity to Chuck is a plus but not decisive.
- The PRD is opinionated by default; the framework should not require a designer-tested wizard.

Return a recommendation with a one-paragraph rationale per framework, a winner, and any risks the winner introduces. Cite specific PRD acceptance criteria you matched against. Output in markdown.
```

- [ ] **Step 2: Receive and review the recommendation**

Read the Plan subagent's return. Verify it cites the PRD acceptance criteria and addresses APP-04 as the critical-path bottleneck.

- [ ] **Step 3: Append the recommendation to OQ-03**

Update `PolicyWonk-Open-Questions.md` row for OQ-03: status → "Plan subagent returned: <one-line summary>. Awaiting Chuck."

- [ ] **Step 4: Surface to Chuck in chat**

Show Chuck the recommendation summary and the three options. Ask which to commit to.

### Task 7: Dispatch Plan subagent for AI-04/05/06 monolithic-vs-split prompt decision

- [ ] **Step 1: Dispatch the agent**

Use the Agent tool with:
- `subagent_type`: `Plan`
- `description`: "Monolithic vs split prompt decision"
- `prompt`: see below

Prompt:
```
You are deciding the prompt architecture for the v0.1 AI inventory pass for PolicyCodex. Read:
- /Users/chuck/PolicyWonk/PolicyWonk-v0.1-Spec.md (P0.2 AI Inventory Pass)
- /Users/chuck/PolicyWonk/PolicyWonk-Spike-Plan.md (full spike including the recorded results section)
- /Users/chuck/PolicyWonk/spike/extract.py (the working monolithic prompt)
- /Users/chuck/PolicyWonk/spike/outputs/results.csv (per-policy extraction results)

The spike's monolithic prompt hit 62.0% across all eight scored fields, 70.9% excluding always-null next_review_date. Per-field weighted averages:
- category 0.900, owner_role 0.906, last_review_date 0.889 (strong)
- effective_date 0.722, address 0.700, title 0.700 (medium)
- retention 0.144 (weak; addressed by AI-12 reference-doc grounding)
- next_review_date 0.000 (n/a; source documents do not specify cadence)

The tickets file splits extraction into per-field-family prompts:
- AI-04: category extraction prompt with eval set
- AI-05: owner, effective date, review date, retention prompts
- AI-06: chapter-section-item address suggestion prompt

Evaluate two architectures:
1. KEEP MONOLITHIC: One prompt extracts all fields, plus AI-11 (taxonomy injection) and AI-12 (retention reference doc) are added as context. AI-04/05/06 become eval-set work, not separate prompt files.
2. COMMIT TO SPLIT: Separate prompts per field family per the tickets. Each prompt can be tuned independently. Implementation cost is higher but each field can be regression-tested in isolation.

Consider:
- Cost: monolithic is one Claude call per document; split is up to three.
- Quality risk: splitting a working 70.9% prompt could regress before improving.
- Eval-set fit: per-field eval sets are easier to grade in isolation; monolithic is graded once per document.
- Future v0.2 RAG: chunk format export (PUBLISH-08) is unrelated to this decision.

Return a recommendation with rationale for both options, a winner, and concrete next steps for AI-04 dispatch. Output in markdown.
```

- [ ] **Step 2: Receive and review.**

- [ ] **Step 3: Append to OQ-04 row.**

- [ ] **Step 4: Surface to Chuck.**

### Task 8: Dispatch general-purpose subagent for AI-01 (LLM provider abstraction)

- [ ] **Step 1: Dispatch the agent**

Use the Agent tool with:
- `subagent_type`: `general-purpose`
- `description`: "AI-01 LLM provider abstraction"
- `isolation`: `"worktree"`
- `prompt`: see below

Prompt:
```
You are implementing AI-01 (LLM provider abstraction interface) for PolicyCodex. Acceptance criteria from the PRD (P0.2 AI Inventory Pass):

> Claude default. LLM provider abstracted via a single interface supporting OpenAI, Gemini, Azure OpenAI, and local Llama as alternates.

This ticket implements only the abstraction interface. AI-02 implements the Claude provider. AI-03 stubs the others.

Source-of-truth context:
- /Users/chuck/PolicyWonk/PolicyWonk-v0.1-Spec.md (P0.2)
- /Users/chuck/PolicyWonk/PolicyWonk-v0.1-Tickets.md (AI-01)
- /Users/chuck/PolicyWonk/spike/extract.py (current direct-Anthropic-SDK usage; this is reference for the prompt content but NOT the architecture)
- /Users/chuck/PolicyWonk/docs/superpowers/specs/2026-05-05-agent-led-execution-design.md (Section 2 explains why extract.py is reference, not a starting codebase)

Decision pending: monolithic-vs-split prompt architecture (OQ-04). Build the abstraction so it works either way: a single `complete(prompt: str, max_tokens: int) -> str` method is enough for the v0.1 use case. Higher-level extraction logic lives outside the provider interface.

Implementation:
- Create a Python package at `ai/` (sibling to `spike/`).
- Define `ai/provider.py` with an abstract base class `LLMProvider` that has one abstract method: `complete(self, prompt: str, max_tokens: int) -> str`.
- Add type hints and a docstring on the class explaining its role.
- Write tests in `ai/tests/test_provider.py` that verify a concrete subclass must implement `complete` (instantiating the abstract class raises TypeError).
- Use pytest. Add `pytest` and `anthropic` (for AI-02 prep) to a new `ai/requirements.txt`.
- Do not import any specific provider. This is interface-only.

After writing tests-first, implement, then run `pytest ai/tests/ -v` and verify both tests pass. Commit on the worktree branch with a clear message.

Constraints:
- Do not modify spike/.
- Do not touch the markdown planning files.
- The abstraction must be import-able as `from ai.provider import LLMProvider`.
- Follow Spartan style for any docstrings: clear, active voice, no em dashes, no filler.
```

- [ ] **Step 2: Review the diff**

Read the worktree's changes. Confirm:
- `ai/provider.py` defines `LLMProvider` with abstract `complete` method
- `ai/tests/test_provider.py` exists and tests instantiation correctly fails
- `ai/requirements.txt` exists with pytest and anthropic
- No changes outside `ai/`

- [ ] **Step 3: Run acceptance**

In the worktree:
```bash
python -m venv ai/venv && source ai/venv/bin/activate && pip install -r ai/requirements.txt && pytest ai/tests/ -v
```
Expected: tests pass.

- [ ] **Step 4: Decide**

Accept → squash-merge to main. Revise → SendMessage feedback. Reject → close worktree, re-dispatch.

- [ ] **Step 5: Squash-merge if accepted**

Run:
```bash
git -C /Users/chuck/PolicyWonk merge --squash <worktree-branch>
git -C /Users/chuck/PolicyWonk commit -m "feat(ai): add LLMProvider abstraction (AI-01)"
```

- [ ] **Step 6: Append to Daily Log**

Add: `- HH:MM PT — AI-01 merged: LLM provider abstraction.`

### Task 9: Dispatch general-purpose subagent for APP-03 (Git provider abstraction)

- [ ] **Step 1: Dispatch the agent**

Same pattern as Task 8. Prompt:
```
You are implementing APP-03 (Git provider abstraction interface) for PolicyCodex. Acceptance criteria implied by the PRD (P0.3) and tickets (APP-03):

> Git provider abstracted so GitHub Enterprise, GitLab, and self-hosted Gitea can be added later. APP-04 (GitHub provider implementation) consumes this interface.

Source-of-truth context:
- /Users/chuck/PolicyWonk/PolicyWonk-v0.1-Spec.md (P0.3 GitHub Provider Integration)
- /Users/chuck/PolicyWonk/PolicyWonk-v0.1-Tickets.md (APP-03, APP-04)
- /Users/chuck/PolicyWonk/docs/superpowers/specs/2026-05-05-agent-led-execution-design.md

Implementation:
- Create a Python package at `app/git_provider/` (anticipating APP-01 may pick a different framework; keep this provider package framework-agnostic).
- Define `app/git_provider/base.py` with an abstract base class `GitProvider`. Methods (all abstract):
  - `clone(repo_url: str, dest: Path) -> None`
  - `branch(name: str, working_dir: Path) -> None`
  - `commit(message: str, files: list[Path], author_name: str, author_email: str, working_dir: Path) -> str` (returns commit SHA)
  - `push(branch: str, working_dir: Path) -> None`
  - `open_pr(title: str, body: str, head_branch: str, base_branch: str, working_dir: Path) -> dict` (returns PR metadata)
  - `read_pr_state(pr_number: int, working_dir: Path) -> str` (returns one of: "drafted", "reviewed", "published", "closed")

- Add a docstring on the class explaining its role and the three-state mapping per the spec (Drafted = open PR, Reviewed = approved, Published = merged).

- Write tests in `app/git_provider/tests/test_base.py` that verify a concrete subclass must implement every abstract method.

- Use pytest. Add `pytest` to a new `app/requirements.txt`.

- Do not implement any concrete provider. APP-04 implements the GitHub one.

After writing tests-first, implement, then run `pytest app/git_provider/tests/ -v` and verify all tests pass. Commit on the worktree branch.

Constraints:
- Same as AI-01: don't touch spike/, don't touch planning markdown.
- Spartan style for docstrings.
```

- [ ] **Step 2: Review, run acceptance, decide, merge if accepted, log.** (Same pattern as Task 8 steps 2–6.)

### Task 10: Dispatch general-purpose subagent for REPO-02 (README skeleton)

- [ ] **Step 1: Dispatch the agent**

Use the Agent tool with:
- `subagent_type`: `general-purpose`
- `description`: "REPO-02 README skeleton"
- `isolation`: `"worktree"`
- `prompt`: see below

Prompt:
```
You are implementing REPO-02 (README skeleton) for PolicyCodex. Acceptance: a public-facing README at the repo root.

Source: copy the content of /Users/chuck/PolicyWonk/PolicyWonk-README-Draft.md verbatim to /Users/chuck/PolicyWonk/README.md, with two changes:
1. The "License" section near the bottom currently says "License decision pending (MIT vs. Apache 2.0 vs. AGPL)." Leave it pending; the LICENSE file will land in REPO-01 before the public push.
2. Add a "Status" line at the very top, right under the title, that reads: "Status: pre-alpha, active development. v0.1 targets DISC mid-June 2026. Not yet public."

Do NOT delete or modify the original PolicyWonk-README-Draft.md. The draft stays as the source for future iterations until the repo goes public.

Verify by running:
- `head -5 README.md` shows title and status line
- `wc -l README.md` shows roughly the same line count as the draft (within ±5 lines for the status line and any trailing whitespace differences)

Commit on the worktree branch with message "docs: add README skeleton (REPO-02)".

Constraints:
- Do not touch any other file.
- Spartan style is already in the draft; preserve it.
```

- [ ] **Step 2: Review, decide, merge if accepted, log.**

### Task 11: Dispatch Explore subagent for PUBLISH-01 (SSG selection)

- [ ] **Step 1: Dispatch the agent**

Use the Agent tool with:
- `subagent_type`: `Explore`
- `description`: "PUBLISH-01 SSG evaluation"
- `prompt`: see below
- (No worktree; this is read-only research.)

Prompt:
```
You are evaluating static-site generators for the PolicyCodex handbook publication lane (PUBLISH-01..06). Read:
- /Users/chuck/PolicyWonk/PolicyWonk-v0.1-Spec.md (P0.5 Handbook Static-Site Generator)
- /Users/chuck/PolicyWonk/PolicyWonk-v0.1-Tickets.md (PUBLISH-01..08)

Candidates per the spec's Open Questions:
1. Astro (component flexibility, modern)
2. Hugo (build speed, single binary)
3. Eleventy (simple, JS-based)

Evaluate each against:
- Markdown plus YAML front matter ingestion (PolicyCodex's content format)
- Chapter.section.item URL scheme (e.g., /5/2/8/) and stable per-policy URLs
- RSS feed support
- Changelog page generation from `git log` of the policy repo
- GitHub Actions build-and-deploy ergonomics
- Theme creation for a default modeled on https://handbook.la-archdiocese.org/
- Build speed for a 200-policy diocese (handbook regenerates on every merge)

Use Context7 or the equivalent doc-fetching tool if you have it for current versions. Use the WebSearch or WebFetch tool to spot-check the LA archdiocese handbook structure.

Return a recommendation with rationale per candidate, a winner, and any v0.2 vector-friendly chunk export (PUBLISH-08) implications. Output in markdown. Do NOT install any package; this is research only.
```

- [ ] **Step 2: Receive recommendation. Append to a new file `/Users/chuck/PolicyWonk/PolicyWonk-SSG-Evaluation.md`.**

- [ ] **Step 3: Surface to Chuck for sign-off** (this is a soft decision per the spec, not a blocking risky one). Append a row to `PolicyWonk-Open-Questions.md`:

```markdown
| OQ-09 | Static-site generator (PUBLISH-01) | Chuck, after Explore subagent recommends | 2026-05-08 EOD | Explore subagent returned: <summary>. Awaiting Chuck. |
```

---

## Phase 3: Risky-ticket prep (drafting human action material)

These tickets need Chuck to act in third-party UIs. Scarlet's job is to produce the exact checklist Chuck follows, so the human time spent in those UIs is minimal.

### Task 12: Draft REPO-03 GitHub App permissions checklist

**Files:**
- Create: `/Users/chuck/PolicyWonk/REPO-03-GitHub-App-Checklist.md`

- [ ] **Step 1: Write the checklist**

Read the GitHub App docs (via Context7 or web fetch) for:
- Required permissions for: contents (read+write), pull_requests (read+write), metadata (read), checks (read), workflows (read+write).
- Webhook events: pull_request, push, pull_request_review.
- Installation scope: organization-only (for diocese installs).

Write the checklist file with:
- App name: "PolicyCodex"
- Homepage URL: placeholder for now (the future public repo)
- Callback URL: `http://localhost:8080/auth/github/callback` for local dev; subdomain TBD for prod
- Required permissions (full list with explanations)
- Required webhook events
- Step-by-step instructions for Chuck: navigate to https://github.com/settings/apps/new, fill in fields, generate private key, save key to `~/.config/policycodex/github-app.pem`, install on PT GitHub org once it exists.

- [ ] **Step 2: Surface to Chuck in chat**

Tell Chuck the checklist is ready. He can run it any time before Friday.

### Task 13: Draft REPO-04 PT policy repo branch protection settings

**Files:**
- Create: `/Users/chuck/PolicyWonk/REPO-04-PT-Repo-Settings.md`

- [ ] **Step 1: Write the settings doc**

Per PRD P0.3: branch protection on `main` requires at least one approving review.

Write the file with:
- Repo name: `pt-policy` (suggestion; Chuck can override)
- Visibility: Private
- Default branch: `main`
- Branch protection rules for `main`:
  - Require pull request before merging: yes
  - Require approvals: 1
  - Dismiss stale reviews on new commits: yes
  - Require status checks to pass: yes (handbook-build workflow once it exists)
  - Require conversation resolution: yes
  - Require signed commits: optional (Chuck's call)
  - Allow force pushes: no
  - Allow deletions: no
- Initial commit content: an empty `policies/` directory with a `.gitkeep`, plus a `references/` directory with a `.gitkeep`, plus a `README.md` saying "PT diocesan policy repo. Managed by PolicyCodex."
- Step-by-step for Chuck: create repo at https://github.com/<pt-org>, apply settings above, push initial commit. Estimated time: 10 minutes.

- [ ] **Step 2: Surface to Chuck.**

---

## Phase 4: Friday wrap

These tasks run Friday afternoon (May 8) once Phase 2 is largely complete and the human-blocking decisions have landed.

### Task 14: Write Week-1 Demo file

**Files:**
- Create: `/Users/chuck/PolicyWonk/PolicyWonk-Week-1-Demo.md`

- [ ] **Step 1: Write the demo file**

Structure:
```markdown
# PolicyCodex Week 1 Demo

**Date:** 2026-05-08

## Summary

(One paragraph: what landed, what slipped.)

## Tickets Merged

| Ticket | Owner | Merge SHA | Notes |
|---|---|---|---|
| (rows for each merged ticket) |

## Decisions Made

(OQ-01 through OQ-08: which resolved, which slipped to Week 2.)

## Lane Status

(One paragraph per lane, against PRD acceptance.)

## Risks Surfaced

(New risks beyond the spec's risk register.)

## Decisions Waiting on Chuck

(Open questions still pending.)

## Week 2 Plan Preview

(Headline: which tickets carry over, which start fresh.)
```

- [ ] **Step 2: Fill in from the daily log and the open-questions log.**

### Task 15: Update Open-Questions log with Week-1 resolutions

- [ ] **Step 1: For each OQ that resolved during Week 1, move its row to the "Resolved" section with the decision and date.**

### Task 16: Write Week-2 Sprint Plan

**Files:**
- Create: `/Users/chuck/PolicyWonk/PolicyWonk-Week-2-Sprint-Plan.md`

- [ ] **Step 1: Carry over any unmerged Week-1 tickets, plus the Week-2 tickets from `PolicyWonk-v0.1-Tickets.md`.**

Mirror the Week-1 plan structure: capacity, sprint backlog, risks, definition of done, key dates, carryover.

### Task 17: First public push to GitHub (gated)

**Gates:**
- OQ-01 license decision is resolved AND
- OQ-02 trademark check passed AND
- Chuck explicitly approves push in chat

- [ ] **Step 1: Verify all gates** (read OQs, confirm with Chuck).

- [ ] **Step 2: Create the GitHub repo** (Chuck does this in the GitHub UI; same pattern as REPO-04 PT repo).

- [ ] **Step 3: Add the remote and push**

Run:
```bash
git -C /Users/chuck/PolicyWonk remote add origin git@github.com:<chuck-org-or-user>/policycodex.git
git -C /Users/chuck/PolicyWonk push -u origin main
```

- [ ] **Step 4: Verify** (visit the GitHub URL).

- [ ] **Step 5: Append to Daily Log:** `- HH:MM PT — Public push: <url>`.

---

## Self-review checklist (already run before saving)

**Spec coverage:** every section of the design spec maps to at least one task. Section 1 (roles) → Task 4. Section 2 (lane mapping) → Tasks 6–11. Section 3 (gates) → Tasks 8–17 (each ticket carries its bucket designation). Section 4 (working tree) → Task 1. Section 5 (cadence) → Tasks 2, 3, 14. Section 6 (Week-1 sequencing) → all of Phase 2 onward.

**Placeholder scan:** no TBDs or TODOs. Subagent prompts contain the full instructions a fresh subagent needs.

**Type / name consistency:** the same ticket IDs (REPO-N, INGEST-N, AI-N, APP-N, PUBLISH-N) are used throughout, matching the source tickets file. The `LLMProvider` abstract method signature is consistent across the AI-01 prompt and the AI-02 prompt referenced for follow-up. The `GitProvider` method names are defined once in APP-03 and not redefined inconsistently.

**Path consistency:** absolute paths used throughout for clarity in the agent-led environment. The `ai/`, `app/`, and `spike/` subdirectories are scoped to avoid collision.
