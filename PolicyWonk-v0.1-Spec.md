# PolicyWonk v0.1 PRD

*Target: working demo + public repo by DISC mid-June 2026.*

## Problem Statement

Most Catholic dioceses keep hundreds of policies, procedures, and by-laws scattered across SharePoint folders, Google Drives, and filing cabinets, with inconsistent metadata, no version control, no annual review cadence, and no public-facing handbook. Front-line staff at parishes and schools cannot find the policy they need when they need it. Policy owners have no system that enforces review cycles. The cost is operational risk, legal exposure, and lost staff trust in the policy program.

## Architecture in Brief

PolicyWonk is **Git-backed**. Every policy is a markdown file in a private GitHub repo per diocese. Every edit is a commit. Every approval gate is a pull request state. Every published handbook is a static site built by GitHub Actions on merge to main.

This means version control, audit, branch-protected approvals, backups, and CI/CD are handled by GitHub, not by us. PolicyWonk is the friendly layer on top: ingest, AI inventory, web-based editing for non-technical users, onboarding wizard, and a default handbook theme. Non-technical users (a CFO editing one section) never see Git. They see a form. The IT director can drop into the GitHub UI any time they want.

GitHub.com is the v0.1 default. The Git provider is abstracted so GitHub Enterprise, GitLab, and self-hosted Gitea can be added later.

## Goals

1. **A diocese can go from "scattered files" to "published handbook" in under one week.** Measure: time from first ingest to first public handbook URL.
2. **Every published policy carries five required metadata fields:** owner, effective date, last review, next review, retention period. Measure: percentage of published policies with complete metadata.
3. **Every policy change is auditable down to the commit, with a named approver.** Measure: 100% of published policies have a corresponding merged PR with at least one approving review.
4. **DISC mid-June 2026 attendees can clone, install, and run a meaningful demo in under 30 minutes.** Measure: qualitative feedback at the conference plus install-success reports.
5. **At least one diocese beyond Pensacola-Tallahassee installs PolicyWonk in production by August 2026.** Measure: a public deployment record.
6. **Pensacola-Tallahassee uses the published handbook as its canonical policy reference within 60 days of v0.1 release.** Measure: link from ptdiocese.org or an internal staff portal page.

## Non-Goals

1. **Multi-LLM consensus reviews.** Overbuilt for the problem. Deferred unless a diocese explicitly asks.
2. **A workflow engine with more than three gates.** Three gates (Drafted, Reviewed, Published) cover v0.1. Full Seven-Gate configurability is v0.2.
3. **Building our own version control or audit log.** GitHub does this better than we can. We build on it, we do not replace it.
4. **Multi-tenant SaaS hosting.** Each diocese runs its own VM and connects to its own private GitHub repo. Multi-tenant changes the security and operations story; not a v0.1 problem.
5. **A designer-polished consumer UI.** DISC's audience is technical. A working web app and a clean repo beat a designer-tested wizard for this audience.
6. **Q&A chatbot over the handbook.** Stretch goal only. Real RAG belongs in v0.2.
7. **Pricing, packaging, or any commercial logic.** Open-source maintainer mode means no payment flow at v0.1.
8. **Public default for the policy repo.** Private by default. The public face is the generated handbook subdomain, not the source repo.

## User Stories

### Primary persona: Diocesan IT Director (installer and admin)

- As a diocesan IT director, I want to install PolicyWonk on a self-hosted VM in under an afternoon so I can demo it internally without a procurement cycle.
- As a diocesan IT director, I want PolicyWonk to commit every policy edit to a private GitHub repo so version control, audit, and CI/CD live on infrastructure I already trust.
- As a diocesan IT director, I want to drop a folder of exported policies onto the PolicyWonk VM and get a structured inventory of every file so I can see the full landscape for the first time. (Native connectors for SharePoint, OneDrive, Google Drive, and others are deferred to v0.2.)
- As a diocesan IT director, I want to choose between LA-style chapter numbering and Catholic-healthcare-style department codes during onboarding so I can match my diocese's existing convention.
- As a diocesan IT director, I want to choose which LLM provider PolicyWonk uses (Claude default, optional OpenAI, Gemini, Azure, or local) so I can match my diocese's data sovereignty requirements.

