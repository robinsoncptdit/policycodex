# PolicyCodex v0.2 Forward-Thinking Brainstorm

*Created 2026-06-08 during Week 5 polish. Working artifact, not spec-grade. Items mature here before they get promoted to canonical spec entries.*

## How to read this

The five items below came out of Chuck's prompt asking what life looks like past v0.1. Each section walks the problem, sketches the interaction, names architecture considerations, calls out risks, and lands on a recommendation. Architectural shells of the strongest items are filed in PRD P2.8 through P2.11 so v0.1 code does not paint anything into a corner.

This doc keeps the longer product reasoning, the rankings, and the "do not prioritize" notes that should not pollute the canonical spec.

## 1. CFO drafts a new policy with AI inside the app

### The opportunity

Today's AI does inventory of existing policies. The natural inverse is blank-canvas authoring. Different buyer pitch ("we help you write policies you don't have yet") and expands the user base beyond "people with hundreds of existing policies to clean up." A diocese launching a new safe-environment program, or adding a remote-work policy, or responding to a new USCCB norm all need the same thing: a drafted policy that follows their voice, fits their address scheme, classifies cleanly into their retention schedule, and references the right external standards.

### Interaction sketch

A "Draft a new policy" button on the catalog. Click opens an HTMX-driven chat panel. The CFO describes the policy in plain language:

> "I need a remote work policy for diocesan employees. Up to two days remote per week, supervisor approval required, exceptions documented."

The AI asks a few clarifying questions (does this apply to clergy as well? what categories of employee are excluded? are there technology requirements?). After two or three exchanges the AI proposes a complete markdown draft: title, frontmatter (suggested address, suggested classification, suggested owner role, retention pulled from the foundational bundle, suggested next review date), body sections (purpose, scope, definitions, requirements, exceptions, references), and a list of suggested cross-references to existing policies.

CFO reviews inline. Clicks Submit. PR opens. Normal Drafted → Reviewed → Published flow takes over.

### What the AI needs as grounding

- The diocese's foundational bundle (`policies/document-retention/data.yaml`) so classification and retention are correct.
- Existing published policies in the same proposed classification, so voice and structure match.
- The diocese's address scheme so the suggested address slots into the right chapter.
- A small library of standard policy elements (purpose, scope, definitions, requirements, exceptions, review cadence, references). Probably ships as a starter pack in the repo.

### Risks

The big one: hallucinated regulatory citations. AI confidently inventing "per IRS Publication 8472" when no such publication exists, or citing a USCCB norm that was superseded. Mitigation: every factual claim the AI generates carries a "needs verification" badge in the draft. Reviewer cannot Approve until every badge is cleared. The verification step is the gate.

Secondary risk: voice drift. AI defaults to legalese instead of the diocese's actual house style. Mitigation: ground on existing published policies in the same classification and explicitly instruct the model to match observed voice.

Tertiary risk: token cost. A chat-style interaction can blow through tokens fast. Bounded by the P2.11 monthly spend ceiling.

### Filed as

PRD **P2.8**. Architecturally compatible with the v0.1 PR-as-gate pattern and HTMX surface.

### Suggested v0.2 ticket scope (when work begins)

One M-sized ticket: `AI-20 Conversational policy authoring`. Reuses the existing provider abstraction, adds a new HTMX-driven chat surface, lands a verification-badge data model on the policy frontmatter that gates the Approve action.

## 2. Dump and re-ingest the whole corpus

### What admins actually mean when they ask for this

The phrase "dump and re-ingest" covers three quite different operations:

**Mode A: Refresh the unfinished work.** Re-extract only Drafted policies (no PR approval yet). Anything Reviewed or Published is untouched. The CFO's edits are safe. The reviewer's approvals are safe. Only the AI's first-pass suggestions get a second try. This is the right default. Common trigger: AI model upgrade, or the foundational bundle was significantly improved after first ingest.

