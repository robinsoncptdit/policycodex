# PolicyCodex

**Status:** pre-alpha, active development. v0.1 targets DISC mid-June 2026. The repo is public; the product has not launched.

*Renamed from PolicyWonk to PolicyCodex on 2026-05-11. Primary domain: `policycodex.org`.*

*A policy lifecycle tool for Catholic dioceses (and other mission-driven institutions with too many governance documents and not enough hours).*

PolicyCodex takes the pile of policies, procedures, and by-laws scattered across your SharePoint and Google Drive, helps you inventory and clean them up with AI assist, runs every change through a pull-request-backed approval workflow, and publishes a versioned handbook on a subdomain you control.

## Status

Pre-alpha. Active development for a public demo at DISC mid-June 2026. Diocese zero is the Diocese of Pensacola-Tallahassee. Design reviewed by the Archdioceses of Los Angeles and Baltimore.

If you are a diocesan IT director and you want to be install number two, please open a discussion or reach out.

## What This Solves

If you run technology for a diocese, you probably know the pattern:

- Hundreds of policies scattered across SharePoint folders, shared drives, and filing cabinets
- No consistent metadata (no owner, no effective date, no review cadence)
- No version history anyone trusts
- No public handbook for parish or school staff to consult
- An annual review cycle that gets mandated and never executed
- Compliance frameworks (USCCB Charter, canon law, civil and state nonprofit law) that overlap in confusing ways

PolicyCodex is the tool you would have built yourself if you had three more hours every week.

## What It Does

1. **Ingests** policy documents from a local folder (v0.1). SharePoint and Google Drive connectors are planned for v0.2.
2. **Inventories** them with AI: proposes a category, owner, effective date, review cadence, retention period, and a chapter-section-item address for each policy. Each policy gets a companion audit file recording the AI's confidence per field plus the provider, model, token counts, and timestamp of the call, so you can attribute API spend.
3. **Stores** every policy as a markdown file in a private GitHub repo your diocese owns. Every change is a commit. Every approval is a pull request review.
4. **Routes** each entry through a simple human approval workflow with three default gates (Drafted, Reviewed, Published) that map to PR states.
5. **Publishes** approved policies as a static handbook site, built and deployed by GitHub Actions on every merge to a subdomain you control, with stable per-policy URLs. A `git log`-driven changelog and an RSS feed are planned for v0.1.
6. **Stays out of the way** of your existing platforms. PolicyCodex does not replace SharePoint, Google Workspace, GitHub, or your CMS. It reads from your filesystems, helps you organize, commits to your repo, and emits a handbook.

## Who It Is For

- Catholic dioceses (the primary target)
- Religious orders, Catholic universities, Catholic healthcare systems
- Any mission-driven nonprofit with hundreds of policies and a lean back-office team

If you are a diocesan IT director or a document control owner, this is built for you.

If you are a non-technical editor (a CFO updating Section 5.2.8 of the financial handbook, an HR director changing a policy paragraph), the friendly admin web app is built for you. You will never see Git. You will see a form.

If you sell generic enterprise document management, this probably is not your tool.

## Design Principles

**Opinionated by default. Configurable where dioceses have legitimate variation. AI-assisted throughout.**

- We default to the LA Archdiocese chapter-section-item numbering. We support a Catholic-healthcare-style department code convention as an alternative.
- We default to semver for individual policy documents (1.0 first published, 1.1 minor revision, 2.0 obligations changed).
- We require five metadata fields on every published policy: owner, effective date, last review, next review, retention period.
- We ground AI extraction in your existing documents. Point PolicyCodex at your Document Retention Policy and it uses your real retention schedule rather than guessing. Same pattern for any other canonical reference your diocese maintains.
- We default to Claude as the LLM. We support OpenAI, Gemini, Azure OpenAI, and local Llama as alternates.
- We assume humans approve every published policy. AI proposes. Humans decide. Lawyers gonna lawyer.

## Architecture

PolicyCodex is **Git-backed**. Every diocese running PolicyCodex gets a private GitHub repo where its policies live as markdown files with YAML front matter. Version control, audit, branch-protected approvals, backups, and CI/CD are handled by GitHub. PolicyCodex is the friendly layer on top.

```
┌──────────────────────┐    ┌──────────────────────┐
│  SharePoint /        │    │   Diocese GitHub     │
│  Google Drive        │    │   Repo (private)     │
│  (source documents)  │    │   - markdown files   │
└─────────┬────────────┘    │   - YAML front matter│
          │ INGEST          │   - branch protection│
          ▼                 └────┬─────────────────┘
┌──────────────────────┐         │ APP                 ▲
│  AI Inventory Pass   │─────────┤ (web UI commits     │
│  (extract metadata,  │ commits │  on user behalf,    │
│  emit markdown)      │ drafts  │  opens PRs, calls   │
└──────────────────────┘         │  GitHub review API) │
                                 │                     │
                                 ▼ on merge to main    │
                        ┌──────────────────────┐       │
                        │  GitHub Actions      │       │
                        │  (PUBLISH lane)      │       │
                        └─────────┬────────────┘       │
                                  ▼                    │
                        ┌──────────────────────┐       │
                        │  Public Handbook     │───────┘
                        │  Subdomain           │
                        │  (static site, RSS)  │
                        └──────────────────────┘
```