### Secondary persona: Document Control Owner (admin user)

- As a document control owner, I want AI to suggest a category, owner, effective date, and review cadence for every discovered policy so I do not have to fill in 200 metadata records by hand.
- As a document control owner, I want to review and approve each AI-suggested entry through a simple web interface so a human stays in the loop on every published record.
- As a document control owner, I want gate transitions to be backed by Git pull requests so every review approval is signed, dated, and attributed.
- As a document control owner, I want to see which policies are missing metadata, missing review dates, or out of date so I know what to triage next.

### Tertiary persona: Subject-matter editor (CFO, HR director, etc.)

- As a CFO updating Section 5.2.8 of the financial handbook, I want to edit the policy text in a friendly form without ever seeing Git so I can make the change in five minutes and submit it for review.
- As a subject-matter editor, I want to see the current owner and last review date for the section I am editing so I know who else is involved.
- As a subject-matter editor, I want my edit to show up as a pull request that the document control owner reviews before publication so I do not accidentally publish a draft.

### Quaternary persona: Parish or School Staff (handbook reader)

- As a parish staff member, I want a public handbook URL with stable chapter-section-item addresses so I can link directly to the section I am following.
- As a parish staff member, I want to see when each policy was last reviewed and who owns it so I know whether to trust the guidance or ask a question.
- As a parish staff member, I want an RSS or email subscription to changes so I learn about updates without checking the site daily.

### Open-source contributor (DISC attendee, post-demo)

- As a DISC attendee, I want to clone the PolicyWonk repo and run it against sample data so I can decide whether to adopt or contribute.
- As a contributor, I want a README that names the design principles and the configurable-vs-opinionated split so I do not waste time proposing changes that conflict with the core philosophy.

## Requirements

### Must-Have (P0)

**P0.1 Local Folder Ingest**

Behavior: Read source documents from a local directory (path passed via CLI argument or config). Walk the directory recursively. Read file contents (PDF, DOCX, MD, TXT). Track source path and content hash for incremental re-runs.

Filesystem-agnostic by design. Any export from SharePoint, OneDrive, Google Drive, Box, Dropbox, a network share, or a scanned filing cabinet ends up as a folder of files that PolicyWonk can ingest. Native cloud connectors are deferred to v0.2 per P1.2.

Acceptance:
- Given a directory containing 50+ policy files, when ingest runs, then it returns a structured manifest of every file with source paths and content hashes within 5 minutes.
- Given a previous manifest plus the same directory with one file changed, when ingest runs, then only the changed file gets re-processed (incremental re-run via hash comparison).
- Given a directory path that does not exist or is empty, when ingest runs, then it fails with a clear error naming the offending path.

**P0.2 AI Inventory Pass**

Behavior: For each ingested file, propose category, owner role, effective date, last review date, next review date, retention period, suggested chapter-section-item address, and a 1.0 version stamp. Output as markdown files with YAML front matter, ready to commit to the diocese's policy repo. Claude default. LLM provider abstracted via a single interface supporting OpenAI, Gemini, Azure OpenAI, and local Llama as alternates.

The extraction prompt receives two pieces of injected context per the spike findings: (1) the diocese's chosen address taxonomy (default LA Chapter.Section.Item), and (2) the diocese's source-of-truth reference documents per P0.X below. Without those, retention and address quality drop sharply (validated against PT corpus on May 5, 2026).

Acceptance:
- Given a catalog of 50+ ingested files, when the inventory pass runs, then a corresponding markdown file with complete YAML front matter is staged for commit, with confidence scores recorded in a separate audit file.

**P0.X Single Source of Truth Reference Documents**

Behavior: During onboarding, the diocese can designate one or more existing documents as "source of truth" references that the AI inventory pass uses to ground its proposals. The Document Retention Policy is the canonical example: pointed at it, the AI reads the retention schedule, the document-type taxonomy, and uses both to constrain its suggestions for retention period, category, and (when no separate address scheme is provided) a starter chapter ordering. If the diocese has no such policy, PolicyWonk offers a starter retention schedule derived from USCCB norms plus state nonprofit law that the diocese can adapt.