**Mode B: Overwrite drafts including human edits, preserve approvals.** Re-extract Drafted policies even if a human has edited them, but stop at Reviewed. This requires a confirmation dialog ("you will lose 12 policies' worth of unsaved human edits"). Common trigger: classification scheme was redesigned and even the human-edited drafts need re-classification.

**Mode C: Nuke and start over.** Archive everything (including Published) to `policies/.archive/<timestamp>/` and re-run the inventory pass from scratch. Power-user CLI command, not a UI button. Recoverable via Git history so the archive itself is a belt-and-suspenders. Common trigger: catastrophic initial extraction, or PolicyCodex was misconfigured for the first install and the entire taxonomy needs to be redone.

### Architecture

v0.1's AI-10 inventory pass is already re-run safe at the slug level (existing slugs are skipped). The new work for v0.2 is:

- Read each policy's gate state from the local working copy (already exposed by APP-21's startup self-check and the catalog view).
- Add a re-ingest entry point that takes a mode (A/B/C).
- For mode A, restrict the inventory pass's input set to slugs that are Drafted only.
- For mode B, restrict to Drafted including human-edited (compare commit history to the bulk-import branch).
- For mode C, do the archive move first, then run a normal inventory pass into an empty `policies/` directory.

Every re-ingest writes a structured audit entry to `internal/reingest-log.md` in the policy repo: who triggered it, when, what mode, which slugs got replaced, which got preserved.

### Risk

Mode B and especially Mode C can destroy human work if the admin clicks the wrong thing. The double-confirmation dialog matters. The audit log matters more. Git history is the safety net of last resort.

### Filed as

PRD **P2.10**.

### Suggested v0.2 ticket scope

One M-sized ticket: `AI-21 Corpus re-ingest with gate-state preservation`. The CLI surface is straightforward. The UI surface (catalog → Settings → Re-ingest) needs careful confirmation UX. Mode C can ship as CLI-only initially and never get a UI button.

## 3. Re-extract a single policy

### Why this is cheaper than #2

Bounded blast radius. One policy. Easy to diff. Easy to roll back (just close the PR without merging). Common triggers are concrete and recurrent:

- Source PDF was replaced in the export folder (the CFO updated the original document outside PolicyCodex).
- AI's first extraction was poor for that one policy and the admin wants a second swing.
- Foundational policy changed (new classification added) and one policy needs re-derivation.
- The admin made human edits, decided they were wrong, and wants the AI baseline back to start over.

### Interaction sketch

A "Re-extract from source" affordance on the policy detail view. Click triggers an `/htmx/<slug>/re-extract` endpoint that:

1. Looks up the source manifest entry from INGEST-04's manifest model.
2. Runs single-policy extraction (`ai/inventory_extract.py`) against that source file.
3. Creates a `policycodex/re-extract-<slug>-<hex>` branch.
4. Writes the new policy.md.
5. Opens a PR. The PR body shows a clean diff between the current policy and the AI-re-proposed version.
6. Reviewer Approves or Closes. Normal flow.

### Architecture

The source-manifest back-reference already exists per INGEST-04. The single-policy extraction function already exists per `ai/inventory_extract.py`. The PR-as-gate flow already exists. The work is mostly wiring plus a new HTMX endpoint plus the diff render.

### Filed as

PRD **P2.9**.

### Suggested v0.2 ticket scope

One S-sized ticket: `APP-31 Targeted policy re-extraction`. Genuinely small. Could be the first v0.2 ticket someone picks up as a quick win.

## 4. Where AI really helps post-v0.2

### Top five by impact times feasibility

**Rank 1: Policy authoring chat (item 1 above).** Already covered. Strongest single bet because it expands the buyer pitch beyond inventory cleanup.

