"""APP-28c: the /htmx/ tree now carries the first fragment endpoints."""
from django.urls import reverse

from core import htmx_urls
from core import urls as core_urls


def test_htmx_urls_module_is_namespaced():
    # The namespace is reserved; fragment views reverse as `htmx:<name>`.
    assert htmx_urls.app_name == "htmx"


def test_foundational_row_route_is_registered():
    # Some entries are URLResolvers (the onboarding /htmx/onboarding/ include)
    # with no .name, so read names defensively.
    names = [getattr(p, "name", None) for p in htmx_urls.urlpatterns]
    assert "foundational_row" in names


def test_core_urls_includes_the_htmx_prefix():
    # The prefix must be wired into core.urls so a future JSON API at
    # /api/v1/ cannot collide with the HTMX fragment surface.
    prefixes = [str(p.pattern) for p in core_urls.urlpatterns]
    assert "htmx/" in prefixes


def test_htmx_endpoints_reverse_under_the_namespace():
    assert (
        reverse("htmx:foundational_row", kwargs={"slug": "x"})
        == "/htmx/foundational/x/row/"
    )
    assert reverse("htmx:onboarding_screen7") == "/htmx/onboarding/screen7/"