Reference documents also drive gap detection: any policy in the catalog that is not represented in the retention schedule is flagged for human review.

Acceptance:
- Given a designated retention policy reference, when the inventory pass runs, then proposed retention periods are sourced from that document for at least 80% of the catalog, and any policy not represented in the schedule is flagged in its YAML front matter.

**P0.3 GitHub Provider Integration**

Behavior: PolicyWonk authenticates to GitHub.com using a GitHub App. It can create or connect to a private repo per diocese, clone it locally as a working copy, create branches, commit changes, open pull requests on behalf of authenticated users, and read PR state. Branch protection on `main` is configured to require at least one approving review.

Acceptance:
- Given a GitHub App installed on a diocese's GitHub organization, when PolicyWonk is configured with a target repo, then it can clone, branch, commit, push, and open PRs for any authenticated admin action that modifies a policy.
- Given an open PR, when a reviewer approves it in GitHub or in the PolicyWonk UI, then PolicyWonk can detect the approval and reflect the gate state.

**P0.4 Admin Web App with PR-Backed Approval UI**

Behavior: Display the policy catalog as a sortable, filterable list, reading from the local working copy of the policy repo. For each entry, show the current AI suggestion or last-published version, and offer an edit form. On save, create a branch, commit the edit, and open a PR. Three gate states map to PR states:

- **Drafted** = open PR with no required reviews completed
- **Reviewed** = open PR with at least one approving review
- **Published** = PR merged to `main`

Authenticated user required for any state change. The user's identity attaches to the commit author.

Acceptance:
- Given an authenticated admin, when they edit a metadata or content field and click "Submit for Review," then PolicyWonk creates a branch, commits the change as that user, and opens a PR. The PR's state is reflected in the admin UI.
- Given an open PR for a policy, when a designated reviewer clicks "Approve" in the UI, then a GitHub review is recorded against the PR and the policy moves to Reviewed in the UI.
- Given a Reviewed policy, when an admin with merge permission clicks "Publish," then the PR merges, the handbook builds, and the policy moves to Published.

**P0.5 Handbook Static-Site Generator (CI-Driven)**

