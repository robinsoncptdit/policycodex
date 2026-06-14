# DISC smoke test

End-to-end Playwright test that drives the post-pivot PolicyCodex Settings flow:
seeded-admin login, forced password change, then the Settings panels (GitHub App,
AI provider, Policy repository), an Inventory upload, and a catalog sync that surfaces
the opened PR. Acts as the DISC-readiness merge gate.

## Required secrets (configured in GitHub Actions repo settings)

- `DISC_SMOKE_GH_APP_ID`: GitHub App ID for a test app
- `DISC_SMOKE_GH_INSTALLATION_ID`: Installation ID in the test org
- `DISC_SMOKE_GH_PRIVATE_KEY`: PEM contents of the test app's private key
- `DISC_SMOKE_ANTHROPIC_KEY`: Anthropic API key for the test budget
- `DISC_SMOKE_TEST_ORG`: GitHub org where test repos are created
- `DISC_SMOKE_TEARDOWN_TOKEN`: PAT with `delete_repo` scope on the test org

## Running locally

```sh
docker compose up --build -d

# Wait for the container to be healthy:
curl -fsS http://localhost:8000/health/

pip install -r tests/disc_smoke/requirements.txt
playwright install --with-deps chromium

export DISC_SMOKE_GH_APP_ID=...
export DISC_SMOKE_GH_INSTALLATION_ID=...
export DISC_SMOKE_GH_PRIVATE_KEY="$(cat /path/to/key.pem)"
export DISC_SMOKE_ANTHROPIC_KEY=sk-ant-...
export DISC_SMOKE_TEST_ORG=your-test-org

python tests/disc_smoke/playwright_smoke.py
```

## Corpus

`tests/fixtures/disc-smoke-corpus/` holds 19 synthetic AGPL-compatible policy PDFs.
PDF 18 (`18-scanned-compliance-memo.pdf`) is intentionally image-only (no text layer)
and exercises the per-item failure path. The remaining 18 PDFs have readable text layers.

Regenerate with:

```sh
pip install reportlab pillow
python tests/fixtures/disc-smoke-corpus/_generate.py
```

The generated PDFs are committed alongside the generator script so CI does not need
`reportlab` or `pillow` to run the smoke test.

## Assertion

After the inventory run, the smoke test asserts two visible states, with a catalog
sync between them:

1. The extraction-success alert appears (`.alert-success` containing "Most recent
   extraction"), confirming the inventory pass finished.
2. The test then syncs the catalog from GitHub (Catalog panel -> "Sync from GitHub")
   — a click action, not an assertion.
3. A "View PR" link is visible on the Inventory page, confirming the run opened the
   pull request.

The test does not assert a catalog row count.
