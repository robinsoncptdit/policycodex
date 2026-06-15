# PolicyCodex

**Status:** v0.1 released 2026-06-14. Public repo. Open source under AGPL-3.0.

*Renamed from PolicyWonk to PolicyCodex on 2026-05-11. Primary domain: `policycodex.org`.*

A policy lifecycle tool for Catholic dioceses and other mission-driven institutions with too many governance documents and not enough hours.

PolicyCodex takes the pile of policies, procedures, and by-laws scattered across your SharePoint and Google Drive, helps you inventory and clean them up with AI assistance, runs every change through a pull-request-backed approval workflow, and publishes a versioned handbook on a subdomain you control.

Install zero is the Diocese of Pensacola-Tallahassee. Design reviewed by the Archdioceses of Los Angeles and Baltimore.

## Who PolicyCodex Is For

PolicyCodex serves five different people in a diocese. Each one cares about different things. The product is designed so each persona sees only what matters to them.

### The CFO, HR Director, or department head who owns a policy

You sometimes need to update Section 5.2.8 of the financial handbook, or change a single paragraph in the personnel policy. Today that means emailing the IT director, waiting for the file to be located, editing in Word, sending it back, and hoping the version on SharePoint is the one parishes actually use.

In PolicyCodex you log in, find your policy in a searchable catalog, and edit it through a friendly web form. You never see Git. You never touch a file system. When you submit, the tool opens a pull request for review and tells you who is next to approve. When the reviewer signs off and the publisher merges, the public handbook updates within five minutes. Every version you touched is dated and attributed to your name in the audit trail.

### The Chancellor or document control owner

You are responsible for keeping the diocesan policy program coherent. You know which policies are out of date, which lack owners, and which contradict each other, but you do not have the time to do the inventory yourself.

In PolicyCodex you point the AI inventory pass at your existing policy folder. Within minutes the tool proposes a category, owner, effective date, review cadence, retention period, and chapter-section-item address for every document. You review the AI's suggestions through a web UI, accept what is right, fix what is not, and your library is suddenly searchable with consistent metadata. Every published policy carries the five required ISO-30301-style fields. Every change is a pull request with a named approver and a date.

### The Bishop or executive leadership

You care that the policies the diocese publishes are current, accurate, approved by the right people, and traceable. You do not want to spend executive council time approving routine administrative documents that the chancellor or HR director can sign off on directly.

PolicyCodex gives you a published handbook at a stable URL your parishes and schools link to, where every policy carries its owner, effective date, and last-reviewed date. Behind the scenes, every published version has a named human approver and a merged pull request. The audit trail is real and complete. The four-layer protection model means routine edits do not require board attention, while the foundational policies that drive the rest stay locked down.

### The diocesan IT director

You will install PolicyCodex, configure it, and operate it. You probably already use SharePoint, GitHub, and Google Workspace. You do not want another platform; you want a small piece of software that ties what you already have together.

PolicyCodex runs as a single Docker container on a small VM you own. It commits to a private GitHub repo your diocese controls. The handbook publishes through GitHub Actions to a subdomain you point at GitHub Pages. No multi-tenant SaaS, no vendor lock-in, no licensing fees. The install path is documented in the Install section below.

### The parish or school staff member who reads the handbook

You need to know how long to keep baptismal records, what the diocesan policy on independent contractors says, or which form to use for a new safe-environment certification.

You bookmark the diocesan handbook subdomain. PolicyCodex gives you stable per-policy URLs, a changelog page so you can see what changed and when, and an RSS feed for the policies you care about.

## What It Does

1. **Ingests** policy documents from a local folder (v0.1). SharePoint and Google Drive connectors are planned for v0.2.
2. **Inventories** them with AI: proposes a category, owner, effective date, review cadence, retention period, and a chapter-section-item address for each policy. Each policy gets a companion audit file recording the AI's confidence per field plus the provider, model, token counts, and timestamp of the call, so the IT director can attribute API spend.
3. **Stores** every policy as a markdown file in a private GitHub repo your diocese owns. Every change is a commit. Every approval is a pull request review.
4. **Routes** each entry through a simple human approval workflow with three default gates (Drafted, Reviewed, Published) that map to pull request states.
5. **Publishes** approved policies as a static handbook site, built and deployed by GitHub Actions on every merge to a subdomain you control, with stable per-policy URLs.
6. **Stays out of the way** of your existing platforms. PolicyCodex does not replace SharePoint, Google Workspace, GitHub, or your CMS. It reads from your filesystems, helps you organize, commits to your repo, and emits a handbook.

## Why This Matters for Your Diocese

If you run a diocese, you probably know the pattern:

- Hundreds of policies scattered across SharePoint folders, shared drives, and filing cabinets.
- No consistent metadata. No owner, no effective date, no review cadence.
- No version history anyone trusts.
- No public handbook for parish or school staff to consult.
- An annual review cycle that gets mandated and never executed.
- Compliance frameworks (USCCB Charter, canon law, civil and state nonprofit law) that overlap in confusing ways.

PolicyCodex is the tool you would have built yourself if you had three more hours every week.

## Design Principles

**Opinionated by default. Configurable where dioceses have legitimate variation. AI-assisted throughout.**

