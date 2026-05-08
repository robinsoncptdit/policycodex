# PolicyWonk: Project Summary

*Working name. The spirit, not the spec.*

## The Idea

A tool that helps Catholic dioceses (and similar mission-driven institutions) manage the full lifecycle of their governing documents. Inventory them. Review them. Update them. Approve them through proper governance. Publish them. Keep them current. Make them findable for the staff who need to apply them.

## Why It Matters

Most dioceses have hundreds of policies scattered across Google Workspace or SharePoint folders, shared drives, and filing cabinets. Annual review cycles get mandated but rarely executed. Compliance frameworks (canon law, civil law, USCCB Charter, state nonprofit law) overlap in confusing ways. Front-line staff cannot find the right policy when they need it. AI is finally good enough to make this affordable for a single diocese to run on its own.

## Who Could Use This

- Catholic dioceses (the original target, around 175 in the US)
- Religious orders managing their own governance documents
- Other mission-driven nonprofits with heavy governance load (hospitals, universities, large charities)
- Any organization with hundreds of policies and a lean back-office team

## The Original Concept (Quick Recap)

A SaaS app driving documents through a Seven-Gate workflow: Inventory, SME Review, Standing Policy Committee, Legal, Executive, Board, Publication and Training. AI assists at each gate (gap analysis, readability, compliance checks, drafting, committee routing, board packets, training content). The 2024 stack converged on Dify.ai for orchestration, MCP plugins for tools, and multi-LLM consensus across Claude, GPT-4, and Gemini. SharePoint held the documents. The plan optimized for one diocese on a 12-week summer deadline.

The Seven-Gate workflow itself, the stakeholder map, and the AI placement at each gate were sound. The platform choices and the consensus pattern were of their moment.

## The Reframe

The deadline is gone. The instinct now is to open this up so other dioceses can use it (free, open source, or commercial is undecided). Several pieces of the original tech stack look overbuilt or out of date:

- Multi-LLM consensus is mostly insurance theater. One strong model with a sharp rubric and a human approver beats three models voting.
- Custom Python MCP servers can be replaced by skills (markdown plus reference docs).
- Dify as orchestration is no longer the obvious choice. Native MCP across Claude, the Claude Agent SDK, and Cowork mode all reduce the need for a middleware layer.
- The highest-value feature is probably "ask the policies a question," not the workflow engine.
- The compliance frameworks themselves are the moat, not the orchestration.

## What I Actually Want to Build (The Spirit)

Give every diocese the policy program of a Fortune 500 legal department, for the cost of a small subscription (or free).

The product should:

- Help a small back-office team inventory and clean up an existing pile of governance documents
- Run those documents through a credible review and approval process with the right humans in the right seats
- Make every approved policy instantly findable and queryable by parish and school staff
- Watch for regulatory changes and flag policies that need a fresh look
- Stay cheap enough that a single diocese can justify it without a board fight

## Open Questions for Brainstorming

- Open source, commercial, or hybrid? Who pays, and for what?
- Single-tenant install per diocese, or multi-tenant SaaS?
- Is the wedge product the workflow engine, the policy Q&A chatbot, the compliance framework library, or the inventory cleanup tool?
- Who is the actual buyer? COO, IT director, General Counsel, Chancellor, or the Bishop's office?
- Does the product stay diocese-flavored, or generalize to all mission-driven nonprofits?
- What is the smallest version that delivers obvious value in 30 days?
- How do we allow the customer to decide which filesystems and which LLMs to use?

## Out of Scope For Now

- Specific tech stack debates
- Pricing
- Brand and naming
- Whether the workflow stays at exactly seven gates (some dioceses will want fewer, some more)
