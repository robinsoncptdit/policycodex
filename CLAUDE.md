# CLAUDE.md

Standing context for the PolicyCodex project. Read this first when working in this folder.

*Renamed from PolicyWonk to PolicyCodex on 2026-05-11. Primary domain: `policycodex.org`. The working folder path stays `/Users/chuck/PolicyWonk/` and existing `PolicyWonk-*.md` file names stay as-is, to avoid breaking subagent prompts and configs.*

## What This Project Is

PolicyCodex is a tool that helps Catholic dioceses (and adjacent mission-driven nonprofits) manage the full lifecycle of their governing documents: inventory, review, approval, publication, and ongoing maintenance.

The product summary lives in `PolicyWonk-Project-Summary.md`. The active spec lives in `PolicyWonk-v0.1-Spec.md`. The sprint board lives in `PolicyWonk-v0.1-Tickets.md`. Read the spec before doing any substantive work in this folder.

## Current Status

Active. Brainstorm complete, v0.1 spec and engineering tickets locked, riskiest-assumption spike passed (70.9% acceptance excluding always-null fields, recorded in `PolicyWonk-Spike-Plan.md`). Week 1 of a six-week sprint is in progress, targeting a public demo at DISC (Diocesan Information Systems Conference) mid-June 2026. Pensacola-Tallahassee is install zero. The Archdiocese of Los Angeles is the reference design partner.

The project is open source under a maintainer model (the maintainer earns through setup, support, and customization, not through licensing).

## What's In This Folder

Active artifacts:

- `PolicyWonk-Project-Summary.md` is the spirit-level product summary
- `PolicyWonk-v0.1-Spec.md` is the active PRD
- `PolicyWonk-v0.1-Tickets.md` is the engineering sprint board
- `PolicyWonk-Week-1-Sprint-Plan.md` is the current sprint plan
- `PolicyWonk-Spike-Plan.md` is the riskiest-assumption spike, including results
- `PolicyWonk-README-Draft.md` is the draft of the public-facing GitHub README
- `spike/` contains the runnable extraction script (`extract.py`), input PDFs, and per-policy JSON outputs

Historical artifacts:

- `Initial.md` is the original 2024 feature brief
- `PolicyWonk-Notes-1.md` through `PolicyWonk-Notes-9.md` are the original 2024 working notes
- `.obsidian/` is the Obsidian vault config

This vault opens in Obsidian. Keep new files in markdown.

## How To Approach Work Here

1. Treat the v0.1 spec and tickets as the active plan. Treat the original 2024 notes as historical context.
2. The Git-backed architecture is settled. Do not propose alternative storage models without new information.
3. Save brainstorming output, design notes, and analysis as new markdown files in this folder.
4. Naming: free-form descriptive names are fine (for example, `Wedge-Product-Options.md`). The `PolicyWonk-Notes-N.md` pattern is reserved for the original 2024 notes.

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
