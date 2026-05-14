"""Tests for GitProvider abstract base class."""
import pytest
from pathlib import Path
from app.git_provider.base import GitProvider


class TestGitProviderAbstractClass:
    """Verify GitProvider cannot be instantiated directly."""

    def test_cannot_instantiate_abstract_class(self):
        """Attempting to instantiate GitProvider directly raises TypeError."""
        with pytest.raises(TypeError):
            GitProvider()


class TestGitProviderSubclassMissingMethods:
    """Verify subclasses must implement all abstract methods."""

    def test_subclass_missing_clone_fails(self):
        """Subclass missing clone() cannot instantiate."""
        class IncompleteProvider(GitProvider):
            def branch(self, name: str, working_dir: Path) -> None:
                pass
            def commit(self, message: str, files: list[Path], author_name: str, author_email: str, working_dir: Path) -> str:
                pass
            def push(self, branch: str, working_dir: Path) -> None:
                pass
            def pull(self, branch: str, working_dir: Path) -> None:
                pass
            def open_pr(self, title: str, body: str, head_branch: str, base_branch: str, working_dir: Path) -> dict:
                pass
            def read_pr_state(self, pr_number: int, working_dir: Path) -> str:
                pass

        with pytest.raises(TypeError):
            IncompleteProvider()

    def test_subclass_missing_branch_fails(self):
        """Subclass missing branch() cannot instantiate."""
        class IncompleteProvider(GitProvider):
            def clone(self, repo_url: str, dest: Path) -> None:
                pass
            def commit(self, message: str, files: list[Path], author_name: str, author_email: str, working_dir: Path) -> str:
                pass
            def push(self, branch: str, working_dir: Path) -> None:
                pass
            def pull(self, branch: str, working_dir: Path) -> None:
                pass
            def open_pr(self, title: str, body: str, head_branch: str, base_branch: str, working_dir: Path) -> dict:
                pass
            def read_pr_state(self, pr_number: int, working_dir: Path) -> str:
                pass

        with pytest.raises(TypeError):
            IncompleteProvider()

    def test_subclass_missing_commit_fails(self):
        """Subclass missing commit() cannot instantiate."""
        class IncompleteProvider(GitProvider):
            def clone(self, repo_url: str, dest: Path) -> None:
                pass
            def branch(self, name: str, working_dir: Path) -> None:
                pass
            def push(self, branch: str, working_dir: Path) -> None:
                pass
            def pull(self, branch: str, working_dir: Path) -> None:
                pass
            def open_pr(self, title: str, body: str, head_branch: str, base_branch: str, working_dir: Path) -> dict:
                pass
            def read_pr_state(self, pr_number: int, working_dir: Path) -> str:
                pass

        with pytest.raises(TypeError):
            IncompleteProvider()

    def test_subclass_missing_push_fails(self):
        """Subclass missing push() cannot instantiate."""
        class IncompleteProvider(GitProvider):
            def clone(self, repo_url: str, dest: Path) -> None:
                pass
            def branch(self, name: str, working_dir: Path) -> None:
                pass
            def commit(self, message: str, files: list[Path], author_name: str, author_email: str, working_dir: Path) -> str:
                pass
            def pull(self, branch: str, working_dir: Path) -> None:
                pass
            def open_pr(self, title: str, body: str, head_branch: str, base_branch: str, working_dir: Path) -> dict:
                pass
            def read_pr_state(self, pr_number: int, working_dir: Path) -> str:
                pass

        with pytest.raises(TypeError):
            IncompleteProvider()

    def test_subclass_missing_pull_fails(self):
        """Subclass missing pull() cannot instantiate."""
        class IncompleteProvider(GitProvider):
            def clone(self, repo_url: str, dest: Path) -> None:
                pass
            def branch(self, name: str, working_dir: Path) -> None:
                pass
            def commit(self, message: str, files: list[Path], author_name: str, author_email: str, working_dir: Path) -> str:
                pass
            def push(self, branch: str, working_dir: Path) -> None:
                pass
            def open_pr(self, title: str, body: str, head_branch: str, base_branch: str, working_dir: Path) -> dict:
                pass
            def read_pr_state(self, pr_number: int, working_dir: Path) -> str:
                pass

        with pytest.raises(TypeError):
            IncompleteProvider()

    def test_subclass_missing_open_pr_fails(self):
        """Subclass missing open_pr() cannot instantiate."""
        class IncompleteProvider(GitProvider):
            def clone(self, repo_url: str, dest: Path) -> None:
                pass
            def branch(self, name: str, working_dir: Path) -> None:
                pass
            def commit(self, message: str, files: list[Path], author_name: str, author_email: str, working_dir: Path) -> str:
                pass
            def push(self, branch: str, working_dir: Path) -> None:
                pass
            def pull(self, branch: str, working_dir: Path) -> None:
                pass
            def read_pr_state(self, pr_number: int, working_dir: Path) -> str:
                pass

        with pytest.raises(TypeError):
            IncompleteProvider()

    def test_subclass_missing_read_pr_state_fails(self):
        """Subclass missing read_pr_state() cannot instantiate."""
        class IncompleteProvider(GitProvider):
            def clone(self, repo_url: str, dest: Path) -> None:
                pass
            def branch(self, name: str, working_dir: Path) -> None:
                pass
            def commit(self, message: str, files: list[Path], author_name: str, author_email: str, working_dir: Path) -> str:
                pass
            def push(self, branch: str, working_dir: Path) -> None:
                pass
            def pull(self, branch: str, working_dir: Path) -> None:
                pass
            def open_pr(self, title: str, body: str, head_branch: str, base_branch: str, working_dir: Path) -> dict:
                pass

        with pytest.raises(TypeError):
            IncompleteProvider()
