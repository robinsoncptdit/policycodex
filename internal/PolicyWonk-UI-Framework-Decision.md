# PolicyCodex UI Framework Decision (OQ-13)

*Resolved 2026-06-05 in Week 5 polish. Tracks the PM brainstorm and three guard rails landed alongside the resolution.*

## Resolution

**Tailwind CSS + DaisyUI + HTMX**, Inter typeface, brand color set via DaisyUI CSS variables. Production build via the Tailwind standalone CLI (a single static binary, no Node toolchain). Three guard rails added to keep options open for a future frontend swap:

1. New PRD section: **Frontend Portability Constraints**.
2. New PRD Licensing subsection: **Frontend Dependencies and AGPL Compatibility**.
3. New ticket **APP-27** to formalize the `/htmx/` URL prefix convention and to land the views-stay-thin note in `CLAUDE.md`.

Mockup comparison preserved in `internal/mockups/disc-demo-pico.html`, `disc-demo-bootstrap.html`, and `disc-demo-tailwind.html`. Open all three at the same viewport size to see the visual delta.

## Why this came up

Week 5 polish opened with REPO-10 (generic-ship audit) closing and Chuck asking whether the admin UI cleared the bar a CFO would expect at DISC. The Django templates ship today as unstyled HTML against `core/templates/base.html`. PolicyCodex was about to walk into the conference looking like a hobby project regardless of how strong the architecture story is. The PM brainstorm ran three options against five mockup screens (catalog, wizard reviewer-roles, wizard PDF upload with HTMX extraction, foundational typed-table editor with HTMX row-add, policy detail with AI summary). The bar Chuck named was Linear, Notion, Stripe Dashboard, modern Microsoft 365.

## Options considered

**Option A: Pico.css classless + 40-line overlay + HTMX.** Lowest dependency. No build chain. Custom CSS overlay was 45 lines. Read as "credible enterprise software" but not "modern SaaS." Pico's defaults still carry a 2018 minimal-CSS-framework aesthetic. Chuck's gut read after viewing the mockup: not enough for DISC.

**Option B: Bootstrap 5 + 30-line overlay + HTMX.** Universally recognizable. Class-heavy templates. Visual identity stamped as "Bootstrap." Chuck's gut read: confirms the 2018 admin-template look, makes the problem worse rather than better.

**Option C: Tailwind CSS + DaisyUI + Inter + HTMX.** Modern SaaS look out of the box. Tailwind utility classes plus DaisyUI component vocabulary plus Inter typeface plus a slate palette converge into the Linear/Notion family by default. Custom CSS overlay was 30 lines. Build chain is the Tailwind standalone CLI: one static binary, runs once at install. Templates are class-heavy but utility-named rather than framework-named. Chuck's gut read after viewing the third mockup: yes, this is the bar.

## Why Tailwind + DaisyUI wins for v0.1

The visual delta against the other two options is large at projector resolution. The DISC audience (diocesan IT directors and the CFO end users they bring along) reads "modern SaaS" within two seconds and that matters more than any pixel-level detail.

DaisyUI gives a component vocabulary (`btn`, `card`, `badge`, `alert`, themes via CSS variables) so the polish-week budget does not get eaten by hand-rolling a design system. Brand color, typeface, radii, and shadows all live in CSS variables, which gives every diocese a clean retheming path.

The build chain cost is real but bounded. Tailwind ships a standalone CLI as a single static binary. Install adds one curl-and-execute step. REPO-10's clean-VM premise survives. No Node, no npm, no postcss in the install path.

All four runtime dependencies (Tailwind, DaisyUI, HTMX, Inter) are MIT, 0BSD, or SIL OFL. AGPL-3.0 absorbs all of them cleanly.

## Forward compatibility analysis

The lock-in question is not really about the CSS framework. It is about the template architecture. Three possible future moves:

**Move 1: Stay server-rendered, add richer interactivity.** Alpine.js or Stimulus on top of HTMX, or more HTMX. Trivial migration from any starting point.

