# CLAUDE.md

Standing context for the PolicyCodex project. Read this first when working in this folder.

*Renamed to PolicyCodex 2026-05-11 (primary domain `policycodex.org`); folder path stays `/Users/chuck/PolicyWonk/` and `PolicyWonk-*.md` filenames stay as-is. Public root carries public artifacts; `internal/` (local sprint workspace, gitignored 2026-06-08, kept locally — history still in git) holds sprint/design docs; `archive/` (gitignored) holds 2024 history.*

## What This Project Is

PolicyCodex is a tool that helps Catholic dioceses (and adjacent mission-driven nonprofits) manage the full lifecycle of their governing documents: inventory, review, approval, publication, and ongoing maintenance. Open source under a maintainer model (the maintainer earns through setup, support, and customization, not through licensing).

The active spec lives in `PolicyWonk-v0.1-Spec.md`. The sprint board lives in `PolicyWonk-v0.1-Tickets.md`. Read the spec before doing any substantive work in this folder.

## Current Status

**Settings-page rebuild SHIPPED (2026-06-11) + polished (2026-06-12); REPO-10 audit run and all 14 findings resolved (2026-06-14).** The 2026-06-11 pivot decision (tear down the seven-screen onboarding wizard, replace it with a Settings page) was executed the same evening: all six phases / 30 tasks of the rebuild plan landed on `main` as feature+cleanup commit pairs, followed by a 13-commit UX polish sprint (`ux-fix-1`..`ux-fix-13`) the next morning (`978a50a`). On 2026-06-14 the full REPO-10 generic-ship + 7-track audit ran (ship-generic gate **PASS**, zero PT leakage; 14 findings F1–F14) and **every finding was fixed** across three subagent-driven batches. **Current code tip `3fea68a`**; suite green at **691 passed, 11 skipped, 0 failed** (run it with `ai/venv/bin/python -m pytest`). All three audit-fix batches are pushed to public `origin/main` (synced through the `3bd6bf1` doc commit, 2026-06-14).

**Post-audit fix (2026-06-15, on public `main`):** the first real install (`~/pcx-test`) hit "GitHub App — install check failed". Root cause: `app/credentials/store.py` cached the decrypted store in a module global with no cross-process invalidation, so under gunicorn `--workers 3` a key written on one worker (`github_app.app_id` from the manifest-create callback) was invisible to the worker serving the install callback → `KeyError`. Fixed (`52234d7`) by reloading when the store file's mtime changes; two TDD regression tests added and `test_manifest_state_placement` made hermetic (it had ridden a leaked credential cache). Note: the GHCR `v0.1.0` image predates this fix — restart reloads all workers as a stopgap; `git pull`+rebuild or a new image carries it. Detail in `internal/PolicyWonk-Daily-Log.md` (2026-06-15) and memory `project_credential_store_cross_worker_cache.md`.

**Audit fixes (2026-06-14, all on `main`; full detail in `internal/PolicyWonk-REPO10-Audit-2026-06-14.md`):**

