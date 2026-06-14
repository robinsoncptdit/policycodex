"""REPO-10 / APP-28d: the compiled CSS and HTMX ship and are collectible."""
import pytest
from django.contrib.staticfiles import finders

pytestmark = pytest.mark.django_db


def test_policycodex_css_is_collectible():
    assert finders.find("css/policycodex.css") is not None
    assert finders.find("js/htmx.min.js") is not None


def test_served_css_carries_brand_and_component_sentinels():
    path = finders.find("css/policycodex.css")
    text = open(path, encoding="utf-8").read()
    # Brand primary survives compilation as the literal hex
    # (`--color-primary:#4a5f8a`); Tailwind v4 leaves theme-var hex untouched.
    assert "4a5f8a" in text.lower() or "74 95 138" in text  # brand color survived
    assert ".btn" in text  # DaisyUI component survived (update if fallback taken)


def test_served_css_covers_newest_template_classes():
    # APP-35: the real drift guard (test_css_build.py) is env-gated and never
    # runs in CI, so APP-29/31 landed templates against a stale compiled CSS.
    # Pin one class per newest template as a toolchain-free canary; extend
    # this list whenever a template introduces classes the CSS may not carry.
    path = finders.find("css/policycodex.css")
    text = open(path, encoding="utf-8").read()
    # F3/F6: the prior canary pinned classes from the onboarding templates
    # deleted in the Settings rebuild (commit dace636). Pin classes the live
    # Settings/Inventory templates actually use and that the @source fix must
    # restore: destructive-action buttons and save/test success banners.
    assert ".btn-error" in text  # app/settings/templates/.../reset.html (destructive buttons)
    assert ".alert-success" in text  # app/settings/.../_panel_messages.html (save banners)
    assert ".badge-error" in text  # settings/inventory status badges
