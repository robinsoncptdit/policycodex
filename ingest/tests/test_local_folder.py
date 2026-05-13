"""Tests for LocalFolderConnector."""
import re
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


def test_walk_skips_hidden_files(tmp_path):
    (tmp_path / "visible.txt").write_text("v")
    (tmp_path / ".hidden.txt").write_text("h")
    result = sorted(p.name for p in LocalFolderConnector(tmp_path).walk())
    assert result == ["visible.txt"]


def test_walk_skips_files_inside_hidden_dirs(tmp_path):
    (tmp_path / "ok.txt").write_text("ok")
    hidden_dir = tmp_path / ".hidden_dir"
    hidden_dir.mkdir()
    (hidden_dir / "secret.txt").write_text("nope")
    nested_visible = hidden_dir / "visible_inside_hidden.txt"
    nested_visible.write_text("still nope")
    result = sorted(p.name for p in LocalFolderConnector(tmp_path).walk())
    assert result == ["ok.txt"]


def test_walk_does_not_follow_symlinks(tmp_path):
    real = tmp_path / "real.txt"
    real.write_text("real content")
    link = tmp_path / "link_to_real.txt"
    link.symlink_to(real)
    result = sorted(p.name for p in LocalFolderConnector(tmp_path).walk())
    assert result == ["real.txt"]


def test_walk_does_not_descend_into_dir_symlinks(tmp_path):
    """Dir-symlinks must not have their contents yielded as resolved files.

    Verified safe across Python 3.11, 3.13, 3.14 (3.11 proxies 3.12,
    which we can't install locally; 3.13+ made `recurse_symlinks=False`
    the explicit default for `Path.rglob`).
    """
    real_dir = tmp_path / "real_dir"
    real_dir.mkdir()
    (real_dir / "inside.txt").write_text("real content")
    link_to_dir = tmp_path / "link_to_dir"
    link_to_dir.symlink_to(real_dir)
    (tmp_path / "regular.txt").write_text("regular")
    result = sorted(
        p.relative_to(tmp_path).as_posix()
        for p in LocalFolderConnector(tmp_path).walk()
    )
    assert result == ["real_dir/inside.txt", "regular.txt"]


def test_walk_raises_filenotfound_on_missing_root(tmp_path):
    missing = tmp_path / "does_not_exist"
    with pytest.raises(FileNotFoundError, match=re.escape(str(missing))):
        list(LocalFolderConnector(missing).walk())


def test_walk_raises_notadirectory_on_file_root(tmp_path):
    f = tmp_path / "iam_a_file.txt"
    f.write_text("x")
    with pytest.raises(NotADirectoryError, match=re.escape(str(f))):
        list(LocalFolderConnector(f).walk())


def test_walk_raises_runtimeerror_on_empty_dir(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(RuntimeError, match=re.escape(str(empty))):
        list(LocalFolderConnector(empty).walk())


def test_walk_raises_runtimeerror_when_only_hidden_entries(tmp_path):
    """A dir that yields zero non-hidden files is treated as empty per the spec."""
    only_hidden = tmp_path / "only_hidden"
    only_hidden.mkdir()
    (only_hidden / ".dotfile").write_text("h")
    with pytest.raises(RuntimeError, match=re.escape(str(only_hidden))):
        list(LocalFolderConnector(only_hidden).walk())
