"""APP-27: the /htmx/ prefix convention is laid before any endpoints exist."""
from core import htmx_urls
from core import urls as core_urls


def test_htmx_urls_module_is_namespaced_and_empty():
    # The htmx fragment endpoints (APP-28c) will live here and reverse as
    # `htmx:<name>`. For now the namespace is reserved with no endpoints.
    assert htmx_urls.app_name == "htmx"
    assert htmx_urls.urlpatterns == []


def test_core_urls_includes_the_htmx_prefix():
    # The prefix must be wired into core.urls so a future JSON API at
    # /api/v1/ cannot collide with the HTMX fragment surface.
    prefixes = [str(p.pattern) for p in core_urls.urlpatterns]
    assert "htmx/" in prefixes