Behavior: A GitHub Actions workflow in the policy repo runs on every merge to `main`. It takes the merged markdown content and YAML front matter and generates a public handbook with chapter-section-item addressing, stable per-policy URLs, a changelog page derived from the Git history, and an RSS feed. The generated site deploys to a configurable subdomain (Caddy or Nginx reverse proxy on the diocese's VM, or optionally GitHub Pages).

Acceptance:
- Given at least one merged PR for a policy, when the GitHub Actions workflow runs, then a static handbook with chapter pages, individual policy pages, a changelog, and an RSS feed is built and deployed to the configured subdomain within 5 minutes of merge.

**P0.6 Onboarding Wizard**

Behavior: Seven screens covering (1) GitHub repository, (2) address scheme, (3) versioning convention, (4) reviewer roles and required approvers, (5) retention defaults, (6) LLM provider, (7) source-of-truth reference documents (the diocese can point at an existing retention policy or similar canonical document; PolicyWonk uses it to ground AI extractions per P0.X). Each screen has a sensible default, an "AI suggest based on my org" affordance where it makes sense, and a "show alternatives" path. Choices persist as configuration files inside the policy repo (so the configuration itself is versioned alongside the content).

Acceptance:
- Given a fresh install, when a new admin completes the wizard, then a private GitHub repo is created or connected, branch protection is configured, all seven settings are committed to the repo as configuration, any designated reference documents are stored in a `references/` directory in the repo, and the inventory pass and handbook generator use them on first run.

**P0.7 Public Repo and README**

Behavior: Public GitHub repo for PolicyWonk itself (the application). README names the design principles, the configurable-vs-opinionated split, supported filesystems, supported LLM providers, and the Git-backed architecture. One-command install (Docker Compose or shell script).

Acceptance:
- Given a fresh VM with Docker installed, when a developer follows the README, then PolicyWonk is running on a configured port within 30 minutes.

### Nice-to-Have (P1)

**P1.1 Compliance Framework Library (functional).** Markdown directory with three or four working checklists (USCCB Charter for the Protection of Children, common state nonprofit retention rules, IT acceptable-use baseline, by-laws standard structure). Wire one checklist into the inventory pass to flag gaps in the diocese's catalog.

**P1.2 Filesystem connector pluggability framework (v0.2 promise).** Define a connector interface in v0.1 such that the v0.1 `LocalFolderConnector` can be joined later by `SharePointConnector`, `OneDriveConnector`, `GoogleDriveConnector`, `BoxConnector`, `DropboxConnector`, and similar drop-in implementations. v0.1 ships only `LocalFolderConnector`. Connector priority for v0.2 is set by what early adopters at DISC actually request, not by us guessing now.

**P1.3 Static-Site Search.** Client-side index over the published handbook (Lunr.js or Pagefind).

**P1.4 Email Notifications.** Outbound notifications as a policy approaches its next review date. Configurable cadence (60, 30, 0 days).

**P1.5 Rich-Text Editor for Non-Technical Users.** A WYSIWYG mode on the edit form for editors who do not want to see markdown.

### Future Considerations (P2)

**P2.1 Q&A Chatbot (RAG over the handbook).** Architectural note: the handbook generator should also emit a vector-friendly chunk format so RAG can be added later without re-extracting.

**P2.2 Full Seven-Gate Workflow.** Architectural note: gate states must map to a configurable set of GitHub branch protection rules and required reviewers, not be hardcoded to three states.

**P2.3 Git Provider Pluggability.** Architectural note: keep the GitHub-specific code behind a Git provider interface so GitHub Enterprise, GitLab, and self-hosted Gitea bolt on later.

**P2.4 Multi-Tenant Hosting.** Architectural note: tenant identifier is a first-class concept in configuration, even though only one tenant is used in v0.1.

**P2.5 Regulatory Change Watching.** Architectural note: every checklist in the framework library carries a "last verified" date and a source URL.

**P2.6 Multilingual Handbook.** Architectural note: translation belongs as a per-policy attribute (additional markdown file per language, sharing front matter), not a separate document.

## Success Metrics

### Leading Indicators (first 30 days post-DISC)

- Repo clones: 25+ within 7 days of DISC, 100+ within 30 days.
- Successful local installs: 5+ within 14 days, self-reported via a GitHub Discussion thread.
- Diocese-zero handbook live: PT runs the published handbook on a real subdomain by July 1, 2026.
- AI suggestion acceptance rate: 60%+ of AI-proposed metadata fields accepted without human edit on the PT corpus.
- PR-backed audit trail: 100% of Published policies have a corresponding merged PR with named approver.

### Lagging Indicators (60 to 90 days post-DISC)

- Install-ones: 2+ dioceses beyond PT running v0.1 in production.
- Community pull requests merged on the PolicyWonk repo: 5+.
- Services revenue signal: 1+ paid setup or support engagement booked.
- Handbook usage at PT: linked from at least one staff portal page or internal newsletter.

## Open Questions

### Engineering

- **Web framework for the admin app**: Python-Django, Node-Next, or thin Go plus HTMX? Driven by which lane owner has the strongest preference. **Blocking before week 1.**
- **Git operations library**: shell out to `git` binary, or use `libgit2` bindings (e.g., pygit2, isomorphic-git)? Recommend shelling out for v0.1 simplicity. Non-blocking.
- **Static-site generator inside CI**: Astro, Hugo, or Eleventy? Recommend Astro for component flexibility, Hugo for build speed. Non-blocking.
- **AI extraction prompt architecture: monolithic vs split**. The spike validated a single monolithic prompt that extracts all eight metadata fields per call at 70.9% acceptance (excluding always-null fields). Tickets AI-04, AI-05, AI-06 currently split extraction into per-field-family prompts. **PM recommendation:** keep the monolithic prompt as the v0.1 baseline, treat AI-04/05/06 as eval-set work against that prompt rather than separate prompt files, and add AI-11 (taxonomy injection) and AI-12 (retention reference) as additional injected context on the existing prompt. Splitting a working 70.9% prompt risks regressing before improving, which is poor calendar economics six weeks from DISC. Final call is Chuck's, after the Plan subagent returns its recommendation. **Blocking before AI-04 dispatch.**
- **Category taxonomy is provisional.** The 12 categories used in the spike prompt (Finance, HR, IT, Safe Environment, Schools, Worship, Parish Operations, Stewardship, By-Laws, Communications, Risk, Other) are working defaults from the spike. The final v0.1 list should be confirmed against the LA handbook chapter structure and the PT corpus during Week 2. Non-blocking.

### Design

- **Default handbook theme**: ship a default modeled on LA's, allow override via CSS, or require the diocese to bring a theme? Recommend ship a default. Non-blocking.

### Legal

- **Open-source license for PolicyWonk itself**: MIT, Apache 2.0, or AGPL? AGPL preserves services-revenue moat. MIT maximizes adoption. **Blocking before public repo creation.**
- **Trademark and naming**: is "PolicyWonk" available, and does it need to clear before DISC? **Blocking before DISC.**

### Stakeholder

- Does the LA contact agree to be named as design reviewer or co-author in the README? **Blocking before DISC.**
- Does PT diocesan leadership agree to PolicyWonk publishing a handbook subdomain on its behalf? **Blocking before public demo.**
- Does PT have an existing GitHub organization for the diocese, or do we need to create one? **Blocking before week 1.**

### Data

- Has the PT policy corpus been fully exported to a local folder? The spike used 19 PDFs from `ptdiocese.org` public pages. The full inventory may include additional policies stored privately. Drives realistic demo timing. **Blocking before week 1.**

## Timeline Considerations

**Hard deadline: DISC mid-June 2026.** Approximately six weeks from today. The demo must run on PT data, with a working PR flow, a deployed handbook subdomain, and a clone-able public repo.

**Team:** four lanes across three or four coders.

1. **Ingest lane.** Local folder reader, file parsing, source-doc extraction.
2. **AI lane.** Prompt design, LLM provider abstraction, markdown plus YAML front-matter output.
3. **App lane.** Admin web app, GitHub integration, PR-backed approval UI, onboarding wizard.
4. **Publish lane.** GitHub Actions workflow, static-site generator, default theme, subdomain deployment.

If only three coders are available, fold Publish into App.

**Suggested phasing within six weeks:**

- **Week 1**: Lane setup. Local folder ingest working end to end on the PT corpus. AI inventory pass producing first markdown file with YAML front matter. GitHub App registered. License decision made. PolicyWonk public repo created. PT diocese's policy repo created (private).
- **Week 2**: App skeleton with list view reading from a local working copy of the policy repo. Static-site generator producing a single chapter page. GitHub Actions workflow scaffolded. Compliance framework directory seeded with one checklist. **Scope freeze at end of week 2.**
- **Week 3**: Edit form opens PRs end to end. Gate states reflect PR states. Handbook generator produces full chapter hierarchy with RSS. Onboarding wizard skeleton.
- **Week 4**: AI inventory pass tested against full PT corpus. Onboarding wizard complete (six screens). Handbook deployed to a real subdomain via GitHub Actions.
- **Week 5**: Bug bash. README polish. Install path verified on a clean VM. Demo script rehearsed.
- **Week 6**: DISC presentation prep. Last-mile fixes. Public announcement coordinated.

**Dependencies:**

- PT policy corpus exported to a local folder. Required by week 1. Already partially complete: 19 PDFs from `ptdiocese.org` public pages used in the spike. Remaining work is whatever private policies the diocese wants in the v0.1 demo.
- PT GitHub organization (or create one). Required by week 1.
- LA contact's review of v0.1 wireframes or a working build. Required by end of week 3.
- Domain registration for the handbook subdomain. Required by week 4.
