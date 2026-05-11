# PolicyCodex v0.1 Engineering Tickets

*P0 work broken into sprint-board tickets, mapped to the four lanes. Architecture is Git-backed: every policy is a markdown file in a private GitHub repo per diocese, every edit is a commit, every gate is a PR state, every publish runs in GitHub Actions.*

## Sizing Convention

- **S** = 1 to 2 days of focused work
- **M** = 3 to 5 days
- **L** = 1 to 2 weeks

## Sprint Calendar

Six weeks, four lanes. Hard scope freeze at the end of Week 2.

| Week | Theme |
|------|-------|
| 1 | Lane setup, local folder ingest reading PT corpus, GitHub App registered, first AI extract committed to the policy repo |
| 2 | App skeleton reading from local working copy, first chapter render, **scope freeze** |
| 3 | PR-backed edit flow end to end, full handbook generation in Actions, wizard skeleton |
| 4 | Full PT corpus run, wizard complete (six screens), real subdomain live |
| 5 | Bug bash, README polish, install verification on a clean VM |
| 6 | DISC prep, last-mile fixes, public announcement coordination |

## Cross-Cutting / Repo

| ID | Title | Size | Week | Notes |
|----|-------|------|------|-------|
| REPO-01 | Decide license (MIT, Apache 2.0, or AGPL) and add LICENSE file to PolicyCodex repo | S | 1 | **Blocking.** All hands sign off. |
| REPO-02 | README skeleton (status, quick start, design principles, Git-backed architecture, acks) | S | 1 | Use draft from `PolicyWonk-README-Draft.md` |
| REPO-03 | Register a PolicyCodex GitHub App for delegated diocese installs | S | 1 | **Blocking.** Owner: App lane. |
| REPO-04 | Create the PT diocesan policy repo (private) and configure branch protection | S | 1 | Owner: IT director (PT) plus App lane support |
| REPO-05 | Docker Compose and one-command install script | M | 4-5 | App or Publish lane owns |
| REPO-06 | CONTRIBUTING.md naming the configurable-vs-opinionated split | S | 5 | Single owner |
| REPO-07 | Issue and PR templates on the PolicyCodex repo | S | 5 | Single owner |

## Ingest Lane (P0.1)

Scope per the v0.1 PRD: **Local folder ingest only.** Native SharePoint, OneDrive, Google Drive, Box, and Dropbox connectors are deferred to v0.2 per P1.2. Any export from those systems lands in a folder of files that PolicyCodex can ingest.

| ID | Title | Size | Week | Depends on |
|----|-------|------|------|-----------|
| INGEST-01 | Local folder reader: walk a directory recursively, accept path via CLI argument or config | S | 1 | None |
| INGEST-02 | Connector interface so v0.2 cloud connectors (SharePoint, OneDrive, Drive, Box, Dropbox) can drop in alongside `LocalFolderConnector` (P1.2 framework) | S | 1-2 | INGEST-01 |
| INGEST-03 | File content extraction for PDF, DOCX, MD, TXT | M | 1-2 | None |
| INGEST-04 | Source manifest data model (path, hash, last-modified, source label) | S | 2 | None |
| INGEST-05 | Incremental re-run support (skip unchanged files via hash comparison) | S | 3 | INGEST-04 |
| INGEST-06 | Test ingest against the full PT policy corpus exported to a local folder | S | 4 | All Ingest tickets |

**Lane acceptance (week 4):** Given a local directory containing the full PT policy corpus (50+ files), the ingest returns a structured manifest with source paths, content hashes, and timestamps in under 5 minutes. Re-running against the same directory with one file changed re-processes only the changed file. Running against a missing or empty directory fails with a clear error naming the offending path.

## AI Lane (P0.2)

