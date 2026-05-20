## Scope

PolicyCodex goes public at DISC in roughly four weeks. The audience is diocesan IT directors and adjacent buyers (Catholic universities, Catholic healthcare). The competitive question is: when a buyer hears PolicyCodex's pitch, what are they comparing it against, and what should you say? This brief covers the five comparators you will actually face: PowerDMS, Microsoft 365 Copilot plus SharePoint, Confluence, Notion, and the "build it ourselves on SharePoint plus Power Automate" option. Status quo ("do nothing") is the implicit sixth and the one most dioceses are actually doing today.

## Competitor overviews

**PowerDMS / NAVEX One.** The dominant purpose-built policy lifecycle vendor. Strong in police departments, government, and healthcare (used by Catholic healthcare systems like Ascension and CommonSpirit affiliates). Enterprise pricing in the $10k to $50k/year range depending on user count. Full lifecycle workflow, accreditation tools, attestation/acknowledgment tracking. Closed source, hosted SaaS, sales-led GTM.

**Microsoft 365 Copilot plus SharePoint.** Every diocese already has SharePoint and most have Microsoft 365. Copilot adds AI search and summarization on top of stored documents. Roughly $30/user/month for Copilot on top of M365 licenses. Strength: zero new install, already trusted by the IT director, fits inside the existing data tenant. Weakness: no policy-specific metadata model, no lifecycle workflow, no public handbook output, no audit trail at the per-policy level.

**Confluence (Atlassian).** Mature knowledge-base platform. Some large dioceses and Catholic universities use it as a policy repository. Around $6 to $11 per user/month for the standard plan, more for enterprise. Strength: page-level permissions, version history, mature ecosystem. Weakness: scales badly for unlimited-user diocesan staff, no policy-specific metadata, no Git audit, no AI inventory, hosted-only or expensive Data Center.

**Notion.** Modern docs and wiki platform. Some Catholic nonprofits use it. Around $8 to $15 per user/month for teams. Strength: friendly UI, Notion AI for retrieval and drafting. Weakness: no governance rigor, page-level permissions get unwieldy at diocese scale, no audit trail strong enough for legal review, no public handbook subdomain story.

**Build-your-own (SharePoint plus Power Automate plus custom forms).** What a competent diocesan IT director might assemble. Free in software cost, expensive in maintenance and onboarding burden. Strength: matches existing tooling, total IT control, customizable. Weakness: maintenance burden falls on a one-person IT team, no community, no AI assist, every diocese reinvents the wheel.

**Do nothing.** The actual status quo for most dioceses. Policies live in scattered SharePoint folders. Annual review gets mandated and rarely executed. No public handbook. No metadata. This is the real competitor for the wedge.

## Feature comparison

|Capability|PolicyCodex v0.1|PowerDMS|M365 + Copilot|Confluence|Notion|Build-your-own|Do nothing|
|---|---|---|---|---|---|---|---|
|Catholic-diocese aware|Strong|Absent|Absent|Absent|Absent|Custom|Absent|
|AI inventory + categorization|Strong|Weak|Adequate|Weak|Adequate|Absent|Absent|
|Required metadata enforcement|Strong|Strong|Absent|Weak|Weak|Custom|Absent|
|PR-as-gate audit trail|Strong|Strong|Absent|Weak|Weak|Custom|Absent|
|Public handbook subdomain|Strong|Weak|Absent|Adequate|Adequate|Custom|Absent|
|Source-of-truth grounding for AI|Strong|Absent|Absent|Absent|Absent|Absent|Absent|
|Self-hosted VM option|Strong|Absent|n/a|Adequate|Absent|Strong|n/a|
|Open-source (AGPL)|Strong|Absent|Absent|Absent|Absent|n/a|n/a|
|Attestation / acknowledgment|Future (v0.2)|Strong|Weak|Adequate|Weak|Custom|Absent|
|Per-seat cost at scale|Free|Enterprise|$30/user Copilot|$6-11/user|$8-15/user|Free|Free|
|Setup effort|Half day|Weeks|Hours|Hours|Hours|Months|None|
|Diocese already runs it|No (new)|No|Yes|Sometimes|Sometimes|Partially|Yes|

