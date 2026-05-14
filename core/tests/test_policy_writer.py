"""Tests for core.policy_writer._render_policy_md."""
from ingest.policy_reader import _split_frontmatter

from core.policy_writer import _render_policy_md


def test_render_with_frontmatter_and_body():
    """Frontmatter + body should serialize as `---\\n<yaml>\\n---\\n<body>`."""
    fm = {"title": "Onboarding", "owner": "HR Director"}
    body = "## Purpose\nWelcome new hires.\n"
    out = _render_policy_md(fm, body)
    assert out.startswith("---\n")
    assert "title: Onboarding" in out
    assert "owner: HR Director" in out
    assert out.endswith("## Purpose\nWelcome new hires.\n")
    # The fence-line separator must end with a newline.
    assert "\n---\n" in out


def test_round_trip_preserves_unexposed_keys():
    """Reading then re-rendering must NOT lose frontmatter keys the form does not expose."""
    original = (
        "---\n"
        "title: Code of Conduct\n"
        "owner: Chancellor\n"
        "effective_date: 2026-01-01\n"
        "retention: 7y\n"
        "---\n"
        "## Scope\nAll staff.\n"
    )
    fm, body = _split_frontmatter(original)
    # Simulate the form changing only title + body.
    fm = dict(fm)
    fm["title"] = "Code of Conduct (Revised)"
    new_body = "## Scope\nAll staff and volunteers.\n"
    out = _render_policy_md(fm, new_body)
    # All four original frontmatter keys still present.
    assert "title: Code of Conduct (Revised)" in out
    assert "owner: Chancellor" in out
    assert "effective_date: 2026-01-01" in out
    assert "retention: 7y" in out
    # Body updated.
    assert "All staff and volunteers." in out
    # And re-parsing yields the same shape.
    fm2, body2 = _split_frontmatter(out)
    assert fm2["title"] == "Code of Conduct (Revised)"
    assert fm2["owner"] == "Chancellor"
    assert body2 == new_body


def test_empty_frontmatter_emits_empty_fenced_block():
    """A policy with no frontmatter keys still emits the fence so the body shape is consistent."""
    out = _render_policy_md({}, "Just a body.\n")
    assert out.startswith("---\n")
    assert "\n---\n" in out
    assert out.endswith("Just a body.\n")


def test_empty_frontmatter_output_round_trips_through_reader():
    """Empty frontmatter writer output must parse back as (empty_fm, body) via
    ingest.policy_reader._split_frontmatter. Without the blank line between
    fences, the reader's regex fails to match and the entire output ends up
    as body content. Regression guard from APP-07 code review."""
    from ingest.policy_reader import _split_frontmatter

    body = "Just a body.\nWith two lines.\n"
    out = _render_policy_md({}, body)
    fm, parsed_body = _split_frontmatter(out)
    assert fm == {}
    assert parsed_body == body


def test_no_em_dashes_in_output():
    """Discipline guard: the rendered output must contain no em dashes
    (project-wide style rule). yaml.safe_dump uses '-' for list items but
    must not emit U+2014. This test catches any future regression where
    a library/setting introduces a fancy-dash transform."""
    fm = {"title": "Policy", "tags": ["alpha", "beta"]}
    body = "Body text - with a hyphen.\n"
    out = _render_policy_md(fm, body)
    assert "—" not in out  # em dash
    assert "–" not in out  # en dash
