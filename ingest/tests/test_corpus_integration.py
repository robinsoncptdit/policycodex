"""End-to-end ingest verification against a real local corpus (INGEST-06).

Gated on POLICYCODEX_CORPUS_DIR: set it to a folder of source documents to
run; unset (CI default) -> these tests skip. The committed assertions are
corpus-agnostic (no hardcoded file count, no diocese specifics) so any
diocese can point the env var at their own corpus. The v0.1 PT-corpus run
(the 19 spike PDFs) is captured as evidence in the Daily Log, not asserted
here.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from ingest.extractors import extract
from ingest.incremental import plan_incremental_run, save_manifest
from ingest.local_folder import LocalFolderConnector
from ingest.manifest import build_manifest

_CORPUS_ENV = "POLICYCODEX_CORPUS_DIR"
_raw = os.environ.get(_CORPUS_ENV)
CORPUS_DIR: Path | None = Path(_raw).expanduser() if _raw else None

corpus_required = pytest.mark.skipif(
    CORPUS_DIR is None or not CORPUS_DIR.is_dir(),
    reason=f"{_CORPUS_ENV} not set to an existing directory",
)


@corpus_required
def test_walk_yields_all_corpus_files():
    walked = list(LocalFolderConnector(CORPUS_DIR).walk())
    assert walked, "corpus walk yielded no files"
    assert len(walked) == len(set(walked)), "corpus walk yielded duplicates"
    for p in walked:
        assert p.is_file(), f"walk yielded a non-file: {p}"


def _empty_extraction_is_explained(path: Path) -> bool:
    """An empty extraction is only acceptable for a genuinely image-only PDF
    (a scan with no text layer). Anything else -- an empty text file, a blank
    or corrupt PDF, or a regression in a text-bearing extractor -- is a real
    failure this test must catch. The text extractor (pypdf) cannot read a
    scan; OCR is out of scope for v0.1.
    """
    if path.suffix.lower() != ".pdf":
        return False
    import pypdf

    try:
        reader = pypdf.PdfReader(str(path))
    except Exception:
        return False
    if not reader.pages:
        return False
    return any(len(getattr(page, "images", [])) for page in reader.pages)


@corpus_required
def test_every_corpus_file_extracts_text_or_is_image_only():
    walked = list(LocalFolderConnector(CORPUS_DIR).walk())
    unexplained_empties = []
    for p in walked:
        if extract(p).strip():
            continue
        if not _empty_extraction_is_explained(p):
            unexplained_empties.append(str(p))
    assert not unexplained_empties, (
        "files extracted empty text without being image-only PDFs: "
        f"{unexplained_empties}"
    )


@corpus_required
def test_manifest_has_one_hashed_entry_per_corpus_file():
    walked = list(LocalFolderConnector(CORPUS_DIR).walk())
    entries = build_manifest(walked, source_label="corpus-test")
    assert len(entries) == len(walked)
    paths = [e.path for e in entries]
    assert len(set(paths)) == len(paths), "manifest has duplicate paths"
    for e in entries:
        assert len(e.content_hash) == 64, f"not a sha256 hex digest: {e.content_hash}"
        assert all(c in "0123456789abcdef" for c in e.content_hash)
        assert e.source_label == "corpus-test"


@corpus_required
def test_incremental_first_run_all_added_then_second_run_all_unchanged(tmp_path):
    walked = list(LocalFolderConnector(CORPUS_DIR).walk())
    manifest_path = tmp_path / "manifest.json"

    first = plan_incremental_run(CORPUS_DIR, manifest_path, source_label="corpus-test")
    assert len(first.added) == len(walked)
    assert first.changed == []
    assert first.removed == []
    assert len(first.to_process) == len(walked)

    save_manifest(first.current, manifest_path)

    second = plan_incremental_run(CORPUS_DIR, manifest_path, source_label="corpus-test")
    assert second.added == []
    assert second.changed == []
    assert second.removed == []
    assert len(second.unchanged) == len(walked)
    assert second.to_process == []