## Positioning analysis

PolicyCodex occupies a position no incumbent owns: **Catholic-diocese-specific, AI-assisted, AGPL open source, Git-backed, with services-revenue rather than per-seat licensing.** Every other option in the market is some combination of generic, enterprise-priced, hosted-only, or DIY.

The two competitors PolicyCodex must beat on different axes:

- **Against PowerDMS:** beat on price, openness, and Catholic fit. PowerDMS does lifecycle better today (acknowledgments, accreditation) but costs an order of magnitude more and treats Catholic dioceses as one vertical among many.
- **Against M365 plus Copilot (the real default):** beat on actually solving the policy problem. Copilot is great at search and summarization; it does not enforce metadata, run a review workflow, or publish a handbook. The IT director who tries to "just use Copilot" hits a wall on day three.
- **Against Notion and Confluence:** beat on per-seat economics and audit-trail rigor. Both are knowledge bases pressed into service as policy repos. They scale badly to unlimited diocesan staff.
- **Against build-your-own:** beat on time and community. A competent IT director can assemble a workflow. None has time, and none gets the AI inventory or the public handbook for free.
- **Against do nothing:** beat on obvious value within 30 days. The handbook subdomain going live is the thing that makes "do nothing" feel embarrassing.

## Strengths and weaknesses

**PolicyCodex strengths:** Catholic-aware out of the box. AGPL plus services-revenue model fits diocese budgets. Git-backed gives bulletproof audit trail. AI inventory grounded in the diocese's own retention policy (validated at 70.9% acceptance, projected 85%+ after AI-12). Subdomain handbook as a first-class output. Maintainer-mode means the project lives on a diocese's GitHub even if the maintainer goes quiet.

**PolicyCodex weaknesses today:** New, with no public reference customers beyond PT at DISC. Publish lane still thin (1 of 7 tickets merged). No acknowledgment/training tracking until v0.2. No mobile UI. Maintainer is a small team. Trademark filed nowhere yet.

**PowerDMS strengths:** Mature lifecycle. Acknowledgment tracking. Accreditation tooling. Established sales motion. Some Catholic healthcare adoption.

**PowerDMS weaknesses:** Enterprise pricing kills it for small to mid-size dioceses. Not Catholic-aware. Closed source means no diocese can audit the code touching their policies. Hosted SaaS means policies leave the diocese's tenant.

**Microsoft 365 plus Copilot strengths:** Already paid for. IT director already knows it. Lives in the same tenant as everything else. Copilot is a credible search and summarization layer.

**Microsoft 365 plus Copilot weaknesses:** No policy-specific anything. Copilot answers questions; it does not run a workflow, enforce metadata, or produce a handbook. Adding governance is a custom-build problem that lands on the IT director's plate.

**Confluence and Notion strengths:** Mature, friendly UI, fast to start. Existing user adoption in some Catholic universities.

**Confluence and Notion weaknesses:** Per-seat cost explodes when unlimited diocesan staff need read access. Audit-trail rigor insufficient for legal review. No policy-specific data model.

## Opportunities

- **Catholic identity is unclaimed.** No competitor markets to dioceses by name. The DISC audience will notice.
- **Per-seat pricing is broken for diocese economics.** A diocese of 5,000 employees plus 50,000 parishioners cannot afford per-user licensing on a knowledge tool. AGPL plus services is the right shape.
- **Audit trail backed by Git is uniquely defensible.** No competitor offers signed-commit-level provenance on every policy change.
- **The published handbook subdomain is a viral surface.** Parishioners who use the LA handbook become aware of "this diocese has its act together." That is marketing other dioceses notice.
- **Foundational-policy bundle pattern is a moat.** Treating the retention policy as both a document and a data file is novel and grounds the AI in something the diocese already trusts.

