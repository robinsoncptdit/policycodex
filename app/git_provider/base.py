"""Abstract base class for Git provider implementations."""
from abc import ABC, abstractmethod
from pathlib import Path


class GitProvider(ABC):
    """Abstract interface for Git operations across multiple providers.

    Implementations of this interface handle Git operations for GitHub,
    GitHub Enterprise, GitLab, Gitea, and other Git-based services.

    State mapping per PolicyWonk spec:
    - Drafted: Policy is in open PR on Git provider
    - Reviewed: PR has been approved (review status varies by provider)
    - Published: PR has been merged to main branch
    - Closed: PR was closed without merge
    """

    @abstractmethod
    def clone(self, repo_url: str, dest: Path) -> None:
        """Clone a repository to the specified destination.

        Args:
            repo_url: The repository URL to clone.
            dest: Local filesystem path where repository will be cloned.
        """
        pass

    @abstractmethod
    def branch(self, name: str, working_dir: Path) -> None:
        """Create a new branch in the working directory.

        Args:
            name: Name of the branch to create.
            working_dir: Path to the repository working directory.
        """
        pass

    @abstractmethod
    def commit(self, message: str, files: list[Path], author_name: str, author_email: str, working_dir: Path) -> str:
        """Commit specified files with the given message.

        Args:
            message: Commit message.
            files: List of file paths to include in commit (relative to working_dir).
            author_name: Name of the commit author.
            author_email: Email of the commit author.
            working_dir: Path to the repository working directory.

        Returns:
            The commit SHA.
        """
        pass

    @abstractmethod
    def push(self, branch: str, working_dir: Path) -> None:
        """Push a branch to the remote repository.

        Args:
            branch: Name of the branch to push.
            working_dir: Path to the repository working directory.
        """
        pass

    @abstractmethod
    def pull(self, branch: str, working_dir: Path) -> None:
        """Pull the latest commits for the given branch into the working directory.

        Args:
            branch: Name of the branch to pull (typically the default branch).
            working_dir: Path to the cloned repository working directory.
        """
        pass

    @abstractmethod
    def open_pr(self, title: str, body: str, head_branch: str, base_branch: str, working_dir: Path) -> dict:
        """Open a pull request.

        Args:
            title: Title of the pull request.
            body: Description/body of the pull request.
            head_branch: Source branch for the pull request.
            base_branch: Target branch for the pull request (typically 'main').
            working_dir: Path to the repository working directory.

        Returns:
            Dictionary containing PR metadata (at minimum: pr_number, url, state).
        """
        pass

    @abstractmethod
    def read_pr_state(self, pr_number: int, working_dir: Path) -> str:
        """Read the current state of a pull request.

        Args:
            pr_number: The pull request number.
            working_dir: Path to the repository working directory.

        Returns:
            One of: "drafted", "reviewed", "published", "closed"
        """
        pass
