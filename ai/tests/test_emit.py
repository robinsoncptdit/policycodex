"""Tests for ai.emit.to_markdown (AI-08: markdown + YAML front-matter emitter)."""
import json
from pathlib import Path

import pytest
import yaml

from ai.emit import FRONTMATTER_KEY_ORDER, to_markdown


SPIKE_OUTPUTS = Path(__file__).resolve().parents[2] / "spike" / "outputs"


# ----- helpers -----

def _split_frontmatter(md: str) -> tuple[dict, str]:
    """Split a markdown string with YAML front matter into (frontmatter dict, body)."""
    assert md.startswith("---\n"), "Output must start with --- delimiter"
    rest = md[len("---\n"):]
    end = rest.find("\n---\n")
    assert end != -1, "Output must have a closing --- delimiter"
    frontmatter_text = rest[:end]
    body = rest[end + len("\n---\n"):]
    return yaml.safe_load(frontmatter_text), body


def _load_spike(name: str) -> dict:
    path = SPIKE_OUTPUTS / name
    if not path.exists():
        pytest.skip(f"Spike output {name} not present in this worktree")
    return json.loads(path.read_text())


# ----- tests -----

def test_round_trip_internal_controls():
    """Round-trip a full extraction (101 Internal Controls)."""
    extraction = _load_spike("101 Internal Controls.json")
    md = to_markdown(extraction)
    fm, _body = _split_frontmatter(md)

    # Canonical front-matter fields match the extraction (after filtering).
    assert fm["title"] == extraction["title"]
    assert fm["category"] == extraction["category"]
    assert fm["owner_role"] == extraction["owner_role"]
    assert str(fm["effective_date"]) == extraction["effective_date"]
    assert str(fm["last_review_date"]) == extraction["last_review_date"]
    assert fm["next_review_date"] == extraction["next_review_date"]  # null
    assert fm["retention_period_years"] == extraction["retention_period_years"]
    assert (
        fm["suggested_chapter_section_item"]
        == extraction["suggested_chapter_section_item"]
    )
    assert fm["version_stamp"] == extraction["version_stamp"]


def test_round_trip_cybersecurity_policy():
    """Round-trip a second spike output to confirm we are not tuned to one document."""
    extraction = _load_spike("2022 Cybersecurity Policy.json")
    md = to_markdown(extraction)
    fm, body = _split_frontmatter(md)

    assert fm["title"] == extraction["title"]
    assert fm["category"] == extraction["category"]
    assert fm["effective_date"] is None  # was null in the source
    assert fm["retention_period_years"] == 3
    assert extraction["summary"] in body


def test_null_value_emits_as_null():
    """A null value in the dict round-trips to YAML null (not empty string, not missing)."""
    extraction = {
        "title": "T",
        "summary": "S",
        "category": "Finance",
        "owner_role": "CFO",
        "effective_date": "2014-08-01",
        "last_review_date": "2014-08-01",
        "next_review_date": None,
        "retention_period_years": 7,
        "suggested_chapter_section_item": "10.1.1",
        "version_stamp": "1.0",
    }
    md = to_markdown(extraction)
    fm, _ = _split_frontmatter(md)

    assert "next_review_date" in fm
    assert fm["next_review_date"] is None


def test_missing_key_emits_as_null():
    """A missing key in the dict still appears in the front matter, as null."""
    extraction = {
        "title": "T",
        "summary": "S",
        "category": "Finance",
        "owner_role": "CFO",
        "effective_date": "2014-08-01",
        "last_review_date": "2014-08-01",
        # next_review_date intentionally missing
        # retention_period_years intentionally missing
        "suggested_chapter_section_item": "10.1.1",
        "version_stamp": "1.0",
    }
    md = to_markdown(extraction)
    fm, _ = _split_frontmatter(md)

    assert "retention_period_years" in fm
    assert fm["retention_period_years"] is None
    assert "next_review_date" in fm
    assert fm["next_review_date"] is None