## Threats

- **Microsoft adds policy templates to Copilot for Office.** If Microsoft ships a "Policy Hub" feature that wraps SharePoint with workflow plus AI in the next 12 to 18 months, the addressable market for PolicyCodex narrows to dioceses that explicitly want self-hosted open source. Likelihood: medium.
- **PowerDMS adds Catholic-specific configuration and discounts.** They have the salespeople and the lifecycle features. If they decide dioceses are a vertical worth pursuing, they can move faster than a maintainer-mode project. Likelihood: low to medium.
- **A Catholic-flavored vendor (ParishSOFT, eCatholic, Realm) bundles a policy tool into their suite.** Cross-sell into existing customers. Likelihood: low for v1.0, rising over time.
- **AGPL scares an enterprise-flavored diocese off.** A General Counsel who reads "AGPL" and assumes worst-case obligations may block adoption. Likelihood: low and addressable through README explanation.
- **GitHub or GitLab launches a "policy" template that absorbs the wedge.** Less direct but possible. Likelihood: low.

## Strategic implications

1. **Lead with the Catholic-aware story at DISC, not the architecture story.** The audience cares that you understand diocesan governance. The Git-backed architecture is the proof, not the pitch.
2. **Show the published handbook subdomain in the first 60 seconds of the demo.** That is the artifact every diocese wants and no competitor delivers without a custom build.
3. **Name PowerDMS and Microsoft Copilot explicitly in the README's "Why not just use X" section.** Pre-empt the comparison. Make the trade-offs visible.
4. **Add acknowledgment tracking to the v0.2 roadmap publicly.** PowerDMS owns this today. v0.2 closes the gap before anyone forks.
5. **Land a second install before DISC if at all possible.** Anything that lets the slides say "deployed at two dioceses" beats "PT plus the LA review board" on credibility.
6. **Avoid talking about Catholic identity as exclusionary.** The same code base can serve Catholic universities, Catholic healthcare, religious orders, and adjacent nonprofits. Keep the door open.

## DISC battle cards

- "We use SharePoint already." Yes, keep using it. PolicyCodex reads from SharePoint exports and emits a versioned handbook. We do not replace your filesystem. We make your filesystem visible.
- "What about PowerDMS?" PowerDMS is excellent for accreditation-heavy healthcare. For a diocese on a tighter budget who wants self-hosted, open-source, and Catholic-aware, PolicyCodex is the cheaper fit. Acknowledgments come in v0.2.
- "Copilot can already search our policies." Search is not lifecycle. Copilot does not enforce that every policy has an owner, an effective date, and a review schedule. It does not produce a handbook. It does not maintain an audit trail you can show a lawyer.
- "Why open source?" So your diocese can audit the code touching your policies. So no vendor can hold your data hostage. So another diocese's IT director can fix a bug and you benefit. Services revenue (setup, support, customization) funds the work.
- "Why Catholic-aware?" Because canon law, USCCB Charter, and diocesan governance norms are real constraints PolicyCodex respects by default. Generic tools force you to bolt them on.

## What to monitor

- **Microsoft Copilot for Office updates** focused on workflow, content governance, or templated apps. Quarterly check on Microsoft 365 roadmap.
- **PowerDMS marketing toward Catholic vertical** specifically. Check their blog and case studies twice a year.
- **DISC community feedback** post-demo. Where do attendees push back? What do they ask for that you do not have? That is your v0.2 prioritization input.
- **ParishSOFT, eCatholic, Realm Connect, and similar Catholic SaaS** product roadmaps for any "documents" or "policies" module.
- **GitHub or GitLab templates** for nonprofit policy management. Niche today, could grow.
- **State and federal regulatory changes** affecting Catholic nonprofit governance (records retention law, audit standards). Each one creates a moment where dioceses ask "are our policies up to date?"

Brief stands as of May 16, 2026. Pricing references are approximate and worth a quick verification before any sales conversation. Re-baseline after DISC reveals which competitors actually come up in conversation.