**Move 2: Heavier component library on the same foundation.** shadcn/ui, Headless UI, Flowbite, Radix primitives. All Tailwind-native or Tailwind-friendly. Picking Tailwind today is the on-ramp for any of these. Cost: roughly one day to adopt shadcn/ui on the foundational editor and detail view if we wanted it post-DISC.

**Move 3: Move to a SPA.** React + a design system, Vue + Vuetify, Svelte + Skeleton. Full frontend rewrite no matter what we pick today. 3 to 6 weeks. The CSS framework choice does not change this estimate. What does change it: whether business logic sits in Django models and services (portable) or in Django template tags and HTMX fragment URLs (not portable).

Picking Tailwind + DaisyUI now does not block any future direction. It sits on the on-ramp for the most likely next moves (richer Tailwind-based component libraries) and is neutral on the SPA path.

## Swap cost matrix from this starting point

- **To Pico or Bootstrap later:** easy. 1-2 days. Would not actually do this.
- **To shadcn/ui or Headless UI:** trivial. Keep Tailwind, adopt the component vocabulary. 1 day.
- **To a different Tailwind-based theme (Flowbite, custom):** half a day.
- **To React + MUI / Vue + Vuetify / etc.:** 3-6 weeks full rewrite. Tailwind/DaisyUI choice does not affect estimate.
- **To a custom independent design system:** depends on Tailwind-compatibility. If compatible, easy. If not, full rewrite.

## Licensing analysis

AGPL-3.0 §13 requires that any user interacting with PolicyCodex over a network gets the corresponding source on request, and that source must be redistributable under AGPL. Permissive licenses flow into AGPL cleanly. Restrictive licenses do not.

**AGPL-compatible (permissive) license families:** MIT, BSD-2-Clause, BSD-3-Clause, Apache 2.0, MPL 2.0 (with file-level care), SIL Open Font License 1.1, 0BSD, Unlicense, CC0.

**AGPL-incompatible (restrictive commercial component libraries):** any library whose license restricts redistribution. The named offenders worth calling out by name in the spec:

- **Tailwind UI** (the paid component library from Tailwind Labs)
- **MUI Pro** and **MUI Premium**
- **Ant Design Pro** components
- **DevExpress**
- **Telerik**
- **Kendo UI**

Their license terms forbid redistribution as components. AGPL-3.0 requires that downstream recipients receive the corresponding source with the same redistribution rights. The two cannot coexist in the same codebase.

This constraint binds dioceses too. A diocese that modifies their PolicyCodex install and serves it to staff cannot drop in Tailwind UI snippets or MUI Pro components without breaking either the component license or the AGPL terms they have inherited. The maintainer-mode services business inherits the same constraint: paid customization work for a diocese cannot bring in restricted components either.

The v0.1 frontend stack (Tailwind core, DaisyUI, HTMX, Inter) is entirely on the permissive side. If a future strategy conversation moves PolicyCodex to dual-licensing or a permissive license, this constraint relaxes. Until then, contributors and maintainers stay on the permissive side.

## Three guard rails (the work alongside the resolution)

**Guard rail 1: PRD section "Frontend Portability Constraints".** Three constraints that cost nothing in v0.1 and preserve the option to swap the frontend stack without rewriting the backend:

1. Views and HTMX fragments stay thin. Business logic lives in Django models, managers, and service functions.
2. HTMX endpoints are URL-segregated under `/htmx/`. A future JSON API at `/api/v1/` does not collide.
3. Authentication and authorization sit in middleware and view decorators, not in template logic.

**Guard rail 2: PRD Licensing subsection "Frontend Dependencies and AGPL Compatibility".** Allowed-license list, disallowed-pattern guidance with the six commercial component libraries named explicitly so a contributor reading the spec does not have to guess.

