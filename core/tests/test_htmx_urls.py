"""APP-27/APP-28b: the /htmx/ prefix convention; foundational_row route reserved."""
from django.urls import reverse

from core import htmx_urls
from core import urls as core_urls


def test_htmx_urls_module_is_namespaced():
    # The namespace is reserved; fragment views reverse as `htmx:<name>`.
    assert htmx_urls.app_name == "htmx"


def test_foundational_row_route_is_registered():
    # APP-28b reserves this route; APP-28c fills in the real body.
    names = [p.name for p in htmx_urls.urlpatterns]
    assert "foundational_row" in names


def test_foundational_row_reverses():
    url = reverse("htmx:foundational_row", kwargs={"slug": "document-retention"})
    assert url == "/htmx/foundational/document-retention/row/"


def test_core_urls_includes_the_htmx_prefix():
    # The prefix must be wired into core.urls so a future JSON API at
    # /api/v1/ cannot collide with the HTMX fragment surface.
    prefixes = [str(p.pattern) for p in core_urls.urlpatterns]
    assert "htmx/" in prefixes
