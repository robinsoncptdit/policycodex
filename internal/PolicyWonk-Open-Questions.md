# PolicyCodex Open Questions

Source-of-truth log for blockers and pending human decisions during the v0.1 sprint. Scarlet writes this; Chuck reads, decides, and confirms in chat.

## Active

| ID | Question | Owner | Deadline | Status |
|---|---|---|---|---|
| OQ-05 | LA contact's role in README | Chuck | 2026-05-15 (Week 2) | **open.** Next action (Chuck): message Patrick this week to confirm whether he's named as "design reviewer," "design partner," or another role; loop the language back. README update is a small follow-up commit once decided. |
| OQ-06 | PT diocesan leadership sign-off for handbook subdomain | Chuck | Week 4 | raised. Start the conversation by Week 3 to absorb diocese-side approval lead time. |
| OQ-08 | PT policy corpus exported to a local folder (full inventory beyond spike's 19 PDFs) | Chuck | Week 4 (raised Week 1) | **open.** Next action (Chuck): pick a target date for export, ideally end of Week 2. INGEST scale test (Week 4) and AI eval ground-truth volume both depend on this. The 19 spike PDFs are enough to develop against in the meantime. |
| OQ-10 | Upgrade PT GitHub org from Free to Team tier (~$4/user/month) to enable private-repo branch protection. | Chuck + PT IT director | before week 4 lane acceptance | **Graduated to ticket REPO-08 on 2026-05-12.** Original deferral context: Ruleset stays configured but unenforced on `pt-policy`. APP-04 development unblocked. Must resolve before week 4 lane acceptance to satisfy PRD G3 (audit trail). Re-raise when budget conversation with PT IT director happens. Track via REPO-08 going forward. |
| OQ-12 | Fresh git worktrees fail two `spike/eval/test_run_eval.py` tests because `spike/outputs/*.json` is gitignored and not carried over. Three options: (a) un-gitignore the canonical 19 outputs and treat them as committed eval fixtures, (b) make the eval harness regenerate-on-miss or skip-on-miss, (c) add a worktree-bootstrap step (Makefile target or `claude/hooks` entry) that copies cached outputs in. (a) is the simplest and matches the project's "ground truth in repo" pattern; (b) is the safest if outputs get large; (c) doesn't help non-worktree fresh clones. | Scarlet | before Week 3 sprint kickoff | **open.** Surfaced 2026-05-13 by both INGEST-03 and APP-02 code reviewers. Not blocking: tests pass cleanly from the main repo cwd. Affects subagent verification only, not CI or local dev. |

## Resolved

| ID | Question | Resolution |
|---|---|---|
| OQ-01 | License: MIT, Apache 2.0, or AGPL? | Resolved 2026-05-11: AGPL-3.0. PRD updated with a new Licensing section; canonical AGPL-3.0 text committed as `LICENSE` (REPO-01). |
| OQ-04 | Monolithic vs split prompt (AI-04/05/06) | Resolved 2026-05-12: **KEEP MONOLITHIC** (Chuck signed off on Plan subagent recommendation). AI-04/05/06 reframed as eval-set tickets against the monolithic prompt; AI-11 + AI-12 layer in as additive context. Plan B if retention <0.70 after AI-12: split retention sub-prompt. Rationale in `internal/PolicyWonk-Prompt-Architecture-Decision.md`. |
| OQ-07 | PT GitHub org availability or creation | Resolved 2026-05-11: PT lives at `https://github.com/Diocese-of-Pensacola-Tallahassee`. REPO-04 unblocked. |
| OQ-03 | Web framework choice (APP-01) | Resolved 2026-05-11: **Python + Django** (per Plan subagent recommendation in `internal/PolicyWonk-Framework-Evaluation.md`). APP-01 skeleton + APP-02 unblocked. |
| OQ-09 | Static-site generator (PUBLISH-01) | Resolved 2026-05-11: **Astro** (Chuck overrode the Explore subagent's Hugo recommendation). Driver: parish web teams forking the handbook theme will find Astro's component model more approachable than Hugo's Go templates. PUBLISH-01 build-it work + PUBLISH-02 URL scheme unblocked. Subagent rationale and trade-offs preserved in `internal/PolicyWonk-SSG-Evaluation.md` for the record. |
| OQ-02 (prior form) | "PolicyWonk" trademark availability | Resolved 2026-05-11. PolicyWonk did not clear; project renamed to PolicyCodex. Reopened as the new TESS search on PolicyCodex (classes 9 and 42); see below. |
| OQ-02 | TESS search on PolicyCodex in classes 9 and 42, before first public push. | Resolved 2026-05-11. Chuck ran the USPTO TESS search on "PolicyCodex" and "Policy Codex" in classes 9 (downloadable software) and 42 (SaaS). **No wordmark hits.** First-public-push trademark gate clear. No registration filed yet; revisit if the project ever monetizes under the PolicyCodex name. |
| OQ-11 | Verify INGEST-01's symlink-skip behavior on Python 3.12. | Resolved 2026-05-13. The reviewer's premise was incorrect: raw `Path.rglob("*")` does NOT descend dir-symlinks on 3.11, 3.13, or 3.14 (verified on Chuck's macOS dev machine with the actual `LocalFolderConnector`). The Python 3.13 change merely formalized the long-standing default by adding `recurse_symlinks=False` as an explicit kwarg; the behavior itself didn't change. 3.11 brackets 3.12 from below, 3.13 brackets it from above. Both pass the new `test_walk_does_not_descend_into_dir_symlinks` regression guard added to `ingest/tests/test_local_folder.py`. Python 3.12 was not installed locally, but the bracketing evidence plus the rglob-signature continuity is sufficient. INGEST-02 / INGEST-03 cleared to proceed without an os.walk refactor. |

## Conventions

- Open questions require a human decision Scarlet cannot make alone.
- Update an entry's row when status changes; move to Resolved only when the decision is final and acted on.
- Add a row when a new blocker surfaces during execution.