- **Blockers** `41608f3..c63c7e9` (pushed): F1 (inventory golden-path TypeError), F3/F6 (Tailwind `@source` missed Settings/Inventory), F2 (orchestrator clean-tree recovery).
- **Tier 1 + Tier 2** `b794fb2..080ae57` (pushed, 10 commits): F14+F9 (inventory runner is the sole PR owner; inert diff layer dropped), F7 (`SECRET_KEY` single source in `env.get_secret_key`), **F5 — fat-views extraction into a new `core/services.py` via dependency injection** (Strategy A'; the three views are thin, 64 existing view tests pass unchanged), F12 + `is_empty_onboarding` (wizard-era renames), F11 (DISC smoke README), F13 (manifest fresh CSRF marker).
- **Docker** `f9c39fd..cf4bf00` (pushed): F4 (`POLICYCODEX_PORT` threads end-to-end through compose + gunicorn), F10 (`/secrets` mount comment corrected to the inert-fallback reality), F8 (canonical public-org slug finalized as `robinsoncptdit` — a dedicated org is a deliberate v0.2 move).
- **F4 live-validated on Colima (2026-06-14):** a clean `git archive HEAD` export of tip `9c1e5e2` booted Profile A from source with `POLICYCODEX_PORT=9000`. `docker compose config` resolved 9000 on both host and container sides; gunicorn bound `0.0.0.0:9000`; `curl :9000/health/` → HTTP 200; `curl :8000/health/` → connection refused (no hardcoded 8000); clean teardown, real repo untouched. Done entirely in an isolated `/tmp` clone — Chuck's working tree and `.env` never touched.
- **Profile-B image published + validated (2026-06-14):** tag `v0.1.0` (on `df90006`) fired `release-ghcr.yml`, which built multi-arch (amd64+arm64) and pushed `ghcr.io/robinsoncptdit/policycodex:latest` + `:v0.1.0`. Verified end-to-end: a genuinely **anonymous** `docker compose -f docker-compose.pull.yml pull` (local docker has no ghcr.io creds) succeeded — so the package is publicly pullable, no visibility flip was needed — then booted on Colima and `curl :9000/health/` returned 200. The `docker-compose.pull.yml` header comment was corrected from "NOT published yet" to the published reality. (F4's live-Colima validation, previously also owed, is also done — see above.) **All REPO-10 audit items (F1–F14) and both deferred deploy validations are now closed.**

**Why the pivot happened:** the live DISC-readiness walkthrough surfaced architectural fault lines between the new credential store and the legacy settings-driven plumbing. Each fix-the-symptom commit revealed the next consumer that had not been refactored. Chuck paused 5 panels in and called for a rethink.

**The architecture now in code:**

- Seeded admin (`admin`/`admin1234`) forced to change password on first login. Migrations `core/migrations/0001_create_user_profile` / `0002_seed_default_admin` / `0003_create_role_groups`; enforced by `core/middleware.py` `ForcePasswordChangeMiddleware` + `core/views.py` `ForcedPasswordChangeView`.
- All configuration lives in a top-level `/settings/` page — its **own Django app `app/settings/`** (label `settings_panel`), routed from `policycodex_site/urls.py`, NOT in `core/`. Six panels in `app/settings/panels/`: GitHub App, AI provider, Policy repository, Diocese configuration (slug `configuration`), Users-and-roles, plus Reset.
- Inventory is a top-level `/inventory/` page — its **own Django app `app/inventory/`** — with a 5-state lifecycle, always-present drop bucket, per-item and whole-run retry endpoints, and HTMX status polling.
- GitHub App provisioning automates via the GitHub App manifest flow (https://docs.github.com/en/apps/sharing-github-apps/registering-a-github-app-from-a-manifest) in `app/settings/panels/github_app_manifest.py`: manifest start/callback persists App ID + PEM + webhook secret, install callback auto-detects the Installation ID. Manual-paste fields remain as the air-gapped fallback.

**Spec:** `internal/superpowers/specs/2026-06-11-settings-page-design.md` (12 sections, ~430 lines).
**Plan:** `internal/superpowers/plans/2026-06-11-settings-page-rebuild.md` (6,679 lines, 30 tasks, six phases — all executed).
**UX-fix plan:** `internal/superpowers/plans/2026-06-12-ux-test-drive-fixes.md`.
**Revert anchors on `main`:** `7286bb4` (pre-pivot clean revert, still reachable; the rebuild + polish sit on top), `f273185` (pre-UX-fix).

**DISC carve-out as executed:**

- DISC-01 (first-boot keys + entrypoint), DISC-02 (Fernet credential store + hydration), DISC-15 (install.sh + GHCR workflow + cleanup) — kept verbatim.
- DISC-11..14 (inventory models + runner + bulk-PR finalize) — light refactor; `finalize_after_inventory` signature simplified to `(run, *, working_dir)`.
- DISC-05..10 (signature pinning, `test_credentials` / `test_key` classmethods, drop-bucket markup, working-copy clone logic) — code reused, migrated into Settings panels.
- DISC-03 (wizard gating), DISC-04..10 (the seven wizard screens), the wizard-state session model, and `app/onboarding/` itself — torn down entirely (commit `dace636`, "phase-1-1: tear down app/onboarding entirely"). DISC-16 rewritten as the new Playwright Settings smoke. Wizard-tickets APP-08..APP-16 and the DISC followup commits (`cb8748a` / `4ff105d` / `384f94d` / `900f4c0` / `75bb6d2` / `f2c43ee` / `cfce5cf`) are superseded.

**Architectural decisions that survive:** REPO-05 containerization, REPO-09 L2 CI guard, REPO-14 deprecated-tombstone end-to-end, APP-23 detail view, APP-25 typed-table editor, AI-10 / AI-16 / AI-17 inventory orchestrator, INGEST-05 / INGEST-06 incremental ingest, the AGPL "View Source" footer, the Frontend Portability constraints, the **`core/services.py` thin-views service layer** (F5 — `build_catalog` / `propose_policy_edit` / `build_foundational_bundle` / `propose_foundational_edit`, collaborators dependency-injected from `core.views`), the foundational-bundle pattern, the PR-as-gate workflow, the handbook generator.

**Sprint board:** `PolicyWonk-v0.1-Tickets.md` (gitignored/local-only) was reconciled 2026-06-14 — the pivot banner updated to the shipped state, a Current State (post-pivot) section added, and the audit fixes recorded (F1–F14 fixed, only the Profile-B image publish left open). The board was also pruned 2026-06-14 (300KB → 52KB): de-padded (208KB of cosmetic markdown-table whitespace removed, lossless), superseded wizard rows + verbose resolution notes moved to `internal/archive/`.

For sprint-by-sprint detail and the full pre-pivot history, see `internal/PolicyWonk-Daily-Log.md`. Older tracking-doc history (May Daily-Log entries, wizard tickets, full resolution notes) was pruned into `internal/archive/` on 2026-06-14 to keep the live trackers greppable.

## What's In This Folder

**Public root (tracked, public-facing):**

- `PolicyWonk-v0.1-Spec.md` is the active PRD.
- `README.md` is the public-facing GitHub README.
- `LICENSE` is the AGPL-3.0 text.
- `HOWTO-GitHub-Team-Setup.md` is a generic, diocese-agnostic guide for upgrading a GitHub org to Team tier, enabling branch protection, optionally requiring the foundational-policy guard, and publishing the handbook at a custom subdomain. Pre-pivot, Part 1 walked the IT director through manual GitHub App creation; post-pivot, App creation is automated by the GitHub App manifest flow inside the Settings GitHub App panel and Part 1 stands as a fallback for installs where the manifest flow does not apply.
- `repo-template/` holds generic, vendorable files copied into a diocese's policy repo during onboarding: the L2 foundational-policy CI guard (REPO-09), the handbook build-and-deploy workflow + vendored Astro `handbook/` + `sync-handbook.sh` re-vendor script (PUBLISH-06 + PUBLISH-07), and a README. Its `tests/` run in the main suite but are not copied on install. Canonical home for installable diocese-repo automation.
- `ai/` is the LLM provider abstraction + Claude implementation, markdown/YAML emit, confidence-audit sidecar, Django-free foundational-bundle loader, gap detection, generic per-policy extraction + the Django-free inventory-pass orchestrator (`inventory_extract.py` + `inventory.py`, AI-10), per-diocese taxonomy seeds, and tests.
- `app/` is App-lane Django code: git provider (clone/branch/commit/push/PR), local working-copy manager + L3 startup self-check, the first-boot key + credential-store machinery (DISC-01/DISC-02), the **`app/settings/`** config app (six panels — GitHub App, AI provider, Policy repository, Diocese configuration, Users-and-roles, Reset — routed at `/settings/`), the **`app/inventory/`** app (top-level `/inventory/` page, 5-state lifecycle + drop bucket + retry endpoints), and tests. `app/onboarding/` was torn down in the rebuild (commit `dace636`) and no longer exists.
- `ingest/` is Ingest-lane code: `LocalFolderConnector` CLI, extractors (PDF/DOCX/MD/TXT), `BundleAwarePolicyReader` (reads flat policies + foundational bundles as one inventory), source manifest model, and tests.
- `core/` is the project-wide Django app: `/health/`, `/login/`, `/logout/`, the seeded-admin + forced-password-change flow (`ForcePasswordChangeMiddleware` + `ForcedPasswordChangeView` + the role-group migrations), policy catalog + read-only detail view + role-gated edit/approve/publish, git-author mapper, the `run_inventory_pass` management command, and tests. Settings and Inventory are NOT here — they are their own apps under `app/` (`app/settings/`, `app/inventory/`).
- `manage.py` plus `policycodex_site/` is the Django 5+ project skeleton (SQLite default; `SECRET_KEY` hardening deferred per REPO-05).
- `pytest.ini` wires pytest-django for the whole repo.
- `spike/` is the riskiest-assumption extraction spike: `extract.py` loading PT taxonomy, per-policy JSON outputs (gitignored), and the `spike/eval/` regression harness.
- `.github/workflows/` holds two dev-time GitHub Actions (installed via `/install-github-app`, 2026-06-05): `claude.yml` (the `@claude` assistant, on issue/PR mentions) and `claude-code-review.yml` (auto code-review on every PR via `claude-code-action` + the marketplace `code-review` plugin). These are development tooling, not shipped product, and no-op without the `CLAUDE_CODE_OAUTH_TOKEN` secret; REPO-10 (generic-ship audit) decides whether they stay in the diocese-facing clone. Editing the review workflow has two non-obvious constraints: any change must live on `main` AND be byte-identical on the PR branch, or `claude-code-action`'s app-token exchange 401s ("Workflow validation failed"); and the review only posts when the prompt passes the PR as a full `https://github.com/...` URL plus a `--comment` flag. Full debug history in the Daily Log (2026-06-05 16:30 PT).

**`internal/` (local sprint workspace, gitignored 2026-06-08 — kept locally, never distributed; history retained in git):**

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
- Settings-page configuration (post-pivot 2026-06-11). Five panels: GitHub App, AI provider, Policy repository, Diocese configuration, Users-and-roles, plus a Reset panel. Per-diocese knobs that were wizard screens are now panel sections. Inventory lives at top-level `/inventory/`.
- UI framework: Tailwind CSS + DaisyUI + HTMX over Django templates, Inter typeface, brand color via DaisyUI CSS variables (resolved 2026-06-05 in OQ-13). Production build via the Tailwind standalone CLI (single static binary, no Node). All four runtime dependencies (Tailwind, DaisyUI, HTMX, Inter) are MIT or equivalent so AGPL stays compatible. Commercial component libraries (Tailwind UI, MUI Pro, Ant Design Pro, DevExpress, Telerik, Kendo UI) are off the table as long as PolicyCodex is AGPL.

**Frontend portability constraints (preserve the option to swap the frontend stack later)**
- Page views and HTMX fragment views stay thin. Business logic lives in Django models, managers, and service functions, so a future SPA replaces only the views.
- HTMX endpoints are URL-segregated under `/htmx/`. A future JSON API at `/api/v1/` does not collide. The fragment endpoints retire cleanly when a SPA arrives.
- Authentication and authorization sit in middleware and view decorators, not in template logic, so a future JSON API gets the same protection without rework.

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
- Install-N flow is: clone the public repo, run install, log in with seeded admin credentials, change the password on first login, walk through the Settings page panels to configure per-diocese values. The Settings page supplies all per-diocese values, including the uploaded retention PDF that AI-parses into the diocese's own foundational-policy bundle. No code edits required for a new diocese.
- Per-diocese values that must be Settings-driven (never hardcoded): diocese name, GitHub org/repo, classification taxonomy and retention schedule, address scheme, versioning convention, reviewer roles, retention defaults, LLM provider, other source-of-truth reference documents.
- When designing new code, treat any value that varies per diocese as Settings-sourced. The classification/retention seed (`ai/taxonomies/seed_classification.example.yaml` by REPO-10) is a clearly-labeled development fixture, not framework data. The live taxonomy lives in a diocese's policy repo as `policies/document-retention/data.yaml` (its proper home per the bundle pattern), read by capability. The seed is used only by the extraction spike as a fallback when no bundle is present.
- Code comments, error messages, log lines, class names: "the diocese" not "PT." Internal docs in `internal/` are exempt; they naturally center PT because that's the install-zero context and they aren't part of the shipping artifact.
- Tracked as REPO-10 for the polish-week audit pass. The "install verification on a clean VM" exercise is the generic-ship test: a clean VM clones, walks the first-login flow plus the Settings panels, and operates without seeing PT anywhere.

**Design principle**
- Opinionated by default. Configurable where dioceses have legitimate variation. AI-assisted throughout.

## Style Preferences

- Spartan, clear, active voice
- No em dashes
- Bullet lists are fine in artifacts and reference docs
- "You" and "your" when addressing the reader
- No filler words