**Guard rail 3: Ticket APP-27.** Tiny architecture-hygiene ticket. Formalize the `/htmx/` URL prefix convention before HTMX endpoints start landing in templates. Add a one-paragraph views-stay-thin note to `CLAUDE.md`.

## Trade-offs we accept

**Template class density goes up.** Django templates carry Tailwind utility classes plus DaisyUI component classes. Compared to Pico classless, this is noisier. Compared to Bootstrap, it is similar density but uses utility names instead of framework-named components. Scarlet and the subagents need to learn the vocabulary once. The compensation is a result that clears the DISC bar without a separate design pass.

**Build chain enters the install path.** Tailwind standalone CLI is one static binary, so the cost is small. REPO-10's clean-VM premise expands by one step. Worth running through REPO-10's verification harness once APP-27 lands.

**Commercial component libraries permanently off the table while AGPL.** Named explicitly so future contributors do not waste time proposing Tailwind UI or MUI Pro components.

## What did not get filed

The bigger UI-adoption work (vendor the Tailwind standalone binary into the repo or scripted-download it, wire it into `manage.py collectstatic` or a pre-commit hook to emit `policycodex.css`, retemplate the existing eight Django templates to the Tailwind + DaisyUI vocabulary, update REPO-10's clean-VM verification harness to cover the new build step) is real work that follows from this decision. It belongs as one or more polish-week tickets after APP-27 sets the foundation. Open as APP-28 or a sibling depending on how the lane wants to slice it.

## Snippets for Scarlet (handoff for the OQ tracker and ticket board)

The OQ tracker and the ticket board belong to Scarlet per the standing role boundary. The snippets below are drafted in the existing file formats. Paste them into the corresponding files in a single commit, or hand them to Scarlet to land.

### For `internal/PolicyWonk-Open-Questions.md`

Add to the **Resolved** table:

```
| OQ-13 | UI framework for the Django admin app (CSS framework, JS sprinkle, and component vocabulary). | Resolved 2026-06-05. **Tailwind CSS + DaisyUI + HTMX**, Inter typeface, brand color set via DaisyUI CSS variables. Production build via Tailwind standalone CLI (single static binary, no Node). Three guard rails landed alongside: (1) PRD section "Frontend Portability Constraints" (thin views + `/htmx/` URL segregation + auth in middleware), (2) PRD Licensing subsection "Frontend Dependencies and AGPL Compatibility" (allowed-license list, disallowed commercial component libraries named), (3) ticket APP-27 (tiny architecture-hygiene, lands the `/htmx/` URL prefix convention and the views-stay-thin note in `CLAUDE.md`). Bigger UI-adoption work (vendor Tailwind CLI, retemplate the existing 8 Django templates, update REPO-10) belongs as a follow-on ticket; not auto-filed. Rationale and mockup comparison in `internal/PolicyWonk-UI-Framework-Decision.md` + `internal/mockups/disc-demo-{pico,bootstrap,tailwind}.html`. |
```

### For `PolicyWonk-v0.1-Tickets.md` (App Lane table)

Add after APP-26 (and before the lane-acceptance paragraph):

```
| APP-27 | UI framework architecture hygiene. (1) Add an `/htmx/` URL prefix to `core/urls.py` (or wherever HTMX fragment endpoints will live) so a future JSON API at `/api/v1/` does not collide. No HTMX endpoints exist yet; this ticket lays the convention before they land. (2) Add a 1-paragraph "Frontend portability constraints" note to `CLAUDE.md` under the existing **Tech** subsection of "What Has Already Been Reconsidered and Locked" capturing the three guard rails (views stay thin, HTMX URL-segregated, auth in middleware). Resolves OQ-13's architecture-hygiene piece. Build-chain enablement (vendor Tailwind standalone CLI, retemplate the 8 existing Django templates, REPO-10 update) is intentionally NOT in scope here; that follows as a sibling ticket. See `internal/PolicyWonk-UI-Framework-Decision.md` for rationale. | S | 5 | None |
```
