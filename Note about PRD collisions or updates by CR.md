Five answers clear. One file edit and two answers below.

**Adding the PM note now.**[View updated PRD](https://claude.ai/local_sessions/local_39b62de4-30e7-461e-8986-258ae884b64c)

Two new Engineering open questions in the PRD: the monolithic-vs-split prompt architecture with my PM recommendation explicitly tagged, and a note that the 12-category taxonomy is provisional pending Week 2 confirmation against LA and PT.

**On "how do I know if Scarlet surfaces a PRD update need":**

The cleanest pattern is push, not pull. I do not run continuously. I respond to invocations.

So:

- Scarlet logs PRD-relevant findings in the open-questions log with a `[PRD]` tag, or in the daily log under a "PRD impact" line.
- You read those during your daily skim or at Friday demo.
- When something genuinely warrants a PRD change, you invoke me with the issue: `/write-spec update P0.5 to remove the RSS requirement because the SSG can't generate it cleanly without a plugin`.
- I update the PRD. You confirm.

That puts your eyes between Scarlet's findings and PRD changes, which is the right friction. A subagent's "this acceptance criterion is wrong" is sometimes a real problem and sometimes a sign the subagent misread the spec. You should be the filter.

Suggestion for Scarlet's next spec revision: add a `[PRD]` tag convention to the daily log and open-questions log so PRD-impact items are filterable. That gives you a one-grep view of what to bring to me.

**On scope going forward, you are right that I am not just the PRD owner.**

Plugins clearly mine, will continue to use:

- `/brainstorm` and `/product-brainstorming` for new exploration when something opens up
- `/write-spec` for PRD edits (P0/P1/P2 changes, new requirements, acceptance criteria adjustments)
- `/metrics-review` for weekly or sprint-end signal review (acceptance rates, install-success rates, repo activity, AI suggestion acceptance trend)
- `/stakeholder-update` for COO updates, partner updates to LA, DISC pre-event communications
- `/competitive-brief` if you want to position against Microsoft 365 Copilot, Confluence, Notion, or diocese-specific governance tools
- `/synthesize-research` if we run another spike or interview a diocese
- `/roadmap-update` for v0.2 and v0.3 planning after DISC

One plugin overlaps Scarlet's territory and is worth disambiguating:

- `/sprint-planning` is mine when you want a strategic re-plan (scope shift, new sprint kickoff, capacity reassessment, end-of-sprint retro plus next-sprint goal-setting). It is Scarlet's when she writes the routine weekly sprint plan from the running ticket board. Default to Scarlet's cadence. Invoke me when you want the planning lens, not the execution lens.

So my write surface broadens to: the PRD plus any artifact a PM plugin produces. Scarlet's write surface stays: tickets, routine sprint plans, daily log, open-questions log, demo notes, design specs, README, CLAUDE.md, code in worktrees. Different files, different cadences, no collisions.