**Rank 2: Regulatory change watching.** PolicyCodex notices USCCB updated the Charter for the Protection of Children on a specific date, identifies the three diocesan policies that reference the prior version, drafts the updates, and opens PRs against each. The architecture skeleton is already filed as **PRD P2.5** ("every checklist in the framework library carries a last verified date and a source URL"). Hard to build well: requires a regulatory-change feed (USCCB, state nonprofit law, IRS, HIPAA where applicable), a per-policy cross-reference index, and a per-update draft engine. Unmatched by any competitor in the diocesan space if done well. Probably v0.3, not v0.2, because the data sources need work.

**Rank 3: Q&A chatbot over the handbook (RAG).** A parish secretary asks "how long do we keep baptismal records," gets the relevant policy plus the retention rule. PRD **P2.1** already says the handbook generator should emit a vector-friendly chunk format. Medium-effort v0.2 ticket: stand up an embedding index, expose a chat endpoint on the public handbook subdomain (or as an embed for parish web teams). High parish-staff value, modest engineering. The diocesan IT director sells this internally as "self-service handbook" and saves themselves help-desk tickets.

**Rank 4: Compliance checklist runs.** Extends the v0.1 gap-detection pattern (AI-13). "Run the IRS substantiation checklist against all donor-related policies. Three are missing required language." Connects to PRD **P1.1** (Compliance Framework Library). Genuinely useful for annual audit prep. The hard part is curating the checklists; the AI plumbing is easy.

**Rank 5: Translation.** Spanish handbook for Hispanic ministries is a real and underserved diocesan need. PRD **P2.6** already names the architecture (additional markdown per language, sharing frontmatter). v0.2 ticket: AI-drafted translation, human-reviewed before publish, ships through the same PR gate. Pitch lands well at DISC; Hispanic ministry is on every IT director's mind.

### Lower-ranked but worth keeping for v0.2/v0.3 consideration

- **Voice-of-the-diocese consistency.** "This new policy reads differently from your published voice. Want me to revise for tone?" Cheap to add as a lint step on top of the policy authoring chat. Probably a v0.2.5 polish.
- **Stale policy detection beyond next-review-date.** Already get notifications via P1.4. AI extension: "Policy X has not been reviewed in five years AND the underlying regulation has changed three times since then. Here's a draft refresh." Combines with regulatory change watching.
- **Audit prep extraction.** "Pull every policy that references PCI-DSS for our annual audit." Search plus extract. Easy if the handbook RAG index exists.
- **AI-assisted onboarding wizard 2.0.** The v0.1 wizard already has AI suggest buttons. Push further: from the uploaded retention PDF, pre-fill more of the seven screens (suggested address scheme based on document structure, suggested reviewer roles based on document signatories). Cuts onboarding time in half.
- **Reviewer assistance.** Already prototyped in the v0.1 mockups (AI summary card on the reviewer screen). Extend with "show me the diff in plain English" or "what other policies does this change affect."

### Do NOT prioritize

**Cross-diocese knowledge transfer.** "The Diocese of X just published a great social media policy. Want me to adapt it for your context?" Sounds clever. Politically sensitive (requires consent), legally fraught (public-handbook scraping invites license arguments), and easy to do badly. The first diocese that complains "PolicyCodex stole our policy" damages the entire maintainer-mode trust story. Skip.

**Auto-publishing of AI drafts.** The temptation will arise: "the AI is good enough, let it merge low-risk changes without a human reviewer." Never. Every PolicyCodex policy carries the diocese's institutional weight; auto-publish breaks the audit-trail guarantee that PRD G3 makes. Hard line.

**Multi-LLM consensus reviews.** Already rejected in v0.1 ("overbuilt for the problem; one model plus a sharp rubric plus a human approver wins"). The reasoning does not change at v0.2 scale.

## 6. Document owner uploads a new policy (overlap detection, merge/replace/parallel resolution)

*Added 2026-06-08 from Chuck's question about post-wizard policy upload flow. Inserted in file order before section 5 due to edit anchor; read in numerical order.*

### Current gap