| ID | Title | Size | Week | Depends on |
|----|-------|------|------|-----------|
| AI-01 | LLM provider abstraction interface | M | 1 | None |
| AI-02 | Claude implementation of the provider interface | S | 1 | AI-01 |
| AI-03 | Stub implementations for OpenAI, Gemini, Azure, local Llama | S | 5 | AI-01 |
| AI-04 | Category extraction prompt with eval set | S | 1-2 | AI-02 |
| AI-05 | Owner, effective date, review date, retention extraction prompts | M | 2 | AI-02 |
| AI-06 | Chapter-section-item address suggestion prompt | S | 2 | AI-02 |
| AI-07 | Confidence scoring on all extraction outputs | S | 3 | AI-04, AI-05, AI-06 |
| AI-08 | Markdown plus YAML front matter emitter | S | 2 | AI-04, AI-05, AI-06 |
| AI-09 | Wire AI-suggest buttons into the onboarding wizard | S | 4 | APP-08 (wizard skeleton) |
| AI-10 | Inventory pass orchestrator: runs all extractions on a manifest, commits markdown to the diocese policy repo as initial drafts | M | 3 | All AI tickets, APP-04 (Git ops) |
| AI-11 | Inject diocese's chosen address taxonomy (LA chapters by default) into the extraction prompt context | S | 1 | AI-04, AI-06 |
| AI-12 | Inject the diocese's retention policy (and any other source-of-truth reference documents) into the extraction prompt context. Resolves the 0.144 retention score from the spike. | M | 2 | AI-05, APP-08 |
| AI-13 | Gap-detection pass: flag any policy whose type is not represented in the diocese's retention schedule | S | 3 | AI-12 |

**Lane acceptance (week 4):** Given a manifest of 50+ files, the inventory pass produces matching markdown files with complete YAML front matter, commits them to the diocese policy repo on a draft branch, and opens a single bulk PR. AI suggestion acceptance rate is measurable against a human-reviewed PT subset.

## App Lane (P0.3 + P0.4 + P0.6)

| ID | Title | Size | Week | Depends on |
|----|-------|------|------|-----------|
| APP-01 | Web framework choice and project skeleton | S | 1 | None. **Blocking decision.** |
| APP-02 | Basic local user auth and identity-to-Git-author mapping | S | 1 | APP-01 |
| APP-03 | Git provider abstraction interface | S | 1 | None |
| APP-04 | GitHub provider implementation: clone, branch, commit, push, open PR, read PR state | M | 1-2 | APP-03, REPO-03 |
| APP-05 | Local working copy management (clone on first run, pull on cadence) | S | 2 | APP-04 |
| APP-06 | Catalog list view reading from local working copy of the policy repo | M | 2 | APP-01, APP-05 |
| APP-07 | Edit form for a single policy: opens a branch, commits, opens PR | M | 2-3 | APP-04, APP-06 |
| APP-08 | Onboarding wizard skeleton (seven-screen flow) | M | 3 | APP-01 |
| APP-09 | Wizard screen 1: GitHub repository (create new or connect existing) | S | 3 | APP-08, APP-04 |
| APP-10 | Wizard screen 2: address scheme picker | S | 3 | APP-08 |
| APP-11 | Wizard screen 3: versioning convention picker | S | 3 | APP-08 |
| APP-12 | Wizard screen 4: reviewer roles and required approvers (writes branch protection rules) | S | 4 | APP-08, APP-04 |
| APP-13 | Wizard screen 5: retention defaults | S | 4 | APP-08 |
| APP-14 | Wizard screen 6: LLM provider picker | S | 4 | APP-08 |
| APP-15 | Wizard screen 7: source-of-truth reference documents (point at retention policy, etc.). Stores uploaded files in `references/` in the policy repo. | S | 4 | APP-08 |
| APP-16 | Configuration commit: persist wizard choices as a config file in the policy repo | S | 4 | All wizard tickets |
| APP-17 | PR-state-to-gate mapping: Drafted (open), Reviewed (approved), Published (merged) | S | 3 | APP-04, APP-07 |
| APP-18 | Approve action in UI calls GitHub review API on behalf of authenticated reviewer | S | 3 | APP-04 |
| APP-19 | Publish action in UI merges PR (requires merge permission) | S | 3 | APP-04 |

