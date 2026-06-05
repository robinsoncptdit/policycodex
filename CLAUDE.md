# CLAUDE.md

Standing context for the PolicyCodex project. Read this first when working in this folder.

*Renamed to PolicyCodex 2026-05-11 (primary domain `policycodex.org`); folder path stays `/Users/chuck/PolicyWonk/` and `PolicyWonk-*.md` filenames stay as-is. Public root carries public artifacts; `internal/` (tracked) holds sprint workspace; `archive/` (gitignored) holds 2024 history.*

## What This Project Is

PolicyCodex is a tool that helps Catholic dioceses (and adjacent mission-driven nonprofits) manage the full lifecycle of their governing documents: inventory, review, approval, publication, and ongoing maintenance. Open source under a maintainer model (the maintainer earns through setup, support, and customization, not through licensing).

The active spec lives in `PolicyWonk-v0.1-Spec.md`. The sprint board lives in `PolicyWonk-v0.1-Tickets.md`. Read the spec before doing any substantive work in this folder.

## Current Status

Active. Targeting a public demo at DISC (Diocesan Information Systems Conference) mid-June 2026. Pensacola-Tallahassee is install zero; the Archdiocese of Los Angeles is the reference design partner.

Week 4 closed 2026-05-24 ahead of plan (suite 339 -> 373). **PUBLISH-07 LIVE 2026-05-26: `https://handbook.ptdiocese.org/` deploys through the three-job workflow on every merge to `pt-policy/main`; Let's Encrypt cert through 2026-08-24.** Suite at 379. **APP-15 (onboarding screen-7 bootstrap), APP-25 (foundational typed-table editor, demo slice), APP-16 (onboarding configuration commit), and APP-23 (read-only policy detail view + L1 gate) landed 2026-06-05 via subagent-driven development; suite at 435.**

**Week-5 polish-week scope:** remaining wizard screens (APP-10..16) + provisioning (APP-15/16), read-only policy detail view (APP-23), generic-ship audit + clean-VM install verification (REPO-10), Python version pin (REPO-11), `workflow_dispatch:` on shipped workflows (REPO-12), incremental re-run + full PT-corpus run (INGEST-05/06), inventory-pass orchestrator (AI-10). Hard feature freeze at end of Week 5. **Progress (2026-06-05): APP-15 done as the read-only bootstrap loop (the editable typed-table UI split out to APP-25, also shipped); APP-16 done — screen-7 accept now commits `.policycodex/config.yaml` + the bundle to the diocese repo in one PR (secrets scrubbed, scoped `git add`); APP-23 done — `/policies/<slug>/` read-only detail view (title, metadata, `provides:`, escaped body, gate badge) with the catalog's L1 foundational gate, catalog rows now link to it, browser-verified; APP-26 filed for post-DISC editor hardening + demo polish. Remaining: REPO-10/11/12, INGEST-05/06, AI-10.**

For sprint-by-sprint detail and per-wave narrative, see `internal/PolicyWonk-Daily-Log.md` (append-only event log) and the `internal/PolicyWonk-Week-N-Demo.md` files.

## What's In This Folder

**Public root (tracked, public-facing):**

- `PolicyWonk-v0.1-Spec.md` is the active PRD.
- `PolicyWonk-v0.1-Tickets.md` is the engineering sprint board.
- `README.md` is the public-facing GitHub README.
- `LICENSE` is the AGPL-3.0 text.
- `HOWTO-GitHub-Team-Setup.md` is a generic, diocese-agnostic guide for upgrading a GitHub org to Team tier, enabling branch protection, optionally requiring the foundational-policy guard, and publishing the handbook at a custom subdomain.
- `repo-template/` holds generic, vendorable files copied into a diocese's policy repo during onboarding: the L2 foundational-policy CI guard (REPO-09), the handbook build-and-deploy workflow + vendored Astro `handbook/` + `sync-handbook.sh` re-vendor script (PUBLISH-06 + PUBLISH-07), and a README. Its `tests/` run in the main suite but are not copied on install. Canonical home for installable diocese-repo automation.
- `ai/` is the LLM provider abstraction + Claude implementation, markdown/YAML emit, confidence-audit sidecar, Django-free foundational-bundle loader, gap detection, per-diocese taxonomy seeds, and tests.
- `app/` is App-lane Django code: git provider (clone/branch/commit/push/PR), local working-copy manager + L3 startup self-check, onboarding wizard (skeleton + screen 1 + per-screen form registry), and tests.
- `ingest/` is Ingest-lane code: `LocalFolderConnector` CLI, extractors (PDF/DOCX/MD/TXT), `BundleAwarePolicyReader` (reads flat policies + foundational bundles as one inventory), source manifest model, and tests.
- `core/` is the project-wide Django app: `/health/`, `/login/`, `/logout/`, git-author mapper, and tests.
- `manage.py` plus `policycodex_site/` is the Django 5+ project skeleton (SQLite default; `SECRET_KEY` hardening deferred per REPO-05).
- `pytest.ini` wires pytest-django for the whole repo.
- `spike/` is the riskiest-assumption extraction spike: `extract.py` loading PT taxonomy, per-policy JSON outputs (gitignored), and the `spike/eval/` regression harness.

