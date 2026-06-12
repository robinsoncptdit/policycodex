"""End-to-end smoke for the post-pivot Settings flow.

Walk: login as seeded admin → forced password change → Settings/GitHub App
(manual paste) → AI provider → Policy repository (Create new) → Inventory
upload → wait for completion → catalog sync → verify PR link visible.

Manifest flow is NOT exercised because it requires a real GitHub round-trip
that is not feasible in a headless CI smoke. The manual-paste path
validates the same underlying credentials.

Run as a standalone script:

    python tests/disc_smoke/playwright_smoke.py

Required env vars (see README for the full list):
    DISC_SMOKE_GH_APP_ID, DISC_SMOKE_GH_INSTALLATION_ID,
    DISC_SMOKE_GH_PRIVATE_KEY, DISC_SMOKE_ANTHROPIC_KEY, DISC_SMOKE_TEST_ORG.
"""
from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


BASE = os.environ.get("DISC_SMOKE_BASE_URL", "http://localhost:8000")
GH_APP_ID = os.environ["DISC_SMOKE_GH_APP_ID"]
GH_INSTALLATION_ID = os.environ["DISC_SMOKE_GH_INSTALLATION_ID"]
GH_PEM = os.environ["DISC_SMOKE_GH_PRIVATE_KEY"]
ANTHROPIC_KEY = os.environ["DISC_SMOKE_ANTHROPIC_KEY"]
TEST_ORG = os.environ["DISC_SMOKE_TEST_ORG"]
REPO_NAME = os.environ.get(
    "DISC_SMOKE_REPO_NAME",
    f"policycodex-smoke-{uuid.uuid4().hex[:8]}",
)
CORPUS = Path(__file__).resolve().parent.parent / "fixtures" / "disc-smoke-corpus"


def run():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        # 1. Login as seeded admin.
        page.goto(f"{BASE}/login/")
        page.fill('input[name="username"]', "admin")
        page.fill('input[name="password"]', "admin1234")
        page.click('button[type="submit"]')

        # 2. Forced password change.
        expect(page).to_have_url(f"{BASE}/accounts/password/change/?next=/", timeout=10_000)
        new_password = "kestrel-sapphire-meadow-91"
        page.fill('input[name="old_password"]', "admin1234")
        page.fill('input[name="new_password1"]', new_password)
        page.fill('input[name="new_password2"]', new_password)
        page.click('button[type="submit"]')

        # 3. lifecycle_state routes us to /settings/github-app/.
        expect(page).to_have_url(f"{BASE}/settings/github-app/", timeout=10_000)

        # 4. GitHub App — manual paste path (manifest flow needs real GitHub).
        page.locator('summary:has-text("Paste credentials manually")').click()
        page.fill('input[name="app_id"]', GH_APP_ID)
        page.fill('input[name="installation_id"]', GH_INSTALLATION_ID)
        page.fill('textarea[name="private_key_pem"]', GH_PEM)
        page.click('button:has-text("Test connection")')
        expect(page.locator('[data-state="ok"]')).to_be_visible(timeout=15_000)
        page.click('button:has-text("Save")')
        expect(page.locator('.alert-success')).to_be_visible(timeout=10_000)

        # 5. AI provider.
        page.click('a:has-text("AI provider")')
        expect(page).to_have_url(f"{BASE}/settings/llm-provider/")
        page.check('input[value="claude"]')
        page.fill('input[name="api_key"]', ANTHROPIC_KEY)
        page.click('button:has-text("Test key")')
        expect(page.locator('[data-state="ok"]')).to_be_visible(timeout=15_000)
        page.click('button:has-text("Save")')
        expect(page.locator('.alert-success')).to_be_visible(timeout=10_000)

        # 6. Policy repository — Create new.
        page.click('a:has-text("Policy repository")')
        expect(page).to_have_url(f"{BASE}/settings/policy-repo/")
        page.click('a:has-text("Create")')
        page.fill('input[name="org"]', TEST_ORG)
        page.fill('input[name="repo_name"]', REPO_NAME)
        page.click('button:has-text("Create repository")')
        # Allow up to 60s for repo creation + initialization push.
        expect(page.locator('.alert-success')).to_be_visible(timeout=60_000)

        # 7. Inventory — drop the corpus.
        page.click('a:has-text("Inventory")')
        expect(page).to_have_url(f"{BASE}/inventory/")
        all_pdfs = sorted(str(p) for p in CORPUS.glob("*.pdf"))
        if not all_pdfs:
            raise RuntimeError(f"No PDFs found in {CORPUS}")
        page.set_input_files('input[name="files"]', all_pdfs)
        # The bucket form submits on file selection or on the (hidden) Upload
        # button. Force a submit via JS to be robust against either pattern.
        page.evaluate(
            "document.querySelector('#bucket form').requestSubmit()"
        )

        # 8. Wait up to 10 min for the run to complete and the PR to open.
        expect(
            page.locator('.alert-success:has-text("Most recent extraction")')
        ).to_be_visible(timeout=600_000)

        # 9. Sync the catalog, then verify the inventory page exposes the PR.
        page.click('a:has-text("Catalog")')
        expect(page).to_have_url(f"{BASE}/catalog/")
        page.click('button:has-text("Sync from GitHub")')

        page.click('a:has-text("Inventory")')
        expect(page.locator('a:has-text("View PR")')).to_be_visible()

        browser.close()
    print("SMOKE PASS")


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        print(f"SMOKE FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
