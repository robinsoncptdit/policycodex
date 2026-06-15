"""Tests for the propose sequence + clean-tree guarantees (APP-33)."""
import subprocess
import threading
import time
from pathlib import Path

import pytest

from app.git_provider.propose import propose_change


def _git(args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


def _current_branch(wd):
    return _git(["rev-parse", "--abbrev-ref", "HEAD"], wd).stdout.strip()


def _is_clean(wd):
    return _git(["status", "--porcelain"], wd).stdout.strip() == ""


def _branches(wd):
    return set(_git(["branch", "--format=%(refname:short)"], wd).stdout.split())


@pytest.fixture
def repo(tmp_path):
    """A real git repo on `main` with one committed policy file."""
    wd = tmp_path / "wc"
    wd.mkdir()
    _git(["init", "-b", "main"], wd)
    _git(["config", "user.email", "t@example.com"], wd)
    _git(["config", "user.name", "T"], wd)
    (wd / "policies").mkdir()
    (wd / "policies" / "safety.md").write_text("original\n", encoding="utf-8")
    _git(["add", "."], wd)
    _git(["commit", "-m", "init"], wd)
    return wd


class _LocalGitProvider:
    """branch/commit run real local git; push/open_pr are stubs.

    `fail_at` raises at the named step to drive the failure paths.
    """

    def __init__(self, fail_at=None):
        self.fail_at = fail_at

    def _maybe_fail(self, step):
        if self.fail_at == step:
            raise RuntimeError(f"boom at {step}")

    def branch(self, name, working_dir):
        self._maybe_fail("branch")
        assert _git(["checkout", "-b", name], working_dir).returncode == 0

    def commit(self, *, message, files, author_name, author_email, working_dir):
        self._maybe_fail("commit")
        for f in files:
            assert _git(["add", str(f)], working_dir).returncode == 0
        assert _git(["commit", "-m", message], working_dir).returncode == 0
        return "deadbeef"

    def push(self, branch, working_dir):
        self._maybe_fail("push")

    def open_pr(self, *, title, body, head_branch, base_branch, working_dir):
        self._maybe_fail("open_pr")
        return {"pr_number": 7, "url": "https://github.com/d/r/pull/7", "state": "open"}


def _propose(repo, provider, files):
    return propose_change(
        provider=provider,
        working_dir=repo,
        default_branch="main",
        branch_name="policycodex/edit-safety-abc12345",
        files=files,
        commit_message="Update safety",
        author_name="Pat Editor",
        author_email="pat@example.com",
        pr_title="Edit policies/safety: Update safety",
        pr_body="body",
    )


def test_success_returns_pr_and_ends_clean_on_default(repo):
    (repo / "policies" / "safety.md").write_text("edited\n", encoding="utf-8")
    pr = _propose(repo, _LocalGitProvider(), [repo / "policies" / "safety.md"])
    assert pr["pr_number"] == 7
    assert _current_branch(repo) == "main"
    assert _is_clean(repo)
    assert "policycodex/edit-safety-abc12345" not in _branches(repo)


def test_failure_at_push_restores_tracked_file_and_branch(repo):
    target = repo / "policies" / "safety.md"
    target.write_text("edited\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="boom at push"):
        _propose(repo, _LocalGitProvider(fail_at="push"), [target])
    assert _current_branch(repo) == "main"
    assert _is_clean(repo)
    assert target.read_text(encoding="utf-8") == "original\n"
    assert "policycodex/edit-safety-abc12345" not in _branches(repo)


def test_failure_at_open_pr_after_commit_still_restores(repo):
    target = repo / "policies" / "safety.md"
    target.write_text("edited\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="boom at open_pr"):
        _propose(repo, _LocalGitProvider(fail_at="open_pr"), [target])
    assert _current_branch(repo) == "main"
    assert _is_clean(repo)
    assert target.read_text(encoding="utf-8") == "original\n"


def test_failure_at_branch_restores_dirty_main(repo):
    target = repo / "policies" / "safety.md"
    target.write_text("edited\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="boom at branch"):
        _propose(repo, _LocalGitProvider(fail_at="branch"), [target])
    assert _current_branch(repo) == "main"
    assert _is_clean(repo)
    assert target.read_text(encoding="utf-8") == "original\n"


def test_failure_removes_untracked_created_paths(repo):
    """The onboarding shape: a new config file + a new bundle directory."""
    config = repo / ".policycodex" / "config.yaml"
    config.parent.mkdir()
    config.write_text("schema_version: 1\n", encoding="utf-8")
    bundle = repo / "policies" / "document-retention"
    bundle.mkdir()
    (bundle / "policy.md").write_text("x\n", encoding="utf-8")
    (bundle / "data.yaml").write_text("classifications: []\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="boom at push"):
        _propose(repo, _LocalGitProvider(fail_at="push"), [config, bundle])
    assert _current_branch(repo) == "main"
    assert _is_clean(repo)
    assert not config.exists()
    assert not bundle.exists()


def test_recovers_when_starting_on_a_stale_feature_branch(repo):
    """Crash recovery: a previous run died mid-sequence and left the copy
    on a feature branch. propose_change checks out the default first."""
    _git(["checkout", "-b", "policycodex/edit-old-dead0000"], repo)
    (repo / "policies" / "safety.md").write_text("edited\n", encoding="utf-8")
    pr = _propose(repo, _LocalGitProvider(), [repo / "policies" / "safety.md"])
    assert pr["pr_number"] == 7
    assert _current_branch(repo) == "main"
    assert _is_clean(repo)


# --- Cross-process working-copy lock (concurrent saves on one shared copy) ---


def test_working_copy_lock_serializes_across_threads(tmp_path):
    """The app runs gunicorn --workers 3 against one working copy. The lock must
    give mutual exclusion so two saves never mutate the same .git at once."""
    from app.git_provider.propose import working_copy_lock
    wd = tmp_path / "wc"
    wd.mkdir()
    state = {"inside": 0, "max_inside": 0}
    state_guard = threading.Lock()

    def worker():
        with working_copy_lock(wd):
            with state_guard:
                state["inside"] += 1
                state["max_inside"] = max(state["max_inside"], state["inside"])
            time.sleep(0.05)
            with state_guard:
                state["inside"] -= 1

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert state["max_inside"] == 1, "two workers held the working-copy lock at once"


def test_concurrent_untracked_saves_serialize_and_both_succeed(repo):
    """Regression: a config save writes a NEW untracked file then proposes.
    Two overlapping saves used to race — worker A's checkout-back removed the
    file before worker B's git add, yielding 'pathspec did not match'. With the
    lock wrapping write+propose, both serialize and succeed."""
    from app.git_provider.propose import working_copy_lock
    cfg = repo / ".policycodex" / "config.yaml"
    results, errors = {}, {}

    def save(idx):
        try:
            with working_copy_lock(repo):
                cfg.parent.mkdir(parents=True, exist_ok=True)
                cfg.write_text(f"version: {idx}\n", encoding="utf-8")
                results[idx] = propose_change(
                    provider=_LocalGitProvider(),
                    working_dir=repo,
                    default_branch="main",
                    branch_name=f"policycodex/config-{idx}",
                    files=[cfg],
                    commit_message=f"config {idx}",
                    author_name="P", author_email="p@e.com",
                    pr_title=f"t{idx}", pr_body="b",
                )
        except Exception as exc:  # noqa: BLE001
            errors[idx] = repr(exc)

    threads = [threading.Thread(target=save, args=(i,)) for i in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == {}, errors
    assert set(results) == {0, 1}
    assert _current_branch(repo) == "main"
    assert _is_clean(repo)
