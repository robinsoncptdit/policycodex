"""Branch -> commit -> push -> open PR, leaving the working copy clean (APP-33).

Every app write path (policy edit, foundational edit, onboarding finalize)
funnels through propose_change so a provider failure can never strand modified
files on the default branch, and a success can never strand the working copy
on the feature branch (which would wedge the next sync pull once the PR merges
and the remote branch is deleted).

Local tree hygiene (checkout, per-path restore, local branch delete) is generic
git, identical for every provider, so it lives here rather than on the
GitProvider interface.
"""
from __future__ import annotations

import fcntl
import logging
import shutil
import subprocess
from contextlib import contextmanager
from pathlib import Path

logger = logging.getLogger(__name__)


@contextmanager
def working_copy_lock(working_dir: Path):
    """Serialize all mutations of one shared working copy across processes.

    The app runs gunicorn with multiple workers against a SINGLE working copy.
    Every write path (config save, policy edit, foundational edit, inventory
    finalize) must hold this lock around BOTH its file writes AND propose_change
    -- not just the git body. Otherwise two concurrent saves race on the same
    .git: while worker A is between writing its file and `git add`, worker B's
    checkout / restore yanks the file out, producing
    "pathspec '<file>' did not match any files" (plus index.lock and
    branch-already-exists contention). Locking only propose_change is NOT enough
    -- A's checkout-back to the default branch removes the just-committed file
    from the tree, so B must re-write it inside the same locked region.

    fcntl.flock is advisory, POSIX, and released automatically if the process
    dies. The lockfile is a sibling of the working copy (never inside it, so it
    is never committed). The lock is NOT acquired inside propose_change to avoid
    a self-deadlock when a caller already holds it.
    """
    lock_path = working_dir.parent / f".{working_dir.name}.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = open(lock_path, "w")
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        fd.close()


def _git(args: list[str], working_dir: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=working_dir, capture_output=True)


def _is_tracked(path: Path, working_dir: Path) -> bool:
    return _git(
        ["ls-files", "--error-unmatch", str(path)], working_dir
    ).returncode == 0


def _restore_clean_default(
    working_dir: Path, default_branch: str, files, branch_name: str
) -> None:
    """Best-effort: return to the default branch with a clean tree. Never raises."""
    _git(["checkout", default_branch], working_dir)
    for f in files:
        path = Path(f)
        if _is_tracked(path, working_dir):
            _git(["checkout", "--", str(path)], working_dir)
            if path.is_dir():
                # A scaffold over an already-tracked bundle can leave new
                # untracked files inside; scope the clean to that directory.
                _git(["clean", "-fd", "--", str(path)], working_dir)
        elif path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        elif path.exists():
            path.unlink(missing_ok=True)
    _git(["branch", "-D", branch_name], working_dir)


def propose_change(
    *,
    provider,
    working_dir: Path,
    default_branch: str,
    branch_name: str,
    files: list[Path],
    commit_message: str,
    author_name: str,
    author_email: str,
    pr_title: str,
    pr_body: str,
) -> dict:
    """Run branch -> commit -> push -> open_pr; guarantee a clean default branch.

    On success returns the provider's PR metadata dict with the working copy
    back on `default_branch` and the local feature branch deleted (its commit
    is on the remote). On ANY failure, restores a clean default branch
    (tracked files reverted, untracked created paths removed, local branch
    deleted) and re-raises; callers re-render their form so nothing is lost.
    """
    try:
        # Crash recovery: a previous run killed mid-sequence may have left the
        # copy on a feature branch. No-op when already on the default branch.
        start = _git(["checkout", default_branch], working_dir)
        if start.returncode != 0:
            raise RuntimeError(
                f"could not check out {default_branch} before proposing: "
                f"{start.stderr.decode(errors='replace')}"
            )
        provider.branch(branch_name, working_dir)
        provider.commit(
            message=commit_message,
            files=list(files),
            author_name=author_name,
            author_email=author_email,
            working_dir=working_dir,
        )
        provider.push(branch_name, working_dir)
        pr = provider.open_pr(
            title=pr_title,
            body=pr_body,
            head_branch=branch_name,
            base_branch=default_branch,
            working_dir=working_dir,
        )
    except Exception:
        _restore_clean_default(working_dir, default_branch, files, branch_name)
        raise
    back = _git(["checkout", default_branch], working_dir)
    if back.returncode != 0:
        # The PR exists; do not fail the user's success. The next
        # propose_change self-heals via the crash-recovery checkout above.
        logger.error(
            "propose_change: checkout back to %s failed after opening PR: %s",
            default_branch,
            back.stderr.decode(errors="replace"),
        )
        return pr
    _git(["branch", "-D", branch_name], working_dir)
    return pr
