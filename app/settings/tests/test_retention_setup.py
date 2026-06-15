"""Upload -> extract -> PR orchestration for the document-retention bundle."""
import subprocess
from pathlib import Path

import pytest


def _git(args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path):
    """A real git repo on main with an empty policies/ dir."""
    wd = tmp_path / "wc"
    wd.mkdir()
    _git(["init", "-b", "main"], wd)
    _git(["config", "user.email", "t@e.com"], wd)
    _git(["config", "user.name", "T"], wd)
    (wd / "policies").mkdir()
    (wd / "policies" / ".gitkeep").write_text("", encoding="utf-8")
    _git(["add", "."], wd)
    _git(["commit", "-m", "init"], wd)
    return wd


class _StubProvider:
    """branch/commit run real local git; push/open_pr are stubs."""
    def branch(self, name, working_dir):
        assert _git(["checkout", "-b", name], working_dir).returncode == 0
    def commit(self, *, message, files, author_name, author_email, working_dir):
        for f in files:
            assert _git(["add", str(f)], working_dir).returncode == 0
        assert _git(["commit", "-m", message], working_dir).returncode == 0
        return "sha"
    def push(self, branch, working_dir):
        pass
    def open_pr(self, *, title, body, head_branch, base_branch, working_dir):
        return {"url": "https://github.com/d/r/pull/9", "pr_number": 9, "state": "open"}


_BUNDLE = {
    "classifications": [{"id": "financial", "name": "Financial"}],
    "retention_schedule": [{"group": "Finance", "type": "Ledger", "retention": "Permanent"}],
}


def test_scaffold_writes_both_files_and_proposes(repo):
    from app.settings.retention_setup import scaffold_retention_bundle, RETENTION_SLUG
    committed = {}

    class _CaptureProvider(_StubProvider):
        def commit(self, *, message, files, author_name, author_email, working_dir):
            # Record the files handed to commit. Do NOT assert via `git log` here:
            # propose_change deletes the local feature branch on success
            # (propose.py) and the stub push is a no-op, so the commit is
            # unreachable and invisible to `git log --all`.
            committed["files"] = [str(f) for f in files]
            return super().commit(message=message, files=files, author_name=author_name,
                                  author_email=author_email, working_dir=working_dir)

    pr = scaffold_retention_bundle(
        document_path=Path("ignored.txt"),
        working_dir=repo,
        default_branch="main",
        llm_provider=object(),
        provider=_CaptureProvider(),
        author_name="Pat", author_email="pat@e.com",
        extract_text=lambda p: "some retention policy text",
        extract_bundle=lambda prov, text: _BUNDLE,
    )
    assert pr["pr_number"] == 9
    # Both bundle files were written and handed to the commit.
    assert any(f.endswith(f"policies/{RETENTION_SLUG}/policy.md") for f in committed["files"])
    assert any(f.endswith(f"policies/{RETENTION_SLUG}/data.yaml") for f in committed["files"])
    # propose_change restores the working copy to a clean default branch.
    assert _git(["rev-parse", "--abbrev-ref", "HEAD"], repo).stdout.strip() == "main"


def test_scaffold_policy_md_has_foundational_frontmatter(repo):
    from app.settings.retention_setup import scaffold_retention_bundle, RETENTION_SLUG
    captured = {}

    class _Capture(_StubProvider):
        def commit(self, *, message, files, author_name, author_email, working_dir):
            # Read the files while they are still on disk (pre checkout-back).
            captured["policy_md"] = (working_dir / "policies" / RETENTION_SLUG / "policy.md").read_text()
            captured["data_yaml"] = (working_dir / "policies" / RETENTION_SLUG / "data.yaml").read_text()
            return super().commit(message=message, files=files, author_name=author_name,
                                  author_email=author_email, working_dir=working_dir)

    scaffold_retention_bundle(
        document_path=Path("x.txt"), working_dir=repo, default_branch="main",
        llm_provider=object(), provider=_Capture(), author_name="P", author_email="p@e.com",
        extract_text=lambda t: "text", extract_bundle=lambda prov, t: _BUNDLE,
    )
    assert "foundational: true" in captured["policy_md"]
    assert "- classifications" in captured["policy_md"]
    assert "- retention-schedule" in captured["policy_md"]
    assert "classifications:" in captured["data_yaml"]
    assert "retention_schedule:" in captured["data_yaml"]


def test_scaffold_raises_on_empty_document_text(repo):
    from app.settings.retention_setup import scaffold_retention_bundle
    from ai.retention_extract import RetentionExtractionError
    with pytest.raises(RetentionExtractionError):
        scaffold_retention_bundle(
            document_path=Path("x.txt"), working_dir=repo, default_branch="main",
            llm_provider=object(), provider=_StubProvider(),
            author_name="P", author_email="p@e.com",
            extract_text=lambda p: "   ",
            extract_bundle=lambda prov, t: _BUNDLE,
        )


def test_scaffold_extracts_real_txt(repo, tmp_path):
    """The default extract_text path runs ingest.extractors on a real .txt."""
    from app.settings.retention_setup import scaffold_retention_bundle
    doc = tmp_path / "retention.txt"
    doc.write_text("Records retention policy body.", encoding="utf-8")
    pr = scaffold_retention_bundle(
        document_path=doc, working_dir=repo, default_branch="main",
        llm_provider=object(), provider=_StubProvider(),
        author_name="P", author_email="p@e.com",
        extract_bundle=lambda prov, t: _BUNDLE,  # stub the LLM only
    )
    assert pr["pr_number"] == 9