def test_key_ordering_is_stable():
    """Canonical front-matter keys emit in the defined stable order regardless of dict insertion order."""
    extraction = {
        "version_stamp": "1.0",
        "suggested_chapter_section_item": "10.1.1",
        "retention_period_years": 7,
        "next_review_date": None,
        "last_review_date": "2014-08-01",
        "effective_date": "2014-08-01",
        "owner_role": "CFO",
        "category": "Finance",
        "summary": "S",
        "title": "T",
    }
    md = to_markdown(extraction)
    # Read raw front-matter text (don't go through safe_load — that would re-order).
    rest = md[len("---\n"):]
    end = rest.find("\n---\n")
    raw = rest[:end]
    lines = [line for line in raw.splitlines() if line and not line.startswith(" ")]
    emitted_keys = [line.split(":", 1)[0] for line in lines]

    canonical = list(FRONTMATTER_KEY_ORDER)
    # The canonical keys present in extraction should appear in canonical order.
    canonical_emitted = [k for k in emitted_keys if k in canonical]
    assert canonical_emitted == canonical


def test_version_stamp_is_quoted_string():
    """version_stamp like '1.0' must emit as a quoted string, not a bare float."""
    extraction = {
        "title": "T",
        "summary": "S",
        "version_stamp": "1.0",
    }
    md = to_markdown(extraction)

    # The raw YAML line must keep the value as a quoted string so round-trip stays str.
    rest = md[len("---\n"):]
    end = rest.find("\n---\n")
    raw = rest[:end]
    version_lines = [ln for ln in raw.splitlines() if ln.startswith("version_stamp:")]
    assert len(version_lines) == 1
    line = version_lines[0]
    # Either single- or double-quoted is fine, but a bare 1.0 is not.
    assert "'1.0'" in line or '"1.0"' in line, (
        f"version_stamp must be quoted, got: {line!r}"
    )

    # And a safe_load round-trip preserves the string type.
    fm, _ = _split_frontmatter(md)
    assert fm["version_stamp"] == "1.0"
    assert isinstance(fm["version_stamp"], str)


def test_body_contains_summary():
    """The body section after the closing --- contains the summary text."""
    extraction = {
        "title": "Internal Controls Policy",
        "summary": "This policy establishes the framework for internal controls.",
    }
    md = to_markdown(extraction)
    _, body = _split_frontmatter(md)

    assert "This policy establishes the framework for internal controls." in body


def test_frontmatter_shape_uses_triple_dash_delimiters():
    """Output starts with --- and has a closing --- separator before the body."""
    extraction = {"title": "T", "summary": "S"}
    md = to_markdown(extraction)

    assert md.startswith("---\n")
    rest = md[len("---\n"):]
    assert "\n---\n" in rest, "Closing --- delimiter missing"


def test_confidence_keys_are_excluded():
    """*_confidence keys must not appear in the front matter or anywhere in the markdown."""
    extraction = {
        "title": "T",
        "summary": "S",
        "category": "Finance",
        "category_confidence": "high",
        "owner_role": "CFO",
        "owner_role_confidence": "high",
        "effective_date": "2014-08-01",
        "effective_date_confidence": "medium",
        "address_confidence": "medium",
        "retention_period_confidence": "low",
    }
    md = to_markdown(extraction)
    fm, _ = _split_frontmatter(md)

    for key in (
        "category_confidence",
        "owner_role_confidence",
        "effective_date_confidence",
        "address_confidence",
        "retention_period_confidence",
    ):
        assert key not in fm, f"{key} leaked into front matter"
        assert key not in md, f"{key} leaked into markdown body"


def test_source_file_metadata_excluded_from_frontmatter():
    """_source_file is spike-internal metadata and must not pollute the YAML front matter."""
    extraction = {
        "title": "T",
        "summary": "S",
        "_source_file": "101 Internal Controls.pdf",
    }
    md = to_markdown(extraction)
    fm, _ = _split_frontmatter(md)

    assert "_source_file" not in fm


def test_block_style_not_inline():
    """YAML must emit as block style, not as a single inline {} dict."""
    extraction = {"title": "T", "summary": "S", "category": "Finance"}
    md = to_markdown(extraction)
    rest = md[len("---\n"):]
    end = rest.find("\n---\n")
    raw = rest[:end]

    # Block style emits one key per line; inline style emits as `{title: T, ...}`.
    assert "{" not in raw
    assert "\n" in raw, "Block-style YAML should span multiple lines"


def test_notes_section_when_present():
    """A non-empty notes field should appear as a clearly delineated section in the body."""
    extraction = {
        "title": "T",
        "summary": "Summary text.",
        "notes": "Extraction caveat: dates inferred from revision header.",
    }
    md = to_markdown(extraction)
    _, body = _split_frontmatter(md)

    assert "Extraction caveat: dates inferred from revision header." in body
    assert "Summary text." in body
