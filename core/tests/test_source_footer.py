"""The AGPL 'View Source' footer must appear on rendered pages (REPO-05)."""
import pytest
from django.test import Client


@pytest.mark.django_db
def test_login_page_shows_view_source_link(settings):
    settings.POLICYCODEX_SOURCE_URL = "https://example.test/policycodex"
    resp = Client().get("/login/", HTTP_HOST="127.0.0.1")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "View Source" in body
    assert 'href="https://example.test/policycodex"' in body
