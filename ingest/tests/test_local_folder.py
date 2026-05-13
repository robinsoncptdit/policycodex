"""Tests for LocalFolderConnector."""
from pathlib import Path

import pytest

from ingest.local_folder import LocalFolderConnector


def test_walk_yields_files_in_flat_dir(tmp_path):
    (tmp_path / "a.txt").write_text("a")
    (tmp_path / "b.pdf").write_bytes(b"%PDF")
    (tmp_path / "c.docx").write_bytes(b"docx")
    result = sorted(p.name for p in LocalFolderConnector(tmp_path).walk())
    assert result == ["a.txt", "b.pdf", "c.docx"]


def test_walk_recurses_into_subdirs(tmp_path):
    (tmp_path / "top.md").write_text("top")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "mid.md").write_text("mid")
    deep = sub / "deeper"
    deep.mkdir()
    (deep / "low.md").write_text("low")
    result = sorted(p.relative_to(tmp_path).as_posix() for p in LocalFolderConnector(tmp_path).walk())
    assert result == ["sub/deeper/low.md", "sub/mid.md", "top.md"]
