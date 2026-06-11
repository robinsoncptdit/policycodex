import pytest
from django.template.loader import render_to_string


def test_base_settings_renders_nav_groups():
    html = render_to_string("settings/base_settings.html", {
        "active_slug": "github-app",
        "nav_groups": [
            ("Credentials", [
                {"slug": "github-app", "title": "GitHub App"},
                {"slug": "llm-provider", "title": "AI provider"},
            ]),
            ("Diocese", [
                {"slug": "policy-repo", "title": "Policy repository"},
            ]),
        ],
        "panel_title": "GitHub App",
    })
    assert "Credentials" in html
    assert "Diocese" in html
    assert "GitHub App" in html
    assert "AI provider" in html
    assert "Policy repository" in html


def test_active_slug_marked():
    html = render_to_string("settings/base_settings.html", {
        "active_slug": "llm-provider",
        "nav_groups": [
            ("Credentials", [
                {"slug": "github-app", "title": "GitHub App"},
                {"slug": "llm-provider", "title": "AI provider"},
            ]),
        ],
        "panel_title": "AI provider",
    })
    # Exactly one link carries the active marker classes; both slugs render.
    assert html.count("bg-base-200 font-medium") == 1
    assert "github-app" in html
    assert "llm-provider" in html
