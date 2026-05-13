# CLAUDE.md

Standing context for the PolicyCodex project. Read this first when working in this folder.

*Renamed from PolicyWonk to PolicyCodex on 2026-05-11. Primary domain: `policycodex.org`. The working folder path stays `/Users/chuck/PolicyWonk/` and existing `PolicyWonk-*.md` file names stay as-is, to avoid breaking subagent prompts and configs.*

*Layout note (2026-05-11): the public repo root holds the public-facing artifacts only (PRD, tickets, code, README, LICENSE, this file). Sprint logs, decision rationale, and per-diocese checklists moved under `internal/` (tracked). Historical 2024 notes and pre-PRD brainstorm artifacts moved to `archive/` (gitignored, local-only).*

## What This Project Is

PolicyCodex is a tool that helps Catholic dioceses (and adjacent mission-driven nonprofits) manage the full lifecycle of their governing documents: inventory, review, approval, publication, and ongoing maintenance.

The active spec lives in `PolicyWonk-v0.1-Spec.md`. The sprint board lives in `PolicyWonk-v0.1-Tickets.md`. Read the spec before doing any substantive work in this folder.

## Current Status

Active. Brainstorm complete, v0.1 spec and engineering tickets locked, riskiest-assumption spike passed (70.9% acceptance excluding always-null fields, recorded in `internal/PolicyWonk-Spike-Plan.md`). Week 2 of a six-week sprint is in progress, targeting a public demo at DISC (Diocesan Information Systems Conference) mid-June 2026. Pensacola-Tallahassee is install zero. The Archdiocese of Los Angeles is the reference design partner.

**Week-2 progress as of 2026-05-13 EOD:** 6 of 10 Committed tickets merged (AI-04, AI-14, APP-01, AI-02, INGEST-01, APP-04). 73 tests passing on main. APP-04 (the central 3-day bottleneck) cleared a day ahead of the Thu-noon checkpoint; live smoke against the PT repo succeeded end-to-end. Remaining for Friday's sprint freeze: AI-05, AI-11, INGEST-03, APP-02, AI-08.

The project is open source under a maintainer model (the maintainer earns through setup, support, and customization, not through licensing).

## What's In This Folder

**Public root (tracked, public-facing):**

- `PolicyWonk-v0.1-Spec.md` is the active PRD
- `PolicyWonk-v0.1-Tickets.md` is the engineering sprint board
- `README.md` is the public-facing GitHub README
- `LICENSE` is the AGPL-3.0 text
- `ai/` holds the LLM provider abstraction (`provider.py`) and the Claude implementation (`claude_provider.py`)
- `app/` holds App-lane code; currently `app/git_provider/` (`GitProvider` ABC + `GitHubProvider`) and `app/requirements.txt`
- `ingest/` holds the Ingest-lane code; currently `LocalFolderConnector` (`local_folder.py`) with a `python -m ingest.local_folder <path>` CLI
- `core/` is the stub Django app with the `/health/` smoke view
- `manage.py` plus `policycodex_site/` is the Django 5+ project skeleton (SQLite default; APP-02 will plumb env-driven config)
- `pytest.ini` wires pytest-django for the whole repo
- `spike/` contains the runnable extraction script (`extract.py`), input PDFs, per-policy JSON outputs, and the `spike/eval/` regression harness (per-field eval sets, scoring CLI, README)

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
- Reference documents live in a `references/` directory inside the diocese's policy repo

**Design principle**
- Opinionated by default. Configurable where dioceses have legitimate variation. AI-assisted throughout.

## Style Preferences

- Spartan, clear, active voice
- No em dashes
- Bullet lists are fine in artifacts and reference docs
- "You" and "your" when addressing the reader
- No filler words
