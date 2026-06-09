# APP-29 — Wizard completion screen design

Date: 2026-06-08
Ticket: APP-29 (S, 5) — depends on APP-16, APP-28
Status: approved, ready for writing-plans

## Problem

When onboarding finishes, the wizard opens the configuration PR via
`finalize_onboarding` and then jumps the admin straight to the policy catalog
(`redirect("catalog")` at `app/onboarding/retention_policy.py:218` for the
plain-POST `accept` path, and `:353` for the HTMX fragment path). Nothing tells
the admin what to do next to get the handbook actually online. Today that
sequence (merge the PR, configure GitHub Pages, set the registrar CNAME) lives
only in `HOWTO-GitHub-Team-Setup.md`, so the admin has to alt-tab to docs to
finish the job. APP-29 closes that disconnect with a presentation-only
completion screen.

Scope is deliberately small and presentation-only: no API calls, no commits, no
GitHub Pages API. The screen renders at **wizard completion** (when the PR is
*opened*), not after the PR merges — the wizard has no merge callback. The
screen instructs the admin through the merge.

Bigger wizard-managed handbook publishing (subdomain collected inside the
wizard, `CNAME` committed automatically) is out of scope; that ships in v0.2 per
PRD P2.7.

## Architecture: dedicated GET view

A new GET-able view + URL, chosen over inline render so the screen is
refresh-safe and revisitable (the admin will sit on it while doing DNS + Pages
configuration). Matches the ticket's "new Django view" wording.

- New URL name `onboarding-complete` wired in `app/onboarding/urls.py`.
- New view `onboarding_complete` in `app/onboarding/views.py`.
- The `accept` handler stops calling `redirect("catalog")`. Instead it stashes
  the PR url in the session and redirects to the completion view:
  - Plain-POST path (`retention_policy.py:218`): set
    `request.session["onboarding_pr_url"] = pr.get("url", "")`, then
    `return redirect("onboarding-complete")`.
  - HTMX fragment path (`:353`): set the same session key, then return an empty
    `HttpResponse(status=200)` carrying header
    `HX-Redirect: <reverse("onboarding-complete")>` so htmx performs a full-page
    navigation. A fragment cannot host the standalone completion screen.
- Drop the existing `messages.success(...)` PR toast at both exit points — the
  PR link now lives in step 1 of the completion screen.

## Data flow (all presentation, zero API calls)

The completion view derives everything from wizard state + session. No network
calls.

Source of org/repo: `state.get_data("github-repo")` (the screen-1 form data).
- `mode == "connect"`: parse `repo_url` (`https://github.com/<org>/<repo>`,
  optional trailing `.git`) into its two path segments. `org` = first segment,
  `repo` = second segment with any `.git` stripped.
- `mode == "create"`: `org` = the `org` field, `repo` = the `repo_name` field.

Derived values:
- `repo_url`     = `https://github.com/{org}/{repo}`
- `pages_url`    = `{repo_url}/settings/pages`
- `cname_target` = `{org}.github.io`
- `howto_url`    = `{source_url}/blob/main/HOWTO-GitHub-Team-Setup.md`, where
  `source_url` is `settings.POLICYCODEX_SOURCE_URL` (already exposed to templates
  by `core/context_processors.py` as `source_url`; default
  `https://github.com/policycodex/policycodex`). Reuses the REPO-05 "View Source"
  config rather than inventing a new constant.
- `pr_url` = `request.session.pop("onboarding_pr_url", None)` — best-effort.
  Step 1 shows the link when present, plain instruction text when absent.

`cname_target` of `{org}.github.io` is correct for a GitHub Pages custom
subdomain (`handbook.<diocese>.org`): the CNAME record points at the
user/org Pages host regardless of project-vs-user pages. Confirmed against the
shipping `repo-template/.github/workflows/build-handbook.yml`
(`actions/deploy-pages@v5`, reads `.cname`; Pages auto-provisions the
Let's Encrypt cert).

## Template

`app/onboarding/templates/onboarding/complete.html`, written in the
DaisyUI / Inter vocabulary established by APP-28(b) so the APP-28 retemplate pass
does not have to revisit it.

- Heading: "Your handbook is almost live."
- Ordered 1-2-3 checklist conveying the real sequence (nothing publishes until
  the PR merges):
  1. Merge the onboarding PR. `[view PR ->]` linking `pr_url` when present.
  2. Configure GitHub Pages. `[open settings ->]` linking `pages_url`.
  3. Set the CNAME at your registrar: `handbook -> {cname_target}` with a
     copy button (same copy-button pattern used elsewhere in the app).
- "Continue to your catalog" button -> `catalog`.
- Footer line: full sequence linking `howto_url`.

Copy is em-dash-free and apostrophe-light per the project style guide.

## Edge case / guard

If `onboarding-complete` is requested without finished onboarding (no wizard
state, or the `github-repo` step data is missing/empty so org/repo cannot be
derived), redirect to the wizard start rather than rendering a half-empty
screen.

## Testing

- View renders for `connect` mode: asserts `repo_url`, `pages_url`,
  `{org}.github.io`, `howto_url` are all correct in context/markup.
- View renders for `create` mode (org + repo_name): same assertions.
- `pr_url` present -> step-1 link shown; absent -> graceful plain text, no
  broken/empty anchor.
- Plain-POST `accept` redirects to `onboarding-complete` and the PR url is in
  the session.
- HTMX `accept` path returns 200 with the `HX-Redirect` header pointing at
  `onboarding-complete`.
- Guard: GET with no wizard state / missing `github-repo` data redirects to the
  wizard start.

## Out of scope

- Any GitHub Pages API call, repo commit, or CNAME file commit (v0.2 P2.7).
- Polling or detecting PR-merge state.
- Collecting the handbook subdomain inside the wizard.