Four lanes:

- **Ingest** reads source documents from a local folder in v0.1. SharePoint and Google Drive connectors are v0.2.
- **AI** runs the inventory pass via a model-agnostic provider interface and emits markdown plus YAML front matter.
- **App** is the admin web interface. It commits to the diocese's GitHub repo, opens PRs on user actions, and surfaces PR state as gate state.
- **Publish** is a GitHub Actions workflow that builds and deploys the handbook on every merge.

Run PolicyCodex on a small VM. Connect it to your private GitHub repo. Point it at your filesystems. Configure your conventions through the onboarding wizard. The handbook deploys to a subdomain you control.

## Install

**Profile A — source clone (developers, AGPL transparency):**

```
git clone https://github.com/robinsoncptdit/policycodex.git
cd policycodex
./install.sh
```

**Profile B — pre-built image (most dioceses):**

```
docker run -d \
  -p 8000:8000 \
  -v policycodex-data:/data \
  --name policycodex \
  ghcr.io/robinsoncptdit/policycodex:latest

open http://localhost:8000
```

Both paths land you in the in-browser onboarding wizard. No environment files
to edit, no credentials on disk, no terminal interaction after the install
command. The wizard collects everything (admin account, GitHub App credentials,
LLM API key, repo, configuration, retention policy, your policy documents) and
opens one pull request to your diocese repo at the end.

To wipe an install and start over: `docker compose down -v && docker volume rm policycodex-data`.

### Before you begin

PolicyCodex needs **API access to a language model, not a consumer chat subscription.** The consumer plans (Claude Pro / Pro Max / Teams, ChatGPT Plus, Google One) have no programmatic access and will not work. Provision an API key before you reach wizard step 6:

- **Anthropic Claude** (default) — an Anthropic API key, not Claude Pro / Pro Max / Teams. The API is pre-paid and billed per token via console.anthropic.com.
- **OpenAI** — an OpenAI API key, not ChatGPT Plus.
- **Google Gemini** — a Gemini API key or Vertex AI credentials, not Google One.
- **Azure OpenAI** — Azure OpenAI deployment credentials (an Azure subscription with the OpenAI service deployed).
- **Local Llama** — no third-party key; runs on your own VM.

The wizard's LLM-provider screen links each provider's API-key docs and shows rough monthly cost ranges.

### Rebuilding the CSS

The compiled stylesheet (`static/css/policycodex.css`) is pre-built and committed, so a plain install needs no toolchain. If you edit a template or a theme variable, regenerate it with `scripts/build-css.sh`. The script downloads the Tailwind standalone CLI and the DaisyUI plugins into the gitignored `.tools/` directory the first time you run it, so you need no Node install. Commit the regenerated `static/css/policycodex.css` alongside your template change.

## Roadmap

**v0.1 (June 2026):** ingest, AI inventory grounded in the diocese's own reference documents, PR-backed approval UI, GitHub Actions handbook publication, seven-screen onboarding wizard, public PolicyCodex repo.

**v0.2 (post-DISC):** Q&A chatbot over the published handbook (RAG), Google Drive parity, compliance framework library expansion, email notifications for review cadence, rich-text edit mode for non-markdown editors.

**Later:** full Seven-Gate workflow configurability, GitHub Enterprise / GitLab / Gitea support, multi-tenant hosting, regulatory change watching, multilingual handbook.

## Contributing

PolicyCodex is being built by a small group of coders with deep ties to the diocesan IT community. We welcome contributions, especially from people who actually run policy programs at dioceses, nonprofits, or healthcare systems.

Before proposing changes that conflict with the core philosophy, read the Design Principles above for the configurable-vs-opinionated split. A full `CONTRIBUTING.md` with the contribution flow is on the way.

## Acknowledgments

- The **Diocese of Pensacola-Tallahassee**, install zero and patient test subject.
- The **Archdiocese of Los Angeles**, whose [public handbook](https://handbook.la-archdiocese.org/) is the reference implementation we are designing toward, and **David Schmitt** (IT Director, Archdiocese of Los Angeles), reviewer.
- **Marcus Madsen** (Director of IT, Archdiocese of Baltimore), design reviewer.
- The **DISC** (Diocesan Information Systems Conference) community of diocesan IT directors.

## License

PolicyCodex is licensed under the **GNU Affero General Public License v3.0 (AGPL-3.0)**. See [LICENSE](LICENSE) for the full text.

AGPL-3.0 means: you may run, modify, and redistribute PolicyCodex freely; if you offer it as a network service to anyone else, you must make your modified source available to those users. This protects the open-source maintainer model and keeps the project healthy for the dioceses installing it.