v0.1 has two ingest paths: wizard screen 7 (retention PDF, foundational bundle) and the bulk inventory pass (CLI against a local folder). Neither serves the non-technical document owner. A CFO who finishes a new policy in Word has no obvious next move. They can drop the file in a watched folder, wait for the next bulk pass, and hope. That is a real gap for the CFO / HR Director / Document Control Owner personas.

### Desired flow

1. Document owner clicks "Add policy" on the catalog.
2. Drops a file (PDF, DOCX, MD, TXT) or pastes text.
3. PolicyCodex runs the same per-policy extractor that AI-10's inventory pass uses (`ai/inventory_extract.py`), grounded in the foundational bundle.
4. Overlap check fires against existing policies.
5. Proposed policy renders in the edit form with AI-suggested metadata pre-filled and any overlap warnings surfaced.
6. Document owner reviews, edits, submits.
7. Submission opens a per-policy PR on `policycodex/new-<slug>-<hex>`. Normal Drafted / Reviewed / Published gates apply.

### Overlap detection

Today's collision check is name-based only. AI-10 skips slugs that already exist. It cannot detect that "Whistleblower Reporting Policy" overlaps semantically with the existing "Diocesan Whistleblower" because their slugs differ.

Semantic overlap detection needs an embedding index over existing policies. Architecturally compatible with PRD P2.1 (Q&A chatbot RAG over the handbook): the handbook generator already needs to emit a vector-friendly chunk format. The same index that powers RAG search powers overlap detection on upload. One investment, two payoffs.

Three similarity buckets to tune during v0.2 against a real corpus:

- High similarity (>0.85): probable duplicate. Recommend merge or replace.
- Medium similarity (0.65 to 0.85): probable supplement. Recommend "create as new" with a "see also" cross-reference.
- Low similarity (<0.65): probably distinct. Proceed as new policy without nagging.

### Resolution when overlap detected

Three explicit choices, AI-recommended defaults, user decides.

**Merge.** Combine new and existing into one updated policy. AI generates a unified draft preserving substantive language from both. PR opens against the EXISTING slug, which preserves the handbook URL. Old version lives in Git history.

**Replace.** New supersedes old. AI marks the old policy `deprecated: true` in frontmatter. New policy gets its own slug. The handbook shows "This policy supersedes 3.1.7" on the new entry and "Superseded by 3.1.20" on the deprecated. One PR with both changes.

**Create as parallel.** AI was overeager about overlap. The new policy is distinct. PR opens as a fresh policy. The "see also" cross-reference still gets added if useful.

### Address stability (push back on default renumbering)

Address strings are URLs in the handbook. Parishioners and clergy link directly to them. Bookmarks and printed materials carry them. Renumbering breaks those links. The default policy is to keep addresses stable through overlap resolution:

- Merge keeps the existing address.
- Replace gets a new address, and the OLD address still resolves (to the new policy or a "superseded" stub).
- Create as parallel gets the next available address in the appropriate chapter.

Whole-taxonomy renumbering (a diocese reorganizing their entire chapter structure) is a separate concern, probably tooled differently. Reserve for v0.3+ if ever, not part of the normal upload flow.

### Risks

**False positive fatigue.** Overlap detection that calls a possible match on every upload trains users to dismiss the warning, and then a real overlap slips through. Threshold tuning matters more than the algorithm. Err toward false negatives, not false positives.

**Per-diocese tuning.** Some dioceses have homogeneous corpora (lots of similar safe-environment policies copied across departments) and need a higher threshold. Some have heterogeneous corpora. Threshold should be configurable per install, not a global constant.

**Embedding cost.** Every upload does N similarity lookups. With an indexed vector store, cheap. Without one, expensive. Pays for itself once P2.1 (RAG) lands the same infrastructure.

### Filed as

PRD **P2.12** (architectural shell, one entry covering upload + overlap + resolution). This brainstorm section (longer reasoning).

### Suggested v0.2 ticket scope

Probably three M-sized tickets:

