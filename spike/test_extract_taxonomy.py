"""AI-12-revised: spike/extract.py taxonomy resolution regression test.

With no POLICYCODEX_POLICIES_DIR set, extract.py must source the seed
taxonomy exactly as before (8 classifications) and render a stable prompt
section, so the change is a pure re-point with no default-behavior drift.
"""
import importlib


def test_extract_defaults_to_seed_taxonomy(monkeypatch):
    monkeypatch.delenv("POLICYCODEX_POLICIES_DIR", raising=False)
    import extract  # spike/ is on sys.path under pytest (rootdir insertion)
    importlib.reload(extract)
    assert extract._taxonomy_source == "seed"
    assert len(extract.TAXONOMY["classifications"]) == 8
    for entry in extract.TAXONOMY["classifications"]:
        assert entry["id"] in extract.TAXONOMY_SECTION
