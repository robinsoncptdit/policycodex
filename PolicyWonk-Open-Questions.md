# PolicyCodex Open Questions

Source-of-truth log for blockers and pending human decisions during the v0.1 sprint. Scarlet writes this; Chuck reads, decides, and confirms in chat.

## Active

| ID | Question | Owner | Deadline | Status |
|---|---|---|---|---|
| OQ-02 | TESS search on PolicyCodex in classes 9 and 42, before first public push. | Chuck | before first public push | re-opened 2026-05-11 after rename; prior form ("PolicyWonk" trademark) marked resolved below |
| OQ-04 | Monolithic vs split prompt (AI-04/05/06) | Chuck, after Plan subagent recommends | 2026-05-08 EOD (slipped from 2026-05-06) | Plan subagent returned: **KEEP MONOLITHIC** (already passes 60% gate at 70.9%; reframe AI-04/05/06 as eval-set tickets; AI-11+AI-12 layer in as context). Plan B if retention &lt;0.70 after AI-12: split retention sub-prompt. See `PolicyWonk-Prompt-Architecture-Decision.md`. Awaiting Chuck. |
| OQ-05 | LA contact's role in README | Chuck | 2026-05-15 (Week 2) | open |
| OQ-06 | PT diocesan leadership sign-off for handbook subdomain | Chuck | Week 4 | raised |
| OQ-08 | PT policy corpus exported to a local folder (full inventory beyond spike's 19 PDFs) | Chuck | Week 4 (raised Week 1) | open |
| OQ-10 | Upgrade PT GitHub org from Free to Team tier (~$4/user/month) to enable private-repo branch protection. | Chuck + PT IT director | before week 4 lane acceptance | **Deferred 2026-05-11** by Chuck. Ruleset stays configured but unenforced on `pt-policy` for now. APP-04 development is unblocked. Must resolve before week 4 lane acceptance to satisfy PRD G3 (audit trail). Re-raise when budget conversation with PT IT director happens. |

## Resolved

| ID | Question | Resolution |
|---|---|---|
| OQ-01 | License: MIT, Apache 2.0, or AGPL? | Resolved 2026-05-11: AGPL-3.0. PRD updated with a new Licensing section; canonical AGPL-3.0 text committed as `LICENSE` (REPO-01). |
| OQ-07 | PT GitHub org availability or creation | Resolved 2026-05-11: PT lives at `https://github.com/Diocese-of-Pensacola-Tallahassee`. REPO-04 unblocked. |
| OQ-03 | Web framework choice (APP-01) | Resolved 2026-05-11: **Python + Django** (per Plan subagent recommendation in `PolicyWonk-Framework-Evaluation.md`). APP-01 skeleton + APP-02 unblocked. |
| OQ-09 | Static-site generator (PUBLISH-01) | Resolved 2026-05-11: **Astro** (Chuck overrode the Explore subagent's Hugo recommendation). Driver: parish web teams forking the handbook theme will find Astro's component model more approachable than Hugo's Go templates. PUBLISH-01 build-it work + PUBLISH-02 URL scheme unblocked. Subagent rationale and trade-offs preserved in `PolicyWonk-SSG-Evaluation.md` for the record. |
| OQ-02 (prior form) | "PolicyWonk" trademark availability | Resolved 2026-05-11. PolicyWonk did not clear; project renamed to PolicyCodex. Reopened above as the new TESS search on PolicyCodex (classes 9 and 42). |

## Conventions

- Open questions require a human decision Scarlet cannot make alone.
- Update an entry's row when status changes; move to Resolved only when the decision is final and acted on.
- Add a row when a new blocker surfaces during execution.