- `APP-XX New-policy upload UI`. The "Add policy" button, file or text input, opens PR through normal flow.
- `AI-XX Embedding index over existing policies`. Foundation for P2.1 RAG too.
- `AI-XX Overlap detection + resolution flow`. Similarity check, three-way choice, AI-recommended default.

### The v0.1 scope question

A stripped-down version (just the "Add policy" button, manual entry only, no AI extraction, no overlap detection) could ship in v0.1 if polish-week budget allows. Drops user into the existing edit form with empty fields. Manual fill-in, PR through normal flow.

Tradeoff: ships the user surface without AI work. Lower wow factor but real workflow value. PM recommendation as of 2026-06-08: skip even the manual button in v0.1 because APP-28 (L), APP-29, APP-30, APP-31, AI-16 are already filling the polish-week budget. CFO use case is real but workaround holds (IT director commits markdown, or drop in watched folder for bulk pass). Re-raise if budget loosens.

## 5. Claude licensing and AI provider operations in production

### The confusion you have to head off at DISC

Diocesan IT directors arrive at DISC having used claude.ai through a Pro subscription, a Pro Max subscription, or a Teams subscription. They will assume that subscription works with PolicyCodex. It does not. The consumer claude.ai products are interactive surfaces for humans typing into a chat box. They do not include programmatic access. An app like PolicyCodex cannot call them.

What PolicyCodex actually needs is Anthropic API access. Separate product, separate pricing model, separate signup flow.

### How the diocese gets set up

1. Diocesan IT director creates an Anthropic API account at console.anthropic.com (different from claude.ai).
2. Generates an API key. Funds a small credit balance (Anthropic API is pre-paid, pay-per-token).
3. Enters the API key during PolicyCodex wizard step 6.
4. PolicyCodex makes calls to api.anthropic.com on their behalf. Each call is logged in the per-policy `.audit.yaml` sidecar.
5. Their Anthropic API usage shows up in console.anthropic.com under their billing account.

### Cost expectations to put in the docs

For a typical diocese:

- **Initial inventory of ~200 policies:** one-time burst, roughly $5 to $20 in API calls depending on policy length and chosen model tier.
- **Ongoing edits and AI suggestions:** pennies per operation.
- **Conversational drafting (P2.8 chat):** cents per draft conversation.
- **Q&A over the handbook (P2.1 RAG):** cents per question, with RAG retrieval minimizing context tokens.
- **Total monthly steady state:** $5 to $50 for an average diocese. Negligible relative to operational value.

These numbers will move with model pricing and should be re-validated annually.

### Provider abstraction extends the same explanation

Same principle for every provider PolicyCodex supports:

- **OpenAI:** API key required, not ChatGPT Plus. Pay-per-token at platform.openai.com.
- **Gemini:** Gemini API key or Vertex AI service-account credentials. Not Google One subscription.
- **Azure OpenAI:** Azure subscription with OpenAI service deployed. Per-token pricing through Azure billing.
- **Local Llama:** No third-party key. Runs on the diocese's own VM with whatever GPU or CPU they have. Zero per-call cost but slower and quality varies by model size. Strongest data-sovereignty story.

### What this implies for the v0.1 / v0.2 work

**v0.1 (pulled forward 2026-06-08, filed as polish-week tickets):**

- **APP-31** (S, Week 5): Wizard step 6 prose changes naming the API-key vs consumer-subscription distinction for each provider (Anthropic, OpenAI, Gemini, Azure, local Llama), direct links to each provider's API-key documentation, expected-monthly-cost table for small / mid / large diocese sizes, and a "Before you begin" subsection in the public `README.md` install section so IT directors hit the wizard already provisioned.
- **AI-16** (S, Week 5): Audit-sidecar extension. Every AI call records provider name, model identifier, input token count, output token count, and call timestamp alongside the existing confidence values in the per-policy `.audit.yaml`. Useful at v0.1 for cost-attribution debugging if a diocese sees unexpected API spend, and the foundation for v0.2 spend ceilings.

