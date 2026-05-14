# CLAUDE.md

Standing context for the PolicyCodex project. Read this first when working in this folder.

*Renamed from PolicyWonk to PolicyCodex on 2026-05-11. Primary domain: `policycodex.org`. The working folder path stays `/Users/chuck/PolicyWonk/` and existing `PolicyWonk-*.md` file names stay as-is, to avoid breaking subagent prompts and configs.*

*Layout note (2026-05-11): the public repo root holds the public-facing artifacts only (PRD, tickets, code, README, LICENSE, this file). Sprint logs, decision rationale, and per-diocese checklists moved under `internal/` (tracked). Historical 2024 notes and pre-PRD brainstorm artifacts moved to `archive/` (gitignored, local-only).*

## What This Project Is

PolicyCodex is a tool that helps Catholic dioceses (and adjacent mission-driven nonprofits) manage the full lifecycle of their governing documents: inventory, review, approval, publication, and ongoing maintenance.

The active spec lives in `PolicyWonk-v0.1-Spec.md`. The sprint board lives in `PolicyWonk-v0.1-Tickets.md`. Read the spec before doing any substantive work in this folder.

## Current Status

Active. Brainstorm complete, v0.1 spec and engineering tickets locked, riskiest-assumption spike passed (70.9% acceptance excluding always-null fields, recorded in `internal/PolicyWonk-Spike-Plan.md`). Targeting a public demo at DISC (Diocesan Information Systems Conference) mid-June 2026. Pensacola-Tallahassee is install zero. The Archdiocese of Los Angeles is the reference design partner.

