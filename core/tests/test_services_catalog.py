from pathlib import Path
from ingest.policy_reader import LogicalPolicy
from core.services import build_catalog


def _pol(slug, *, category=None):
    pp = Path(f"/tmp/policies/{slug}.md")
    fm = {"title": slug.title()}
    if category is not None:
        fm["category"] = category
    return LogicalPolicy(slug=slug, kind="flat", policy_path=pp, data_path=None,
                         frontmatter=fm, body="", foundational=False, provides=())


class _Reader:
    def __init__(self, _dir):
        self._dir = _dir
    def read(self):
        return iter(_Reader.policies)


def test_build_catalog_assembles_rows_gaps_and_pending():
    _Reader.policies = [_pol("known", category="Financial"), _pol("unknown", category="Marketing")]
    gate = {"unknown": {"gate": "drafted", "pr": {"number": 7}}}
    def load_tax(_dir, _req):
        return {"classifications": [{"id": "financial", "name": "Financial"}]}
    out = build_catalog(Path("/tmp/policies"), Path("/tmp"),
                        reader_cls=_Reader, load_taxonomy=load_tax,
                        gate_lookup_fn=lambda wd: gate)
    assert out["gap_count"] == 1
    assert {r["policy"].slug: r["gate"] for r in out["rows"]} == {"known": "published", "unknown": "drafted"}
    assert [p["policy"].slug for p in out["pending_review"]] == ["unknown"]


def test_build_catalog_degrades_when_taxonomy_load_raises():
    _Reader.policies = [_pol("x", category="Whatever")]
    def boom(_dir, _req):
        raise RuntimeError("bad data.yaml")
    out = build_catalog(Path("/tmp/policies"), Path("/tmp"),
                        reader_cls=_Reader, load_taxonomy=boom, gate_lookup_fn=lambda wd: {})
    assert out["gap_count"] == 0 and out["rows"][0]["gate"] == "published"