**v0.2:** Filed as PRD **P2.11** for the remainder. Optional monthly spend ceiling enforced at the provider abstraction layer, with the wizard collecting the ceiling at step 6 and PolicyCodex refusing to call once exhausted. Wizard step 6 grows a "test connection" button that does a one-token round-trip to validate the key before the wizard completes.

### A hosted-AI tier conversation worth deferring

Someday the maintainer (you) could offer "we run the AI for you and pass through API costs plus a small margin" as a paid setup tier. This collides with the single-tenant self-hosted v0.1 model and introduces a billing relationship that the maintainer-mode pitch deliberately avoids. v0.3+ conversation if at all, and probably never. The cleaner pitch is "use your own API key, we charge for setup and customization." Keeps the operational story simple and the trust story clean.

## How the v0.2 cycle starts

Per Chuck (2026-06-08): the v0.2 spec and ticket markdown files get drafted here in Claude Cowork via the Product Management plugin, mirroring the v0.1 origin pattern. The trigger is finishing v0.1 plus securing buy-in from other dioceses or contributing partners. This brainstorm doc seeds that conversation: P2.8 through P2.11 in the v0.1 PRD already carry the architectural shells, and the rank-1-through-5 list in item 4 above gives the prioritization framework. When the v0.2 cycle opens, the natural first move is a fresh PM brainstorm against the actual feedback signal coming in from real dioceses post-DISC, with this doc as the running-start input.

**Before any v0.2 design work begins, walk `internal/PolicyCodex-v0.1-Closeout-Checklist.md` top to bottom.** That checklist captures the cleanup that transitions the project from v0.1 sprint mode to v0.2 design mode, including the CLAUDE.md compression pass (REPO-13) that frees up context for v0.2 thinking.

## Open questions for v0.2 planning

- **What triggers a v0.2 sprint?** Hard date (DISC Q1 2027?) or pull-based (when N dioceses have installed v0.1 and the pattern of feature requests is visible)?
- **How do P2 items get prioritized into v0.2?** First-come-first-served from the issue tracker, or curated against a v0.2 roadmap that ships before any work starts?
- **Who is the v0.2 design partner?** PT is install zero for v0.1. Does PT carry forward, or does LA become primary, or does whichever diocese installs second drive the next round?
- **What is the v0.2 success metric?** Repo clones and install counts are v0.1 metrics. v0.2 needs adoption/engagement metrics that justify shipping the next round of work.
- **Does the maintainer model still hold past v0.2?** As features grow, the support burden grows. At some point either pricing changes (paid hosted tier, paid premium features under dual-license) or the open-source ceiling becomes visible. Worth having the conversation before it forces itself.

## What got filed in the spec vs. what stays here

Promoted to PRD P2.X entries (architectural notes only, brief):

| PRD | Topic |
|---|---|
| P2.8 | AI-assisted policy authoring |
| P2.9 | Targeted policy re-extraction |
| P2.10 | Bulk corpus re-ingest with gate-state preservation |
| P2.11 | AI provider key management, cost controls, and audit logging |

Stays in this brainstorm doc until matured:

- Full ranking of post-v0.2 AI opportunities (the rank-1-through-5 list above and the lower-ranked items)
- "Do not prioritize" notes (cross-diocese knowledge transfer, auto-publishing, multi-LLM consensus)
- Cost expectation framing for the diocesan IT director's setup conversation
- The hosted-AI tier question
- Open questions for v0.2 sprint planning

Existing P2 entries that already cover items raised here:

| PRD | Topic | This brainstorm relates to |
|---|---|---|
| P2.1 | Q&A Chatbot (RAG) | Rank 3 in item 4 |
| P2.5 | Regulatory Change Watching | Rank 2 in item 4 |
| P2.6 | Multilingual Handbook | Rank 5 in item 4 (translation) |
| P1.1 | Compliance Framework Library | Rank 4 in item 4 (checklist runs) |
| P1.4 | Email Notifications | Lower-ranked stale-policy detection |