**Week-2 status (closed 2026-05-13, two days ahead of Friday's planned freeze):** all 10 Committed tickets merged: AI-04, AI-14, APP-01, AI-02, INGEST-01, APP-04 in the first wave; INGEST-03, APP-02, AI-11, AI-05, AI-08 in the second. Plus AI-15 (delegated from Chuck) resolved. 116 tests passing on main (was 73 going in). APP-04 cleared its 3-day bottleneck a day early; live smoke against PT succeeded. Code review (`superpowers:requesting-code-review`) ran on every subagent's output before merge per discipline. **The 2026-05-13 foundational-policy brainstorm** (Chuck: "the Document Retention Policy IS a policy AND is the source of app configuration variables") produced an approved architectural design captured in `internal/PolicyWonk-Foundational-Policy-Design.md`; six new tickets land in Week 3+ (INGEST-07, APP-20, APP-21, REPO-09, AI-12-revised, APP-15-revised).

**Week-3 plan ready** (`internal/PolicyWonk-Week-3-Sprint-Plan.md`). 10 Committed tickets, theme "PR-backed edit flow end-to-end + foundational-policy bundle reading." Pre-sprint actions: Scarlet scaffolds PT's `policies/document-retention/` bundle (one-time, ~30 min); Chuck advances OQ-05 / OQ-08 / REPO-08. **Two locked architectural commitments added the same session:** (1) v0.1 ships generic — all PT-specific scaffolding is development-time only, install-N onboards via clone + wizard with no code edits (REPO-10 audit, Week 5); (2) v0.1 supports a boxed-ship Docker profile alongside clone-and-build so non-developer dioceses pull a pre-built container, do the wizard, and never touch code (REPO-05 dual-Compose scope; AGPL compliance is a footer "View Source" link).

**Week-3 Wave-1 status (2026-05-14, 4 days ahead of plan):** all 4 Wave-1 Committed tickets merged: APP-05 (`e9a41cc`), INGEST-07 (`7035946`), PUBLISH-01 (`7427ffc`), AI-06 (`282b2d7`). Plus OQ-12 resolved (`ff3ac47`) and the PT bundle scaffold landed on `pt-policy@34a1671`. Code review ran on every branch before merge; INGEST-07 + AI-06 each had Important review fixes applied in-branch before merge. 156 tests passing on main (was 116 going in). Astro 5.18.1 builds 4 pages clean. **Subagent dispatch recipe (verified afternoon of 2026-05-14):** the blessed pattern for implementer subagents is the Agent tool's `isolation: "worktree"` parameter, which the harness manages at `/Users/chuck/PolicyWonk/.claude/worktrees/agent-<id>/`. This was already the design per `internal/superpowers/specs/2026-05-05-agent-led-execution-design.md` (lines 57, 113); Scarlet's morning attempt to manually `git worktree add /tmp/pc-wt-<ticket>` and brief implementer subagents to operate there tripped the harness's intent-based safety classifier (denied at Bash tool layer) and forced an in-session sequential execution of all 4 Wave-1 tickets. Wave-2 onwards: use `isolation: "worktree"` on every implementer dispatch, sequentially (parallel implementer dispatch is a `superpowers:subagent-driven-development` skill red flag). Reviewer subagents stay parallel-safe (verified Wave-1 afternoon with 4 concurrent reviewers using `.tmp-reviews/` staging). Full verified recipe in the `feedback_subagent_sandbox.md` auto-memory. Wave-2 (APP-06 catalog view + APP-21 startup self-check) unblocked.

**Week-3 Wave-2 status (2026-05-15, recipe verified end-to-end):** APP-21 merged at `9aabce8` (L3 startup self-check via Django check framework; `POLICYCODEX_ONBOARDING_COMPLETE` setting gates infra-failure severity; bundle-validity always Error; 15 new tests). APP-06 merged at `a681d0f` (function-based catalog view at `/catalog/` with `@login_required`, first base layout template `core/templates/base.html`, `/` redirect to catalog, empty-state for fresh installs, 9 new tests). 180 tests passing on main (was 156 going in). The verified `isolation: "worktree"` recipe worked end-to-end: 2 implementer subagents dispatched sequentially, both DONE first try, 4 reviewer subagents dispatched in parallel pairs (spec + quality per ticket). APP-21 reviewer found 2 Important issues (Path import load-bearing + manage.py check assertion) fixed in-branch before merge; APP-06 reviewer APPROVED with 2 minor nits as follow-ups. The two-stage review (spec compliance first, then code quality) caught complementary issues — keep both. Wave-3 (APP-07 edit form, APP-17 PR-state mapping, APP-18 approve action, APP-19 publish action) is dispatch-ready: APP-06 + APP-04 (Wave-1) are the prerequisites.

**Week-3 Wave-3 status (2026-05-16, end-to-end edit-flow demo-ready):** All 4 Wave-3 tickets merged: APP-07 (`1a8e626`), APP-17 (`02739b3`), APP-18 (`3674997`), APP-19 (`0125323`). 265 tests passing on main (was 180 going in; +85 net). The complete edit flow lives: CFO opens `/policies/<slug>/edit/` → form POST opens a PR with branch `policycodex/edit-<slug>-<uuid>` → catalog row shows Drafted gate → reviewer clicks Approve → PR approved via GitHub API → row flips to Reviewed → publisher clicks Publish → PR squash-merged → row Published. Each ticket dispatched sequentially via `isolation: "worktree"`, each got the two-stage spec + quality review in parallel, each got an in-branch review-fix commit before merge. Notable gotchas surfaced this session: (1) APP-17 implementer accidentally `cd /Users/chuck/PolicyWonk` for git operations and landed commits on parent's local main; rolled back via `git update-ref` with Chuck's authorization, and the implementer prompt for APP-18/APP-19 was strengthened with a "Critical Operational Note" forbidding parent-cd for git ops; (2) APP-18 implementer reported Edit/Write tools silently failing inside `.claude/worktrees/<id>/` and worked around via Python heredocs (the failure didn't recur for APP-19, suggesting it may be classifier-sensitive to brief framing rather than a hard sandbox limit); (3) APP-19's plan included a `policymeta.py` sidecar producer/consumer pattern, but APP-07 doesn't write the sidecar, so the Publish view was non-functional end-to-end; review caught it and the view was pivoted to `provider.list_open_prs() + branch_to_slug` (same lookup APP-17 already uses for the catalog gate badges), making Publish work today and deleting `policymeta.py` as dead code. Three reviewers across Wave-3 flagged `_resolve_repo` subprocess-duplication across 5 provider methods as a follow-up hygiene ticket. Wave-3 closes the v0.1 PR-backed edit-flow theme; remaining sprint scope is the Stretch tickets and Week-4 carries (APP-20 L1 UI gate, REPO-09 L2 CI guard, AI-12 retention bundle wire, etc.).

The project is open source under a maintainer model (the maintainer earns through setup, support, and customization, not through licensing).

## What's In This Folder

**Public root (tracked, public-facing):**

- `PolicyWonk-v0.1-Spec.md` is the active PRD
- `PolicyWonk-v0.1-Tickets.md` is the engineering sprint board
- `README.md` is the public-facing GitHub README
- `LICENSE` is the AGPL-3.0 text
- `ai/` holds the LLM provider abstraction (`provider.py`), Claude implementation (`claude_provider.py`), `emit.py` (markdown + YAML front-matter emitter), `taxonomies/` (per-diocese classification + retention seeds; `pt_classification.yaml` is install-zero's), and `ai/tests/`
- `app/` holds App-lane code: `app/git_provider/` (`GitProvider` ABC + `GitHubProvider` with clone, branch, commit, push, open-PR, read-PR-state) and `app/requirements.txt`
- `ingest/` holds the Ingest-lane code: `local_folder.py` (`LocalFolderConnector` with the `python -m ingest.local_folder <path>` CLI), `extractors/` (PDF via pypdf, DOCX via python-docx, MD/TXT via `read_text`; dispatched by extension via `from ingest.extractors import extract`), and `ingest/tests/`
- `core/` is the project-wide Django app: `/health/` smoke view, `/login/` and `/logout/` (Django's built-in LoginView/LogoutView with a spartan template), `git_identity.py` (the `get_git_author(user)` mapper that feeds `GitHubProvider.commit`), and `core/tests/`
- `manage.py` plus `policycodex_site/` is the Django 5+ project skeleton (SQLite default; deployment-hardening of `SECRET_KEY` deferred per REPO-05/PUBLISH-07)
- `pytest.ini` wires pytest-django for the whole repo
- `spike/` contains the runnable extraction script (`extract.py`, now loading PT taxonomy from `ai/taxonomies/pt_classification.yaml` and injecting it into the prompt per AI-11), per-policy JSON outputs (gitignored), and the `spike/eval/` regression harness (per-field eval sets for category/owner_role/dates/retention, scoring CLI with `--outputs DIR` / `POLICYCODEX_EVAL_OUTPUTS` flag, README)

**`internal/` (tracked, sprint workspace):**

- `internal/PolicyWonk-Daily-Log.md` is Scarlet's append-only event log
- `internal/PolicyWonk-Open-Questions.md` is the live OQ tracker
- `internal/PolicyWonk-Week-N-Sprint-Plan.md` is the per-week sprint plan
- `internal/PolicyWonk-Week-N-Demo.md` is the per-week demo wrap
- `internal/PolicyWonk-Spike-Plan.md` is the riskiest-assumption spike, including results
- `internal/PolicyWonk-Framework-Evaluation.md`, `internal/PolicyWonk-SSG-Evaluation.md`, `internal/PolicyWonk-Prompt-Architecture-Decision.md` capture decision rationale
- `internal/REPO-03-GitHub-App-Checklist.md`, `internal/REPO-04-PT-Repo-Settings.md` are per-diocese onboarding checklists
- `internal/superpowers/specs/`, `internal/superpowers/plans/` hold agent-led design and execution plans

**`archive/` (gitignored, local-only):**

- 2024 feature brief, original Notes-1..9, pre-PRD Project Summary, README draft. Historical context only; not part of the public repo.

`.obsidian/` is the Obsidian vault config (gitignored). This vault opens in Obsidian. Keep new files in markdown.

## How To Approach Work Here

1. Treat the v0.1 spec and tickets as the active plan. The 2024 notes in `archive/` are historical context only.
2. The Git-backed architecture is settled. Do not propose alternative storage models without new information.
3. New sprint logs, decision rationale, and per-diocese checklists go in `internal/`. New public-facing artifacts (docs about the product itself) go at the root or under `ai/`/`app/`.
4. Naming: free-form descriptive names are fine.

## What Has Already Been Reconsidered and Locked

Do not reopen these without new information:

**Business model**
- Maintainer mode: open source plus services revenue (setup, support, customization)
- Single-tenant self-hosted VM per diocese, not multi-tenant SaaS
- License: AGPL-3.0 (resolved 2026-05-11). Canonical text committed as `LICENSE`.

**Wedge and audience**
- v0.1 wedge is inventory cleanup plus handbook publication
- Buyer and admin user is the diocesan IT director
- Distribution channel is DISC (the diocesan IT director community)
- Diocese zero is Pensacola-Tallahassee, design partner is Archdiocese of Los Angeles

**Architecture**
- Git-backed: every policy is a markdown file in a private GitHub repo per diocese
- Every gate transition is a pull request state (Drafted = open, Reviewed = approved, Published = merged)
- Handbook publishes via GitHub Actions on every merge to main
- Non-technical editors (CFO, HR director) never see Git; the admin web app handles commits and PRs on their behalf
- GitHub.com is the v0.1 default, Git provider abstracted for GitHub Enterprise, GitLab, Gitea later

**Conventions**
- Versioning address: LA Archdiocese chapter-section-item by default, Catholic healthcare department-code as an alternative, configurable per diocese
- Document version: semver (1.0 first published, 1.1 minor, 2.0 obligations changed)
- Required metadata on every published policy: owner, effective date, last review, next review, retention period (modeled on ISO 30301)
- Three gates in v0.1: Drafted, Reviewed, Published. Full Seven-Gate configurability is v0.2

**Tech**
- Claude is the default LLM. Provider abstracted for OpenAI, Gemini, Azure OpenAI, and local Llama
- Multi-LLM consensus is overbuilt for the problem. One model plus a sharp rubric plus a human approver wins
- Custom Python MCP servers are not needed. Skills (markdown plus reference docs) cover the AI-assist work
- Seven-screen onboarding wizard: GitHub repo, address scheme, versioning, reviewer roles, retention, LLM provider, source-of-truth reference documents

**AI extraction grounding (validated by spike)**
- The AI inventory pass receives two pieces of injected context per extraction: (1) the chosen address taxonomy, (2) any source-of-truth reference documents the diocese has designated
- The Document Retention Policy is the canonical source-of-truth example. It supplies retention periods, document-type taxonomy, and gap-detection signal in one document
- Without that context, retention extraction quality drops to 0.144 on the rubric. With it, the extraction passes 60% acceptance comfortably

**Foundational-policy bundle pattern (approved 2026-05-13)**
- Policies that are simultaneously inventory documents AND sources of app configuration variables (the Document Retention Policy is the canonical example) live as a directory bundle: `policies/<slug>/policy.md` (narrative + frontmatter declaring `foundational: true` and `provides: [...]`) plus `policies/<slug>/data.yaml` (canonical machine-readable variables). Both reviewed in the same PR; the app reads `data.yaml` directly with no markdown parsing.
- Live sync via PR merge: a CFO edit to the retention policy opens a PR, reviewer approves, publisher merges; the handbook rebuilds AND the app's local working copy pulls AND the next AI extraction sees the new taxonomy.
- Four protection layers against accidental deletion: L0 Git branch protection (existing), L1 app UI hides Delete (APP-20), L2 pre-merge CI guard (REPO-09), L3 app startup self-check (APP-21).
- Removing a classification is **soft-delete only** (`deprecated: true` keeps the id valid for existing references). Hard remove requires re-classifying dependents first. No auto-re-extraction of orphaned policies in v0.1.
- Non-data-bearing policies stay as flat `policies/<slug>.md` files. The bundle pattern is opt-in via the `foundational: true` frontmatter flag.
- Other source-of-truth reference docs that are NOT policies in the inventory (e.g., a category cheatsheet) may still live in a `references/` directory; the bundle pattern is for documents that play both roles.
- Full design: `internal/PolicyWonk-Foundational-Policy-Design.md`.

**Ship generic, never PT-flavored**
- v0.1 ships as a generic, diocese-agnostic codebase. PT-specific scaffolding present in the repo today (taxonomy YAML, retention PDF reference, "Diocese of Pensacola-Tallahassee" in code/comments) is development-time convenience only — install-zero has to develop against something concrete.
- Install-N flow is: clone the public repo, run install, complete the seven-screen onboarding wizard. The wizard supplies all per-diocese values, including the uploaded retention PDF that AI-parses into the diocese's own foundational-policy bundle (per APP-15-revised). No code edits required for a new diocese.
- Per-diocese values that must be wizard-driven (never hardcoded): diocese name, GitHub org/repo, classification taxonomy and retention schedule, address scheme, versioning convention, reviewer roles, retention defaults, LLM provider, other source-of-truth reference documents.
- When designing new code, treat any value that varies per diocese as wizard-sourced. `ai/taxonomies/pt_classification.yaml` is a seed example, not framework data — by v0.1 ship it should either move into PT's policy repo as `policies/document-retention/data.yaml` (its proper home per the bundle pattern) or stay as a clearly-labeled test fixture.
- Code comments, error messages, log lines, class names: "the diocese" not "PT." Internal docs in `internal/` are exempt — they naturally center PT because that's the install-zero context and they aren't part of the shipping artifact.
- Tracked as REPO-10 for the Week 5 polish-week audit pass. "Install verification on a clean VM" (Week 5 calendar item) is the generic-ship test: a clean VM clones, wizards through, and operates without seeing PT anywhere.

**Design principle**
- Opinionated by default. Configurable where dioceses have legitimate variation. AI-assisted throughout.

## Style Preferences

- Spartan, clear, active voice
- No em dashes
- Bullet lists are fine in artifacts and reference docs
- "You" and "your" when addressing the reader
- No filler words