**`internal/` (tracked, sprint workspace):**

- `internal/PolicyWonk-Daily-Log.md` is Scarlet's append-only event log.
- `internal/PolicyWonk-Open-Questions.md` is the live OQ tracker.
- `internal/PolicyWonk-Week-N-Sprint-Plan.md` and `internal/PolicyWonk-Week-N-Demo.md` are per-week plans and demo wraps.
- `internal/PolicyWonk-Spike-Plan.md` is the spike with results.
- `internal/PolicyWonk-Framework-Evaluation.md`, `internal/PolicyWonk-SSG-Evaluation.md`, and `internal/PolicyWonk-Prompt-Architecture-Decision.md` capture decision rationale.
- `internal/REPO-03-GitHub-App-Checklist.md` and `internal/REPO-04-PT-Repo-Settings.md` are per-diocese onboarding checklists.
- `internal/superpowers/specs/` and `internal/superpowers/plans/` hold agent-led design and execution plans.

**`archive/` (gitignored, local-only):** 2024 feature brief, original Notes-1..9, pre-PRD Project Summary, README draft. Historical context only; not part of the public repo.

`.obsidian/` is the Obsidian vault config (gitignored). This vault opens in Obsidian. Keep new files in markdown.

## How To Approach Work Here

1. Treat the v0.1 spec and tickets as the active plan. The 2024 notes in `archive/` are historical context only.
2. The Git-backed architecture is settled. Do not propose alternative storage models without new information.
3. New sprint logs, decision rationale, and per-diocese checklists go in `internal/`. New public-facing artifacts (docs about the product itself) go at the root or under `ai/` / `app/`.
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
- v0.1 ships as a generic, diocese-agnostic codebase. PT-specific scaffolding present in the repo today (taxonomy YAML, retention PDF reference, "Diocese of Pensacola-Tallahassee" in code/comments) is development-time convenience only (install-zero has to develop against something concrete).
- Install-N flow is: clone the public repo, run install, complete the seven-screen onboarding wizard. The wizard supplies all per-diocese values, including the uploaded retention PDF that AI-parses into the diocese's own foundational-policy bundle (per APP-15-revised). No code edits required for a new diocese.
- Per-diocese values that must be wizard-driven (never hardcoded): diocese name, GitHub org/repo, classification taxonomy and retention schedule, address scheme, versioning convention, reviewer roles, retention defaults, LLM provider, other source-of-truth reference documents.
- When designing new code, treat any value that varies per diocese as wizard-sourced. The classification/retention seed (renamed to `ai/taxonomies/seed_classification.example.yaml` by REPO-10, 2026-06-05) is a clearly-labeled development fixture, not framework data; the live taxonomy lives in a diocese's policy repo as `policies/document-retention/data.yaml` (its proper home per the bundle pattern), read by capability via AI-12-revised. The seed is used only by the extraction spike as a fallback when no bundle is present.
- Code comments, error messages, log lines, class names: "the diocese" not "PT." Internal docs in `internal/` are exempt; they naturally center PT because that's the install-zero context and they aren't part of the shipping artifact.
- Tracked as REPO-10 for the Week 5 polish-week audit pass. "Install verification on a clean VM" (Week 5 calendar item) is the generic-ship test: a clean VM clones, wizards through, and operates without seeing PT anywhere.

**Design principle**
- Opinionated by default. Configurable where dioceses have legitimate variation. AI-assisted throughout.

## Style Preferences

- Spartan, clear, active voice
- No em dashes
- Bullet lists are fine in artifacts and reference docs
- "You" and "your" when addressing the reader
- No filler words
