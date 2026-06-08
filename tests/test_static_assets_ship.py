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
