# PolicyCodex Week 1 Demo

**Date:** 2026-05-08
**Operating model:** Agent-led (per `docs/superpowers/specs/2026-05-05-agent-led-execution-design.md`)

## Summary

Week 1 was a soft start. The brainstorm, design spec, and execution plan all landed on Tuesday May 5, but execution didn't start until Friday May 8 — partly because Chuck was working other priorities Tue-Thu, and partly because the Cowork PM plugin landed a substantive PRD update midday Friday (P0.1 reframed from SharePoint+local to local-folder-only; P1.2 reframed as a v0.2 connector pluggability framework). That PRD edit triggered a tickets/sprint-plan reconciliation pass before any code dispatches could happen. The actual Week 1 work then ran as a single Friday-evening push: bootstrap + Phase 2 dispatches + Phase 3 prep + Phase 4 wrap, all in one sitting.

The push landed cleanly. Both Plan-subagent decisions are back and ready for Chuck. AI-01 is merged. APP-03 is in flight at the time of writing. REPO-02 is queued.

## Tickets Merged (Friday push)

| Ticket | Owner | Merge SHA | Notes |
|---|---|---|---|
| Bootstrap | Scarlet | ca3a38a | git init, .gitignore, Open-Questions log, Daily Log, Week-1 sprint plan refresh, all planning markdown |
| AI-01 LLMProvider abstraction | subagent (Haiku) | d837279 | 4 tests passing, importable as `from ai.provider import LLMProvider` |
| APP-03 GitProvider abstraction | subagent (Haiku) | cf4b6c2 | 7 tests passing (one per abstract method), six methods covering clone/branch/commit/push/open_pr/read_pr_state |
| REPO-02 README skeleton | subagent (Haiku) | cad3fbb | 149 lines, +2 over draft (Status line + blank), license stays pending |

## Decisions Made (Plan-subagent recommendations awaiting Chuck)

| OQ | Decision area | Subagent recommendation | Status |
|---|---|---|---|
| OQ-03 | Web framework (APP-01) | **Python + Django** (in-process import of Friday's Python interfaces; FormWizard fits the seven-screen wizard) | Awaiting Chuck |
| OQ-04 | Prompt architecture (AI-04/05/06) | **KEEP MONOLITHIC** (passes 60% gate at 70.9%; reframe AI-04/05/06 as eval-set tickets; AI-11+AI-12 layer in as context) | Awaiting Chuck |
| OQ-09 | Static-site generator (PUBLISH-01) | **Hugo** (build speed, simple GitHub Actions, native Markdown+YAML) | Awaiting Chuck |

## Decisions Slipped to Week 2

| OQ | Decision area | Why slipped |
|---|---|---|
| OQ-01 | License (MIT/Apache 2.0/AGPL) | Chuck not yet decided; fallback AGPL stands |
| OQ-02 | "PolicyCodex" trademark check | Chuck still investigating |
| OQ-07 | PT GitHub org availability | Awaiting PT IT confirmation |
| OQ-08 | PT corpus full export to local folder | Week 4 dependency, raised early |
| OQ-05 | LA contact's role in README | Week 2 deadline |
| OQ-06 | PT diocesan leadership sign-off for handbook subdomain | Week 4 dependency, raised early |

## Lane Status

**Cross-Cutting (REPO):** REPO-02 README in flight via subagent. REPO-03 GitHub App registration checklist drafted (`REPO-03-GitHub-App-Checklist.md`); Chuck's action item, ~15 min in the GitHub UI. REPO-04 PT repo settings drafted (`REPO-04-PT-Repo-Settings.md`); Chuck's action item once PT GitHub org exists. REPO-01 license unresolved.

**Ingest (P0.1):** No tickets dispatched in Week 1. INGEST-01 (local folder reader) is small (1 day) and starts Week 2. The PRD's mid-Friday pivot to local-folder-only ingest simplified this lane substantially.

**AI (P0.2):** AI-01 merged (LLMProvider abstraction). AI-02 (Claude provider impl) ready for Week 2. AI-04/05/06 reframed as eval-set tickets per the monolithic-vs-split recommendation; concrete next steps in `PolicyWonk-Prompt-Architecture-Decision.md`. AI-11 + AI-12 still scheduled for Week 1-2 per original plan.

**App (P0.3 + P0.4 + P0.6):** APP-03 (Git provider abstraction) in flight. Framework decision (APP-01 Python+Django) pending Chuck. APP-01 skeleton + APP-02 (auth) start Week 2 once Chuck signs off.

**Publish (P0.5):** PUBLISH-01 SSG evaluation done (Hugo recommended). Build-it work starts Week 2.

## Risks Surfaced

- **Tuesday-Thursday execution slip.** The agent-led plan was written Tuesday but not executed until Friday. Calendar lost: ~3 working days. Week 2 still hits the v0.1 timeline because the Friday push compressed Week 1 well, but a repeat slip in Week 2 would put DISC at risk. Mitigation: kick off Monday morning with the carryover tickets immediately rather than re-deciding scope.
- **Subagent worktree isolation failed mid-session.** The harness cached "is a git repository: false" at session start (when no .git existed), so the Agent tool's `isolation: "worktree"` parameter rejected three dispatches after the bootstrap commit. Fallback: dispatch without worktree, commit directly to main, sequential to avoid race conditions. The agent-led design spec assumed worktree isolation would work in every session; documented exception for sessions that init the repo mid-way. Mitigation: future Scarlet sessions inherit a git-repo-existing world, so this is a one-time issue.
- **Subagent dependency-pin drift.** Haiku-4.5 subagents pinned `anthropic==0.41.1` from training data; that exact version doesn't exist on current PyPI. Fixed by relaxing to `anthropic>=0.40`. Lesson for Week 2 prompts: explicitly tell subagents to use floor-constraints (`>=`) on pip dependencies, not exact pins, unless there's a known compatibility reason.
- **Subagents lacking shell permission.** Haiku-4.5 subagent for AI-01 wrote files but couldn't run pytest or git commands due to permission scoping in the parent session. Scarlet ran tests + commit on its behalf, which works but breaks the design spec's "subagent self-tests then commits" loop. Mitigation for Week 2: either pre-approve shell permissions for code subagents or accept the inline-verification pattern as the new normal.

## Decisions Waiting on Chuck (Monday morning)

1. **OQ-01 license decision** (or confirm AGPL fallback). Public push depends on it.
2. **OQ-03 Django sign-off** (or counter-pick). APP-01 skeleton dispatch depends on it.
3. **OQ-04 monolithic-prompt sign-off** (or commit to split). AI-04 dispatch depends on it.
4. **OQ-09 Hugo sign-off** (or counter-pick). PUBLISH-01 build-it work depends on it.
5. **OQ-07 PT GitHub org status.** REPO-04 execution depends on it.
6. **REPO-03 / REPO-04 actions.** Chuck runs the checklists when ready; outputs (App ID, repo URL, etc.) come back to Scarlet for APP-04 wiring.

## Week 2 Plan Preview

See `PolicyWonk-Week-2-Sprint-Plan.md` for the forward-looking artifact. Headline: pick up the carryover (INGEST-01, AI-02, INGEST-02, INGEST-03, AI-04 eval-set, AI-11, APP-01 skeleton, APP-02, PUBLISH-01 build-it work) plus the Week-2-native tickets (APP-04 GitHub provider, AI-12 retention reference, PUBLISH-02 URL scheme, REPO-04 PT repo creation if Chuck does it Monday). Hard scope freeze still hits end of Week 2.
