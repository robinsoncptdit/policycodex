# PolicyCodex v0.1 Closeout Checklist

*Created 2026-06-08. The "don't forget" list to walk through when v0.1 ships. Trigger: end-of-Week-5 feature freeze + a clean DISC demo + a confident "we're done" call.*

## How to use this

When v0.1 is shipped and stable (post-DISC dust settles, no critical fix-forward in flight), open this file and walk it top to bottom. Items get checked off as they land. If items get added during DISC or the post-DISC tail, append them here so the next walk catches them.

The CLAUDE.md compression item below is the single most important entry. Doing it transitions the project from "v0.1 sprint mode" to "v0.2 design mode" mentally and contextually.

## Closeout items

### Context and documentation

- [ ] **CLAUDE.md compression (REPO-13, S).** Snapshot the v0.1-era `CLAUDE.md` as `internal/PolicyCodex-v0.1-Closeout.md` before any edits, preserving the rich sprint narrative for archeology. Then rewrite `CLAUDE.md` fresh for the v0.2 cycle. Target size roughly 2,000 tokens (down from ~5,000). Structure: What This Project Is (unchanged), Current Status (one paragraph naming v0.1 ship date and v0.2 opening), What's In This Folder (trimmed to only what a v0.2 agent needs), What Has Already Been Reconsidered and Locked (mostly preserved, the high-value section), Style Preferences (unchanged). Decision rationale: the existing "Current Status" paragraph is ~2,000 tokens of sprint narrative that becomes post-mortem the moment v0.1 ships. See the 2026-06-08 chat with Chuck where this was scoped.
- [ ] **Public `README.md` status line update.** Change from current "Active development, targeting DISC mid-June 2026" framing to "v0.1 shipped DATE. Install instructions below." Refresh the version badge if one exists.
- [ ] **Update PRD `Current Status` framing.** The PRD says "Target: working demo + public repo by DISC mid-June 2026" near the top. Update to "v0.1 shipped DATE. v0.2 in design." Keep the PRD as the canonical v0.1 specification for the shipped artifact.

### v0.2 cycle kickoff

- [ ] **Draft `PolicyCodex-v0.2-Spec.md` and `PolicyCodex-v0.2-Tickets.md`** as fresh files. Do not edit the v0.1 files in place. The v0.1 record stays clean as the shipped artifact. Per Chuck (2026-06-08), the drafting happens here in Cowork via the `/product-management:write-spec` plugin. Input materials: `internal/PolicyCodex-v0.2-Brainstorm.md`, actual DISC feedback, any post-DISC install reports.
- [ ] **PM brainstorm refresh against real DISC signal.** Run `/product-management:product-brainstorming` after collecting at least two weeks of post-DISC feedback. Refresh the rank-1-through-5 list in the brainstorm doc against what dioceses actually asked for, not what we guessed in June 2026.
- [ ] **Decide v0.2 design partner.** PT was install zero for v0.1. Carry forward, move primary to LA, or let whichever diocese installs second drive v0.2? See open question in the brainstorm doc.

### Sprint artifact tidy

- [ ] **Archive Week-N sprint files.** Move `internal/PolicyWonk-Week-{1,2,3,4,5}-Sprint-Plan.md` and `internal/PolicyWonk-Week-{1,2,3,4}-Demo.md` files into `internal/v0.1-sprint-archive/` or similar. Keep them tracked (not deleted) but get them out of the active workspace listing.
- [ ] **Daily log rollover.** The append-only `internal/PolicyWonk-Daily-Log.md` is rich v0.1 narrative. Either keep appending into v0.2 (single living log) or snapshot and start fresh as `internal/PolicyCodex-v0.2-Daily-Log.md`. Chuck and Scarlet decide.

### Tickets already deferred to post-v0.1

These were filed during v0.1 but explicitly scoped as post-DISC or post-freeze. Pull each into the v0.2 ticket file or close as obsolete:

- [ ] **APP-26 (L, post-DISC).** Foundational editor hardening + demo polish (title-case headers, pagination for large schedules, soft-delete semantics, mtime concurrency guard, reuse from detail view).
- [ ] **INGEST-08 (S, post-freeze).** Flag image-only / scanned source documents during the inventory pass (warning surface for what APP-30 guards inside the wizard).

### Spec items pulled forward from v0.2 brainstorm

These got architectural P2 entries in the v0.1 spec. When v0.2 work starts, they become real tickets:

- [ ] **P2.7** Wizard-managed handbook publishing (subdomain collected in wizard, CNAME committed automatically).
- [ ] **P2.8** AI-assisted policy authoring (CFO chat to draft new policies).
- [ ] **P2.9** Targeted policy re-extraction (single policy from source).
- [ ] **P2.10** Bulk corpus re-ingest with gate-state preservation (three modes A/B/C).
- [ ] **P2.11** AI provider key management remainder (spend ceiling + test-connection button; the v0.1 minimum already landed via APP-31 + AI-16).

Plus the pre-existing P2.X entries that were already there before this brainstorm:

- [ ] **P2.1** Q&A Chatbot (RAG over the handbook).
- [ ] **P2.2** Full Seven-Gate Workflow.
- [ ] **P2.3** Git Provider Pluggability (GitHub Enterprise, GitLab, Gitea).
- [ ] **P2.4** Multi-Tenant Hosting.
- [ ] **P2.5** Regulatory Change Watching.
- [ ] **P2.6** Multilingual Handbook.

### Post-DISC retrospective

- [ ] **Capture DISC feedback in a structured doc.** `internal/PolicyCodex-DISC-2026-Feedback.md`. Names of attendees who engaged, install attempts, feature requests, criticisms, partnership conversations. This becomes the input signal for the v0.2 brainstorm refresh.
- [ ] **Write the post-DISC stakeholder update.** Use `/product-management:stakeholder-update`. Audience: any diocesan IT directors who attended, plus design partners. Frame v0.1 outcomes, v0.2 direction, how to engage.
- [ ] **Open question retro.** Review `internal/PolicyWonk-Open-Questions.md`. Confirm every Resolved entry held up under real install conditions. Anything that needs to be reopened gets filed in the v0.2 OQ tracker.

## Additions during the v0.1 tail

Append new closeout items here as they surface between now and ship. Each addition gets a date and a short note about origin.

- [ ] **Visual storyboard of the onboarding wizard sequence** (added 2026-06-08 from Chuck's user-journey walkthrough question). Linear, page-by-page mockup showing the full onboarding flow: install → seven wizard screens → completion screen → onboarding PR merge → DNS + Pages configuration → bulk inventory ingest → first reviewed/published policy → handbook live. Modeled on the `internal/mockups/disc-demo-tailwind.html` aesthetic. Useful at DISC for "here's what your first 30 minutes with PolicyCodex looks like" without making attendees install the demo themselves. Chuck deferred this to "later" with a remember-it instruction; if DISC prep time is tight, this could slip to post-DISC v0.2 marketing materials.
