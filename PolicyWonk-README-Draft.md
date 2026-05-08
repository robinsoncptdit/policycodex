# PolicyWonk

*A policy lifecycle tool for Catholic dioceses (and other mission-driven institutions with too many governance documents and not enough hours).*

PolicyWonk takes the pile of policies, procedures, and by-laws scattered across your SharePoint and Google Drive, helps you inventory and clean them up with AI assist, runs every change through a pull-request-backed approval workflow, and publishes a versioned, searchable handbook on a subdomain you control.

## Status

Pre-alpha. Active development for a public demo at DISC mid-June 2026. Diocese zero is the Diocese of Pensacola-Tallahassee. Design reviewed by the Archdiocese of Los Angeles.

If you are a diocesan IT director and you want to be install number two, please open a discussion or reach out.

## What This Solves

If you run technology for a diocese, you probably know the pattern:

- Hundreds of policies scattered across SharePoint folders, shared drives, and filing cabinets
- No consistent metadata (no owner, no effective date, no review cadence)
- No version history anyone trusts
- No public handbook for parish or school staff to consult
- An annual review cycle that gets mandated and never executed
- Compliance frameworks (USCCB Charter, canon law, civil and state nonprofit law) that overlap in confusing ways

PolicyWonk is the tool you would have built yourself if you had three more hours every week.

## What It Does

1. **Ingests** policy documents from SharePoint, Google Drive, or a local folder.
2. **Inventories** them with AI: proposes a category, owner, effective date, review cadence, retention period, and a chapter-section-item address for each policy.
3. **Stores** every policy as a markdown file in a private GitHub repo your diocese owns. Every change is a commit. Every approval is a pull request review.
4. **Routes** each entry through a simple human approval workflow with three default gates (Drafted, Reviewed, Published) that map to PR states.
5. **Publishes** approved policies as a static handbook site, built by GitHub Actions on every merge, with stable URLs, a changelog from `git log`, and an RSS feed.
6. **Stays out of the way** of your existing platforms. PolicyWonk does not replace SharePoint, Google Workspace, GitHub, or your CMS. It reads from your filesystems, helps you organize, commits to your repo, and emits a handbook.

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
- We ground AI extraction in your existing documents. Point PolicyWonk at your Document Retention Policy and it uses your real retention schedule rather than guessing. Same pattern for any other canonical reference your diocese maintains.
- We default to Claude as the LLM. We support OpenAI, Gemini, Azure OpenAI, and local Llama as alternates.
- We assume humans approve every published policy. AI proposes. Humans decide. Lawyers gonna lawyer.

## Architecture

PolicyWonk is **Git-backed**. Every diocese running PolicyWonk gets a private GitHub repo where its policies live as markdown files with YAML front matter. Version control, audit, branch-protected approvals, backups, and CI/CD are handled by GitHub. PolicyWonk is the friendly layer on top.

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

- **Ingest** reads source documents from SharePoint, Google Drive, or local folders.
- **AI** runs the inventory pass via a model-agnostic provider interface and emits markdown plus YAML front matter.
- **App** is the admin web interface. It commits to the diocese's GitHub repo, opens PRs on user actions, and surfaces PR state as gate state.
- **Publish** is a GitHub Actions workflow that builds and deploys the handbook on every merge.

Run PolicyWonk on a small VM. Connect it to your private GitHub repo. Point it at your filesystems. Configure your conventions through the onboarding wizard. The handbook deploys to a subdomain you control.

## Quick Start

```bash
# Clone the repo
git clone https://github.com/<org>/policywonk.git
cd policywonk

# Configure
cp .env.example .env
# edit .env with your filesystem credentials and chosen LLM provider

# Run
docker compose up -d
```

Open `http://localhost:8080` and complete the seven-screen onboarding wizard:

1. Connect or create a private GitHub repo for your policies (PolicyWonk uses a GitHub App)
2. Pick an address scheme (LA chapter-section-item or Catholic healthcare department code)
3. Pick a versioning convention (semver default)
4. Set reviewer roles and required approvers (writes branch protection rules)
5. Set retention defaults
6. Pick an LLM provider (Claude default)
7. Point PolicyWonk at any source-of-truth reference documents you already have (Document Retention Policy, by-laws, etc.). The AI extractor uses them as ground truth rather than guessing.

Full installation guide: [docs/install.md](docs/install.md).

## Roadmap

**v0.1 (June 2026):** ingest, AI inventory grounded in the diocese's own reference documents, PR-backed approval UI, GitHub Actions handbook publication, seven-screen onboarding wizard, public PolicyWonk repo.

**v0.2 (post-DISC):** Q&A chatbot over the published handbook (RAG), Google Drive parity, compliance framework library expansion, email notifications for review cadence, rich-text edit mode for non-markdown editors.

**Later:** full Seven-Gate workflow configurability, GitHub Enterprise / GitLab / Gitea support, multi-tenant hosting, regulatory change watching, multilingual handbook.

## Contributing

PolicyWonk is being built by a small group of coders with deep ties to the diocesan IT community. We welcome contributions, especially from people who actually run policy programs at dioceses, nonprofits, or healthcare systems.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the contribution flow and a clear statement of the configurable-vs-opinionated split. Read it before proposing changes that conflict with the core philosophy.

## Acknowledgments

- The **Diocese of Pensacola-Tallahassee**, install zero and patient test subject.
- The **Archdiocese of Los Angeles**, whose [public handbook](https://handbook.la-archdiocese.org/) is the reference implementation we are designing toward.
- The **DISC** (Diocesan Information Systems Conference) community of diocesan IT directors.

## License

License decision pending (MIT vs. Apache 2.0 vs. AGPL). See `LICENSE` once chosen.
