# PolicyWonk Web Framework Evaluation (APP-01)

**Date:** 2026-05-08
**Author:** Plan subagent (Claude, Friday-night Phase 2 dispatch)
**Status:** Resolved 2026-05-11. Chuck signed off on Django. APP-01 skeleton + APP-02 unblocked for Week 2 dispatch.

## Recommendation: Python + Django

## Why Django wins

Django ships the primitives this app actually needs out of the box: server-rendered forms with CSRF, sessions, an ORM for the small amount of local state (auth, working-copy metadata, manifest cache), an admin panel for scaffolding, and the `FormWizard`/multi-step form pattern that maps cleanly onto the seven-screen wizard (P0.6). `subprocess.run(["git", ...])` plus `requests` or `PyGithub` covers APP-04 (clone, branch, commit, push, open PRs). AI-01 and APP-03 are being built in Python during the same Friday push, so the App lane imports them in-process — no port, no IPC, no language fork. A single `python:3.12-slim` image plus SQLite (or optional Postgres) satisfies the "running within 30 minutes on a clean VM" criterion.

## Why Next.js loses

Next.js's strengths (React Server Components, edge runtimes, rich client interaction) are wasted on this app's explicit Non-Goal #5 ("no designer-polished consumer UI"). Worse, picking Next forks the runtime: either re-port AI-01/APP-03 to TypeScript (paying twice for working code in a six-week sprint) or run a Python sidecar with an HTTP/IPC contract. Bad calendar economics.

## Why Go + HTMX loses (close second)

Go + HTMX is operationally cleanest: single static binary, trivial Docker image, HTMX is a near-perfect fit for the seven-screen wizard pattern. The Python interfaces from Friday (LLM provider, Git provider) are shallow enough to redo in Go in 2–4 dev-days. But "redo in 2–4 dev-days" is not free in an AI-agent-driven workflow where the Python code is fresh and tested. Framework familiarity also weakest here, and the spec flags Chuck-familiarity as a plus.

## Risks Django introduces

1. **Operational footprint vs. Go.** Django + Gunicorn + DB is heavier than a Go static binary. Mitigation: SQLite by default, Postgres optional; slim base images.
2. **Async Git operations under load.** Django is sync-first. APP-04 round-trips to GitHub can be slow. Mitigation: Django async views for API calls, or queue long ops via Django-Q/RQ. For v0.1 single-tenant scale, synchronous-with-spinner is acceptable.
3. **WYSIWYG editor (P1.5) post-v0.1.** Django templates + Stimulus/HTMX/Alpine sprinkle handles it. If the team later pivots to React-heavy UI, you fight the framework. Acceptable since P1.5 is explicitly Nice-to-Have.
4. **Two language ecosystems if Publish adds tooling.** Astro/Hugo run in GitHub Actions, so loosely coupled. Not a real risk.

## PRD acceptance criteria matched

- P0.4 ("Display the policy catalog as a sortable, filterable list") → Django ListView + filters
- P0.4 ("create a branch, commit the edit, and open a PR") → subprocess + PyGithub
- P0.6 ("Seven screens covering...") → Django FormWizard
- P0.7 ("PolicyWonk is running on a configured port within 30 minutes") → Docker Compose with `python:3.12-slim`
