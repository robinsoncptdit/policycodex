# PolicyWonk Open Questions

Source-of-truth log for blockers and pending human decisions during the v0.1 sprint. Scarlet writes this; Chuck reads, decides, and confirms in chat.

## Active

| ID | Question | Owner | Deadline | Status |
|---|---|---|---|---|
| OQ-01 | License: MIT, Apache 2.0, or AGPL? Fallback AGPL. | Chuck | 2026-05-08 EOD | open |
| OQ-02 | "PolicyWonk" trademark availability | Chuck | 2026-05-08 EOD | open |
| OQ-03 | Web framework choice (APP-01) | Chuck, after Plan subagent recommends | 2026-05-08 EOD (slipped from 2026-05-06) | Plan subagent returned: **Python + Django** (in-process import of Friday's Python interfaces; FormWizard fits the seven-screen wizard). See `PolicyWonk-Framework-Evaluation.md`. Awaiting Chuck. |
| OQ-04 | Monolithic vs split prompt (AI-04/05/06) | Chuck, after Plan subagent recommends | 2026-05-08 EOD (slipped from 2026-05-06) | Plan subagent returned: **KEEP MONOLITHIC** (already passes 60% gate at 70.9%; reframe AI-04/05/06 as eval-set tickets; AI-11+AI-12 layer in as context). Plan B if retention &lt;0.70 after AI-12: split retention sub-prompt. See `PolicyWonk-Prompt-Architecture-Decision.md`. Awaiting Chuck. |
| OQ-05 | LA contact's role in README | Chuck | 2026-05-15 (Week 2) | open |
| OQ-06 | PT diocesan leadership sign-off for handbook subdomain | Chuck | Week 4 | raised |
| OQ-07 | PT GitHub org availability or creation | Chuck | 2026-05-08 EOD (slipped from 2026-05-06) | open |
| OQ-08 | PT policy corpus exported to a local folder (full inventory beyond spike's 19 PDFs) | Chuck | Week 4 (raised Week 1) | open |
| OQ-09 | Static-site generator (PUBLISH-01) | Chuck, after Explore subagent recommends | 2026-05-08 EOD | Explore subagent returned: **Hugo** (build speed, simple GitHub Actions story, native Markdown+YAML; trade-off is less flexibility for v0.2 dynamic content). See `PolicyWonk-SSG-Evaluation.md`. Awaiting Chuck. |

## Resolved

(None yet.)

## Conventions

- Open questions require a human decision Scarlet cannot make alone.
- Update an entry's row when status changes; move to Resolved only when the decision is final and acted on.
- Add a row when a new blocker surfaces during execution.