- We default to the LA Archdiocese chapter-section-item numbering. We support a Catholic-healthcare-style department code convention as an alternative.
- We default to semantic versioning for individual policy documents (1.0 first published, 1.1 minor revision, 2.0 obligations changed).
- We require five metadata fields on every published policy: owner, effective date, last review, next review, retention period.
- We ground AI extraction in your existing documents. Point PolicyCodex at your Document Retention Policy and it uses your real retention schedule rather than guessing. Same pattern for any other canonical reference your diocese maintains.
- We default to Anthropic Claude as the LLM. We support OpenAI, Gemini, Azure OpenAI, and local Llama as alternates.
- We assume humans approve every published policy. AI proposes. Humans decide. Lawyers gonna lawyer.

## Architecture (for technical readers)

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
- **App** is the admin web interface. It commits to the diocese's GitHub repo, opens pull requests on user actions, and surfaces pull request state as gate state.
- **Publish** is a GitHub Actions workflow that builds and deploys the handbook on every merge.

Run PolicyCodex on a small VM. Connect it to your private GitHub repo. Point it at your filesystems. Configure your conventions through the Settings page. The handbook deploys to a subdomain you control.

## Install (for IT directors)

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

Both paths land you at the in-browser login. Sign in with the seeded `admin` / `admin1234` credentials and change the password on first login. The Settings page collects everything (GitHub App credentials, LLM API key, policy repo, diocese configuration, users and roles) and the Inventory page handles your policy documents. Configuration commits to your diocese repo as it lands.

To wipe an install and start over: `docker compose down -v && docker volume rm policycodex-data`.

### Before you begin

PolicyCodex needs **API access to a language model, not a consumer chat subscription.** The consumer plans (Claude Pro / Pro Max / Teams, ChatGPT Plus, Google One) have no programmatic access and will not work. Provision an API key before you configure the Settings AI provider panel:

- **Anthropic Claude** (default) — an Anthropic API key, not Claude Pro / Pro Max / Teams. The API is pre-paid and billed per token via console.anthropic.com.
- **OpenAI** — an OpenAI API key, not ChatGPT Plus.
- **Google Gemini** — a Gemini API key or Vertex AI credentials, not Google One.
- **Azure OpenAI** — Azure OpenAI deployment credentials (an Azure subscription with the OpenAI service deployed).
- **Local Llama** — no third-party key. Runs on your own VM.

The Settings AI provider panel links each provider's API-key docs and shows rough monthly cost ranges for typical diocese sizes.

### Rebuilding the CSS

The compiled stylesheet (`static/css/policycodex.css`) is pre-built and committed, so a plain install needs no toolchain. If you edit a template or a theme variable, regenerate it with `scripts/build-css.sh`. The script downloads the Tailwind standalone CLI and the DaisyUI plugins into the gitignored `.tools/` directory the first time you run it, so you need no Node install. Commit the regenerated `static/css/policycodex.css` alongside your template change.

## Roadmap

**v0.1 (released 2026-06-14):** ingest, AI inventory grounded in the diocese's own reference documents, pull-request-backed approval UI, GitHub Actions handbook publication, Settings-page configuration (admin account, GitHub App, AI provider, Policy repository, Diocese, Users-and-roles) plus a top-level Inventory page, published GHCR image.

**v0.2 (post-adopter signal):** Q&A chatbot over the published handbook, Google Drive and SharePoint connectors, compliance framework library expansion, email notifications for review cadence, rich-text edit mode for non-markdown editors, document-type substrate (Policy, Standard, Guideline, Process, SOP).

**Later:** full Seven-Gate workflow configurability, GitHub Enterprise / GitLab / Gitea support, regulatory change watching, multilingual handbook.

See [ROADMAP.md](ROADMAP.md) for the full living roadmap.

## How To Get Involved

**If you represent a diocese interested in being install partner number two:** email chuck@bricklauncher.com or open a discussion. The Diocese of Pensacola-Tallahassee is install zero; the next install is the conversation we are most interested in.

**If you are a CFO, Chancellor, or document control owner curious about whether this fits your workflow:** ask your IT director to clone the repo and stand up a local install. The Settings page guides them through configuration. Once it is up, the policy editing experience is yours.

**If you are a developer interested in contributing:** browse the source code and open a GitHub Issue describing what you want to work on. CONTRIBUTING.md will land before the first outside pull request to set expectations on review cadence and code style.

PolicyCodex is being built by a small group of coders with deep ties to the diocesan IT community. We welcome contributions, especially from people who actually run policy programs at dioceses, nonprofits, or healthcare systems.

## Acknowledgments

- The **Diocese of Pensacola-Tallahassee**, install zero and patient test subject.
- The **Archdiocese of Los Angeles**, whose [public handbook](https://handbook.la-archdiocese.org/) is the reference implementation we are designing toward, and **David Schmitt** (IT Director, Archdiocese of Los Angeles), reviewer.
- **Marcus Madsen** (Director of IT, Archdiocese of Baltimore), design reviewer.
- The **DISC** (Diocesan Information Systems Conference) community of diocesan IT directors.

## License

PolicyCodex is licensed under the **GNU Affero General Public License v3.0 (AGPL-3.0)**. See [LICENSE](LICENSE) for the full text.

AGPL-3.0 means you may run, modify, and redistribute PolicyCodex freely. If you offer it as a network service to anyone else, you must make your modified source available to those users. This protects the open-source maintainer model and keeps the project healthy for the dioceses installing it.

The maintainer earns through setup, support, and customization, not through license fees.