**Lane acceptance (week 4):** A new admin can complete the seven-screen wizard (including pointing PolicyCodex at the diocese's retention policy as a source-of-truth reference), ingest from a local folder of exported policies, see policies appear as drafts in the policy repo with retention values sourced from the reference document, edit a policy through the form (which opens a PR), have a reviewer approve via the UI, and publish (which merges the PR and triggers the handbook build).

## Publish Lane (P0.5)

| ID | Title | Size | Week | Depends on |
|----|-------|------|------|-----------|
| PUBLISH-01 | Prove Astro builds from a sample markdown directory (Astro picked per OQ-09 2026-05-11) | M | 1-2 | None |
| PUBLISH-02 | Chapter-section-item URL scheme and page templates | M | 2 | PUBLISH-01 |
| PUBLISH-03 | Default theme modeled on the LA handbook | M | 3 | PUBLISH-02 |
| PUBLISH-04 | Changelog page generated from `git log` of the policy repo | S | 3 | PUBLISH-02 |
| PUBLISH-05 | RSS feed generation | S | 3 | PUBLISH-02 |
| PUBLISH-06 | GitHub Actions workflow: build handbook on push to `main`, deploy artifact | M | 3 | PUBLISH-01, REPO-04 |
| PUBLISH-07 | Subdomain deployment doc and Caddy or Nginx reverse-proxy config (or GitHub Pages alternative) | M | 4 | None |
| PUBLISH-08 | Vector chunk format export (architectural placeholder for v0.2 RAG) | S | 5 | PUBLISH-02 |

**Lane acceptance (week 4):** Given a merged PR on the diocese's policy repo, GitHub Actions builds and deploys a static handbook with chapter pages, individual policy pages, a `git log`-driven changelog, and an RSS feed to the configured subdomain within 5 minutes of merge.

## Critical Path

The longest dependency chain across lanes:

```
INGEST-01 (local folder reader)
  → INGEST-03 (file content extraction)
    → INGEST-04 (manifest)
      → AI-10 (inventory pass commits drafts)
        → APP-04 (GitHub provider)
          → APP-07 (edit form opens PR)
            → APP-17 (PR-state-to-gate)
              → APP-19 (publish merges PR)
                → PUBLISH-06 (Actions builds and deploys)
                  → first published handbook page on a real subdomain
```

Two blockers must clear in week 1, full stop:

- **App framework decision** (gates APP-01 and the entire App lane).
- **GitHub App registration plus PT diocesan policy repo creation** (gates APP-04, AI-10, and PUBLISH-06).

A third near-blocker, by Week 4: the **PT policy corpus exported to a local folder.** The 19 PDFs from the spike are enough to prove the path; the full demo corpus has to be on disk before INGEST-06 runs. This is data-handling, not authentication, and it can be done piecemeal as PT decides which private policies to include.

If any of the two true blockers slips past Friday of week 1, the timeline slips with it.

## Sprint Board Suggestions

- Use a kanban with five columns: Backlog, This Week, In Progress, Review, Done.
- One swimlane per coder lane (Ingest, AI, App, Publish) plus one for Cross-Cutting.
- Cross-lane dependencies show as blocked tickets tagged "depends on [TICKET-ID]."
- Stand-up cadence: 15-minute async update three times a week (Mon, Wed, Fri) plus a 30-minute lane-leads sync once a week.
- Ticket close requires acceptance criteria from `PolicyWonk-v0.1-Spec.md` checked off in the PR description.
- For the App lane specifically: every ticket landing should be exercised end to end against the PT policy repo by Friday of its week, since most App work is downstream of GitHub round trips.

## Open Decisions Tracked Outside the Tickets

These are spec-level open questions, not tickets. Resolve them in week 1:

- ~~License (REPO-01)~~ **Resolved 2026-05-11: AGPL-3.0.**
- ~~Web framework (APP-01)~~ **Resolved 2026-05-11: Python + Django.**
- ~~Static-site generator (PUBLISH-01)~~ **Resolved 2026-05-11: Astro.**
- Git operations library: shell out to `git` binary, or `libgit2` bindings (recommend shelling out for v0.1)
- Trademark and naming (is "PolicyCodex" available?) — open as OQ-02; TESS search pending.
- LA contact's role in the README (advisor, design reviewer, co-author) — open as OQ-05.
- PT diocesan leadership approval for the public handbook subdomain — open as OQ-06.
- ~~PT GitHub organization availability (or creation)~~ **Resolved 2026-05-11: `Diocese-of-Pensacola-Tallahassee`.**
