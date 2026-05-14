"""Tests for GitHubProvider."""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.git_provider.base import GitProvider
from app.git_provider.github_provider import GitHubProvider


def _fake_config(tmp_path: Path) -> MagicMock:
    cfg = MagicMock()
    cfg.app_id = 1
    cfg.installation_id = 2
    cfg.private_key_path = tmp_path / "key.pem"
    return cfg


def test_github_provider_is_git_provider(tmp_path):
    cfg = _fake_config(tmp_path)
    (tmp_path / "key.pem").write_text("FAKE PEM")
    assert issubclass(GitHubProvider, GitProvider)
    p = GitHubProvider(config=cfg, github_client=MagicMock())
    assert isinstance(p, GitProvider)


def test_constructor_loads_config_by_default(tmp_path):
    fake_cfg = _fake_config(tmp_path)
    (tmp_path / "key.pem").write_text("FAKE PEM")
    with patch("app.git_provider.github_provider.load_github_config", return_value=fake_cfg) as loader:
        p = GitHubProvider(github_client=MagicMock())
    loader.assert_called_once()
    assert p._config is fake_cfg


def test_installation_token_fetched_via_app_auth(tmp_path):
    cfg = _fake_config(tmp_path)
    (tmp_path / "key.pem").write_text("FAKE PEM")
    with patch("app.git_provider.github_provider._build_installation_token", return_value="ghs_fake_token_xyz") as builder:
        p = GitHubProvider(config=cfg, github_client=MagicMock())
        token = p._installation_token()
    assert token == "ghs_fake_token_xyz"
    builder.assert_called_once_with(cfg)


def test_clone_invokes_git_with_tokenized_url(tmp_path):
    cfg = _fake_config(tmp_path)
    (tmp_path / "key.pem").write_text("FAKE PEM")
    with patch("app.git_provider.github_provider._build_installation_token", return_value="ghs_TOK"):
        with patch("app.git_provider.github_provider.subprocess.run") as run:
            run.return_value = MagicMock(returncode=0)
            p = GitHubProvider(config=cfg, github_client=MagicMock())
            p.clone("https://github.com/foo/bar.git", tmp_path / "dest")
    clone_call = run.call_args_list[0]
    cmd = clone_call[0][0]
    assert cmd[0] == "git"
    assert cmd[1] == "clone"
    assert any("x-access-token:ghs_TOK@github.com/foo/bar.git" in part for part in cmd)
    assert str(tmp_path / "dest") in cmd


def test_clone_resets_origin_to_clean_url(tmp_path):
    """Token must not be persisted in the on-disk origin URL."""
    cfg = _fake_config(tmp_path)
    (tmp_path / "key.pem").write_text("FAKE PEM")
    dest = tmp_path / "dest"
    with patch("app.git_provider.github_provider._build_installation_token", return_value="ghs_TOK"):
        with patch("app.git_provider.github_provider.subprocess.run") as run:
            run.return_value = MagicMock(returncode=0)
            p = GitHubProvider(config=cfg, github_client=MagicMock())
            p.clone("https://github.com/foo/bar.git", dest)
    reset_call = run.call_args_list[1]
    assert reset_call[0][0] == [
        "git", "remote", "set-url", "origin", "https://github.com/foo/bar.git"
    ]
    assert reset_call[1]["cwd"] == dest


def test_clone_raises_on_nonzero_exit(tmp_path):
    cfg = _fake_config(tmp_path)
    (tmp_path / "key.pem").write_text("FAKE PEM")
    with patch("app.git_provider.github_provider._build_installation_token", return_value="t"):
        with patch("app.git_provider.github_provider.subprocess.run") as run:
            run.return_value = MagicMock(returncode=128, stderr=b"fatal: repo not found")
            p = GitHubProvider(config=cfg, github_client=MagicMock())
            with pytest.raises(RuntimeError, match="git clone"):
                p.clone("https://github.com/foo/bar.git", tmp_path / "dest")


def test_branch_creates_new_branch_in_working_dir(tmp_path):
    cfg = _fake_config(tmp_path)
    (tmp_path / "key.pem").write_text("FAKE PEM")
    with patch("app.git_provider.github_provider.subprocess.run") as run:
        run.return_value = MagicMock(returncode=0)
        p = GitHubProvider(config=cfg, github_client=MagicMock())
        p.branch("policycodex/draft-foo", tmp_path / "wd")
    args, kwargs = run.call_args
    assert args[0] == ["git", "checkout", "-b", "policycodex/draft-foo"]
    assert kwargs["cwd"] == tmp_path / "wd"


def test_branch_raises_on_nonzero_exit(tmp_path):
    cfg = _fake_config(tmp_path)
    (tmp_path / "key.pem").write_text("FAKE PEM")
    with patch("app.git_provider.github_provider.subprocess.run") as run:
        run.return_value = MagicMock(returncode=128, stderr=b"branch exists")
        p = GitHubProvider(config=cfg, github_client=MagicMock())
        with pytest.raises(RuntimeError, match="git checkout"):
            p.branch("dupe", tmp_path / "wd")


def test_commit_stages_files_then_commits_with_identity(tmp_path):
    cfg = _fake_config(tmp_path)
    (tmp_path / "key.pem").write_text("FAKE PEM")
    wd = tmp_path / "wd"
    files = [Path("policies/hr/onboarding.md"), Path("policies/finance/budget.md")]
    with patch("app.git_provider.github_provider.subprocess.run") as run:
        run.side_effect = [
            MagicMock(returncode=0),
            MagicMock(returncode=0),
            MagicMock(returncode=0),
            MagicMock(returncode=0, stdout=b"abc1234567890\n"),
        ]
        p = GitHubProvider(config=cfg, github_client=MagicMock())
        sha = p.commit(
            message="Update HR onboarding",
            files=files,
            author_name="Pat Editor",
            author_email="pat@diocese-pt.example",
            working_dir=wd,
        )
    assert sha == "abc1234567890"
    add1 = run.call_args_list[0]
    assert add1[0][0] == ["git", "add", "policies/hr/onboarding.md"]
    assert add1[1]["cwd"] == wd
    commit_call = run.call_args_list[2]
    cmd = commit_call[0][0]
    assert cmd[:5] == ["git", "-c", "user.name=Pat Editor", "-c", "user.email=pat@diocese-pt.example"]
    assert "commit" in cmd
    assert "-m" in cmd
    assert "Update HR onboarding" in cmd


def test_commit_raises_on_nonzero_exit(tmp_path):
    cfg = _fake_config(tmp_path)
    (tmp_path / "key.pem").write_text("FAKE PEM")
    with patch("app.git_provider.github_provider.subprocess.run") as run:
        run.side_effect = [MagicMock(returncode=0), MagicMock(returncode=1, stderr=b"nothing to commit")]
        p = GitHubProvider(config=cfg, github_client=MagicMock())
        with pytest.raises(RuntimeError, match="git commit"):
            p.commit("msg", [Path("a.md")], "n", "e", tmp_path / "wd")


def test_push_rewrites_remote_url_with_token(tmp_path):
    cfg = _fake_config(tmp_path)
    (tmp_path / "key.pem").write_text("FAKE PEM")
    wd = tmp_path / "wd"
    with patch("app.git_provider.github_provider._build_installation_token", return_value="ghs_PUSH"):
        with patch("app.git_provider.github_provider.subprocess.run") as run:
            run.side_effect = [
                MagicMock(returncode=0, stdout=b"https://github.com/foo/bar.git\n"),
                MagicMock(returncode=0),
            ]
            p = GitHubProvider(config=cfg, github_client=MagicMock())
            p.push("policycodex/draft-foo", wd)
    push_call = run.call_args_list[1]
    cmd = push_call[0][0]
    assert cmd[0] == "git"
    assert cmd[1] == "push"
    assert any("x-access-token:ghs_PUSH@github.com/foo/bar.git" in c for c in cmd)
    assert "policycodex/draft-foo" in cmd


def test_push_raises_on_nonzero_exit(tmp_path):
    cfg = _fake_config(tmp_path)
    (tmp_path / "key.pem").write_text("FAKE PEM")
    with patch("app.git_provider.github_provider._build_installation_token", return_value="t"):
        with patch("app.git_provider.github_provider.subprocess.run") as run:
            run.side_effect = [
                MagicMock(returncode=0, stdout=b"https://github.com/foo/bar.git\n"),
                MagicMock(returncode=1, stderr=b"rejected"),
            ]
            p = GitHubProvider(config=cfg, github_client=MagicMock())
            with pytest.raises(RuntimeError, match="git push"):
                p.push("br", tmp_path / "wd")


def test_open_pr_uses_repo_from_origin_and_returns_metadata(tmp_path):
    cfg = _fake_config(tmp_path)
    (tmp_path / "key.pem").write_text("FAKE PEM")
    wd = tmp_path / "wd"
    fake_pr = MagicMock(number=42, html_url="https://github.com/foo/bar/pull/42", state="open")
    fake_repo = MagicMock()
    fake_repo.create_pull.return_value = fake_pr
    fake_client = MagicMock()
    fake_client.get_repo.return_value = fake_repo
    with patch("app.git_provider.github_provider.subprocess.run") as run:
        run.return_value = MagicMock(returncode=0, stdout=b"https://github.com/foo/bar.git\n")
        p = GitHubProvider(config=cfg, github_client=fake_client)
        result = p.open_pr(
            title="Draft: policies/hr/onboarding.md",
            body="Opened by PolicyCodex on behalf of Pat Editor",
            head_branch="policycodex/draft-foo",
            base_branch="main",
            working_dir=wd,
        )
    fake_client.get_repo.assert_called_once_with("foo/bar")
    fake_repo.create_pull.assert_called_once_with(
        title="Draft: policies/hr/onboarding.md",
        body="Opened by PolicyCodex on behalf of Pat Editor",
        head="policycodex/draft-foo",
        base="main",
    )
    assert result == {
        "pr_number": 42,
        "url": "https://github.com/foo/bar/pull/42",
        "state": "open",
    }


@pytest.mark.parametrize("pr_state,merged,approvals,expected", [
    ("open", False, 0, "drafted"),
    ("open", False, 1, "reviewed"),
    ("open", False, 3, "reviewed"),
    ("closed", True, 0, "published"),
    ("closed", True, 2, "published"),
    ("closed", False, 0, "closed"),
    ("closed", False, 1, "closed"),
])
def test_read_pr_state_mapping(tmp_path, pr_state, merged, approvals, expected):
    cfg = _fake_config(tmp_path)
    (tmp_path / "key.pem").write_text("FAKE PEM")
    wd = tmp_path / "wd"
    review_mocks = []
    for _ in range(approvals):
        rv = MagicMock(); rv.state = "APPROVED"; review_mocks.append(rv)
    noise = MagicMock(); noise.state = "COMMENTED"
    review_mocks.append(noise)
    fake_pr = MagicMock(state=pr_state, merged=merged)
    fake_pr.get_reviews.return_value = review_mocks
    fake_repo = MagicMock()
    fake_repo.get_pull.return_value = fake_pr
    fake_client = MagicMock()
    fake_client.get_repo.return_value = fake_repo
    with patch("app.git_provider.github_provider.subprocess.run") as run:
        run.return_value = MagicMock(returncode=0, stdout=b"https://github.com/foo/bar.git\n")
        p = GitHubProvider(config=cfg, github_client=fake_client)
        assert p.read_pr_state(123, wd) == expected
    fake_repo.get_pull.assert_called_once_with(123)


def test_build_installation_token_uses_github_integration(tmp_path):
    """Regression guard: re-introducing AppAuth.get_installation_auth(...).token
    would fail this test before failing the smoke."""
    from app.git_provider.github_provider import _build_installation_token

    cfg = MagicMock()
    cfg.app_id = 42
    cfg.installation_id = 99
    cfg.private_key_path = tmp_path / "key.pem"
    (tmp_path / "key.pem").write_text("FAKE PEM CONTENT")

    with patch("app.git_provider.github_provider.Auth") as MockAuth, \
         patch("app.git_provider.github_provider.GithubIntegration") as MockIntegration:
        fake_app_auth = MagicMock()
        MockAuth.AppAuth.return_value = fake_app_auth
        fake_integration = MagicMock()
        MockIntegration.return_value = fake_integration
        fake_access = MagicMock()
        fake_access.token = "ghs_real_token_xyz"
        fake_integration.get_access_token.return_value = fake_access

        token = _build_installation_token(cfg)

    assert token == "ghs_real_token_xyz"
    MockAuth.AppAuth.assert_called_once_with(42, "FAKE PEM CONTENT")
    MockIntegration.assert_called_once_with(auth=fake_app_auth)
    fake_integration.get_access_token.assert_called_once_with(99)


def test_default_client_built_via_get_github_for_installation(tmp_path):
    """Regression guard: the else-branch in __init__ is otherwise only
    exercised by the live smoke."""
    cfg = _fake_config(tmp_path)
    (tmp_path / "key.pem").write_text("FAKE PEM")

    with patch("app.git_provider.github_provider.Auth") as MockAuth, \
         patch("app.git_provider.github_provider.GithubIntegration") as MockIntegration:
        MockAuth.AppAuth.return_value = MagicMock()
        fake_integration = MagicMock()
        MockIntegration.return_value = fake_integration
        fake_client = MagicMock()
        fake_integration.get_github_for_installation.return_value = fake_client

        p = GitHubProvider(config=cfg)

    fake_integration.get_github_for_installation.assert_called_once_with(2)
    assert p._client is fake_client


def test_pull_runs_git_pull_with_tokenized_origin(tmp_path):
    cfg = _fake_config(tmp_path)
    (tmp_path / "key.pem").write_text("FAKE PEM")
    wd = tmp_path / "wd"
    with patch("app.git_provider.github_provider._build_installation_token", return_value="ghs_PULL"):
        with patch("app.git_provider.github_provider.subprocess.run") as run:
            run.side_effect = [
                MagicMock(returncode=0, stdout=b"https://github.com/foo/bar.git\n"),
                MagicMock(returncode=0),
            ]
            p = GitHubProvider(config=cfg, github_client=MagicMock())
            p.pull("main", wd)
    assert run.call_count == 2
    first_call = run.call_args_list[0]
    assert first_call[0][0] == ["git", "remote", "get-url", "origin"]
    second_call = run.call_args_list[1]
    cmd = second_call[0][0]
    assert cmd[0:2] == ["git", "pull"]
    assert any("x-access-token:ghs_PULL@github.com/foo/bar.git" in c for c in cmd)
    assert cmd[-1] == "main"


def test_pull_raises_on_non_github_origin(tmp_path):
    cfg = _fake_config(tmp_path)
    (tmp_path / "key.pem").write_text("FAKE PEM")
    with patch("app.git_provider.github_provider.subprocess.run") as run:
        run.return_value = MagicMock(
            returncode=0, stdout=b"git@github.com:org/repo.git\n"
        )
        p = GitHubProvider(config=cfg, github_client=MagicMock())
        with pytest.raises(ValueError, match="https://github.com/"):
            p.pull("main", tmp_path / "wd")


def test_pull_raises_on_nonzero_exit_and_redacts_token(tmp_path):
    cfg = _fake_config(tmp_path)
    (tmp_path / "key.pem").write_text("FAKE PEM")
    with patch("app.git_provider.github_provider._build_installation_token", return_value="SECRET_TOKEN"):
        with patch("app.git_provider.github_provider.subprocess.run") as run:
            run.side_effect = [
                MagicMock(returncode=0, stdout=b"https://github.com/foo/bar.git\n"),
                MagicMock(returncode=1, stderr=b"fatal: could not read from remote (token=SECRET_TOKEN)"),
            ]
            p = GitHubProvider(config=cfg, github_client=MagicMock())
            with pytest.raises(RuntimeError) as excinfo:
                p.pull("main", tmp_path / "wd")
    msg = str(excinfo.value)
    assert "SECRET_TOKEN" not in msg
    assert "<redacted>" in msg
    assert "git pull" in msg


def test_parse_owner_repo_handles_dots_in_repo_name():
    """Regex must accept dotted repo names (e.g., owner.github.io)."""
    from app.git_provider.github_provider import _parse_owner_repo

    assert _parse_owner_repo("https://github.com/foo/bar") == "foo/bar"
    assert _parse_owner_repo("https://github.com/foo/bar.git") == "foo/bar"
    assert _parse_owner_repo("https://github.com/foo/bar.baz") == "foo/bar.baz"
    assert _parse_owner_repo("https://github.com/foo/bar.baz.git") == "foo/bar.baz"
    assert _parse_owner_repo("https://github.com/owner/owner.github.io") == "owner/owner.github.io"


def test_list_open_prs_empty_when_no_open_prs(tmp_path):
    cfg = _fake_config(tmp_path)
    (tmp_path / "key.pem").write_text("FAKE PEM")
    wd = tmp_path / "wd"
    fake_repo = MagicMock()
    fake_repo.get_pulls.return_value = []
    fake_client = MagicMock()
    fake_client.get_repo.return_value = fake_repo
    with patch("app.git_provider.github_provider.subprocess.run") as run:
        run.return_value = MagicMock(returncode=0, stdout=b"https://github.com/foo/bar.git\n")
        p = GitHubProvider(config=cfg, github_client=fake_client)
        result = p.list_open_prs(wd)
    assert result == []
    fake_repo.get_pulls.assert_called_once_with(state="open")


def test_list_open_prs_returns_one_drafted_pr(tmp_path):
    cfg = _fake_config(tmp_path)
    (tmp_path / "key.pem").write_text("FAKE PEM")
    wd = tmp_path / "wd"
    fake_pr = MagicMock(
        number=42,
        state="open",
        merged=False,
        html_url="https://github.com/foo/bar/pull/42",
    )
    fake_pr.head.ref = "policycodex/draft-onboarding"
    fake_pr.get_reviews.return_value = []
    fake_repo = MagicMock()
    fake_repo.get_pulls.return_value = [fake_pr]
    fake_client = MagicMock()
    fake_client.get_repo.return_value = fake_repo
    with patch("app.git_provider.github_provider.subprocess.run") as run:
        run.return_value = MagicMock(returncode=0, stdout=b"https://github.com/foo/bar.git\n")
        p = GitHubProvider(config=cfg, github_client=fake_client)
        result = p.list_open_prs(wd)
    assert result == [{
        "pr_number": 42,
        "head_branch": "policycodex/draft-onboarding",
        "gate": "drafted",
        "url": "https://github.com/foo/bar/pull/42",
    }]


def test_list_open_prs_marks_approved_pr_as_reviewed(tmp_path):
    cfg = _fake_config(tmp_path)
    (tmp_path / "key.pem").write_text("FAKE PEM")
    wd = tmp_path / "wd"
    approved = MagicMock(); approved.state = "APPROVED"
    commented = MagicMock(); commented.state = "COMMENTED"
    fake_pr = MagicMock(
        number=7,
        state="open",
        merged=False,
        html_url="https://github.com/foo/bar/pull/7",
    )
    fake_pr.head.ref = "policycodex/draft-retention"
    fake_pr.get_reviews.return_value = [commented, approved]
    fake_repo = MagicMock()
    fake_repo.get_pulls.return_value = [fake_pr]
    fake_client = MagicMock()
    fake_client.get_repo.return_value = fake_repo
    with patch("app.git_provider.github_provider.subprocess.run") as run:
        run.return_value = MagicMock(returncode=0, stdout=b"https://github.com/foo/bar.git\n")
        p = GitHubProvider(config=cfg, github_client=fake_client)
        result = p.list_open_prs(wd)
    assert len(result) == 1
    assert result[0]["gate"] == "reviewed"
    assert result[0]["head_branch"] == "policycodex/draft-retention"


def test_list_open_prs_returns_mixed_drafted_and_reviewed(tmp_path):
    cfg = _fake_config(tmp_path)
    (tmp_path / "key.pem").write_text("FAKE PEM")
    wd = tmp_path / "wd"

    pr_drafted = MagicMock(number=1, state="open", merged=False, html_url="u1")
    pr_drafted.head.ref = "policycodex/draft-foo"
    pr_drafted.get_reviews.return_value = []

    approved = MagicMock(); approved.state = "APPROVED"
    pr_reviewed = MagicMock(number=2, state="open", merged=False, html_url="u2")
    pr_reviewed.head.ref = "policycodex/draft-bar"
    pr_reviewed.get_reviews.return_value = [approved]

    fake_repo = MagicMock()
    fake_repo.get_pulls.return_value = [pr_drafted, pr_reviewed]
    fake_client = MagicMock()
    fake_client.get_repo.return_value = fake_repo
    with patch("app.git_provider.github_provider.subprocess.run") as run:
        run.return_value = MagicMock(returncode=0, stdout=b"https://github.com/foo/bar.git\n")
        p = GitHubProvider(config=cfg, github_client=fake_client)
        result = p.list_open_prs(wd)
    gates = {row["head_branch"]: row["gate"] for row in result}
    assert gates == {
        "policycodex/draft-foo": "drafted",
        "policycodex/draft-bar": "reviewed",
    }


def test_list_open_prs_passes_state_open_filter(tmp_path):
    """The library call must filter to state=open at the API layer (not via
    a post-fetch Python filter), to avoid pulling merged/closed history."""
    cfg = _fake_config(tmp_path)
    (tmp_path / "key.pem").write_text("FAKE PEM")
    wd = tmp_path / "wd"
    fake_repo = MagicMock()
    fake_repo.get_pulls.return_value = []
    fake_client = MagicMock()
    fake_client.get_repo.return_value = fake_repo
    with patch("app.git_provider.github_provider.subprocess.run") as run:
        run.return_value = MagicMock(returncode=0, stdout=b"https://github.com/foo/bar.git\n")
        p = GitHubProvider(config=cfg, github_client=fake_client)
        p.list_open_prs(wd)
    fake_repo.get_pulls.assert_called_once_with(state="open")


def test_approve_pr_creates_review_with_approve_event(tmp_path):
    """approve_pr calls Repository.get_pull(N).create_review(event='APPROVE')."""
    cfg = _fake_config(tmp_path)
    (tmp_path / "key.pem").write_text("FAKE PEM")
    wd = tmp_path / "wd"
    fake_review = MagicMock(id=987, state="APPROVED")
    fake_pr = MagicMock(number=42)
    fake_pr.create_review.return_value = fake_review
    fake_repo = MagicMock()
    fake_repo.get_pull.return_value = fake_pr
    fake_client = MagicMock()
    fake_client.get_repo.return_value = fake_repo
    with patch("app.git_provider.github_provider.subprocess.run") as run:
        run.return_value = MagicMock(returncode=0, stdout=b"https://github.com/foo/bar.git\n")
        p = GitHubProvider(config=cfg, github_client=fake_client)
        result = p.approve_pr(pr_number=42, working_dir=wd, body="Looks good.")
    fake_client.get_repo.assert_called_once_with("foo/bar")
    fake_repo.get_pull.assert_called_once_with(42)
    fake_pr.create_review.assert_called_once_with(body="Looks good.", event="APPROVE")
    assert result == {"review_id": 987, "state": "APPROVED", "pr_number": 42}


def test_approve_pr_defaults_body_to_empty_string(tmp_path):
    """When no body is supplied, approve_pr passes body='' to create_review."""
    cfg = _fake_config(tmp_path)
    (tmp_path / "key.pem").write_text("FAKE PEM")
    fake_review = MagicMock(id=1, state="APPROVED")
    fake_pr = MagicMock(number=7)
    fake_pr.create_review.return_value = fake_review
    fake_repo = MagicMock()
    fake_repo.get_pull.return_value = fake_pr
    fake_client = MagicMock()
    fake_client.get_repo.return_value = fake_repo
    with patch("app.git_provider.github_provider.subprocess.run") as run:
        run.return_value = MagicMock(returncode=0, stdout=b"https://github.com/foo/bar.git\n")
        p = GitHubProvider(config=cfg, github_client=fake_client)
        p.approve_pr(pr_number=7, working_dir=tmp_path / "wd")
    fake_pr.create_review.assert_called_once_with(body="", event="APPROVE")


def test_approve_pr_raises_on_origin_lookup_failure(tmp_path):
    """If `git remote get-url origin` fails, approve_pr raises RuntimeError."""
    cfg = _fake_config(tmp_path)
    (tmp_path / "key.pem").write_text("FAKE PEM")
    with patch("app.git_provider.github_provider.subprocess.run") as run:
        run.return_value = MagicMock(returncode=128, stderr=b"not a git repo")
        p = GitHubProvider(config=cfg, github_client=MagicMock())
        with pytest.raises(RuntimeError, match="git remote get-url"):
            p.approve_pr(pr_number=1, working_dir=tmp_path / "wd")


def test_approve_pr_propagates_pygithub_exceptions(tmp_path):
    """If PyGithub raises (e.g., GithubException from create_review), bubble it up."""
    from github import GithubException
    cfg = _fake_config(tmp_path)
    (tmp_path / "key.pem").write_text("FAKE PEM")
    fake_pr = MagicMock()
    fake_pr.create_review.side_effect = GithubException(
        status=403, data={"message": "Resource not accessible by integration"}, headers={}
    )
    fake_repo = MagicMock()
    fake_repo.get_pull.return_value = fake_pr
    fake_client = MagicMock()
    fake_client.get_repo.return_value = fake_repo
    with patch("app.git_provider.github_provider.subprocess.run") as run:
        run.return_value = MagicMock(returncode=0, stdout=b"https://github.com/foo/bar.git\n")
        p = GitHubProvider(config=cfg, github_client=fake_client)
        with pytest.raises(GithubException):
            p.approve_pr(pr_number=1, working_dir=tmp_path / "wd")


def test_merge_pr_calls_pygithub_with_squash_default(tmp_path):
    """merge_pr defaults to merge_method='squash' and returns merge metadata."""
    cfg = _fake_config(tmp_path)
    (tmp_path / "key.pem").write_text("FAKE PEM")
    wd = tmp_path / "wd"
    fake_pr = MagicMock(number=42)
    # PyGithub's pr.merge() returns an object with attrs merged + sha.
    fake_merge_result = MagicMock(merged=True, sha="cafebabe1234")
    fake_pr.merge.return_value = fake_merge_result
    fake_repo = MagicMock()
    fake_repo.get_pull.return_value = fake_pr
    fake_client = MagicMock()
    fake_client.get_repo.return_value = fake_repo
    with patch("app.git_provider.github_provider.subprocess.run") as run:
        run.return_value = MagicMock(returncode=0, stdout=b"https://github.com/foo/bar.git\n")
        p = GitHubProvider(config=cfg, github_client=fake_client)
        result = p.merge_pr(42, wd)
    fake_client.get_repo.assert_called_once_with("foo/bar")
    fake_repo.get_pull.assert_called_once_with(42)
    fake_pr.merge.assert_called_once()
    call_kwargs = fake_pr.merge.call_args.kwargs
    assert call_kwargs["merge_method"] == "squash"
    assert result == {"merged": True, "sha": "cafebabe1234", "merge_method": "squash"}


def test_merge_pr_honors_explicit_merge_method(tmp_path):
    """merge_pr passes through merge_method='merge' or 'rebase' when given."""
    cfg = _fake_config(tmp_path)
    (tmp_path / "key.pem").write_text("FAKE PEM")
    wd = tmp_path / "wd"
    fake_pr = MagicMock()
    fake_pr.merge.return_value = MagicMock(merged=True, sha="abc")
    fake_repo = MagicMock()
    fake_repo.get_pull.return_value = fake_pr
    fake_client = MagicMock()
    fake_client.get_repo.return_value = fake_repo
    with patch("app.git_provider.github_provider.subprocess.run") as run:
        run.return_value = MagicMock(returncode=0, stdout=b"https://github.com/foo/bar.git\n")
        p = GitHubProvider(config=cfg, github_client=fake_client)
        result = p.merge_pr(7, wd, merge_method="rebase")
    assert fake_pr.merge.call_args.kwargs["merge_method"] == "rebase"
    assert result["merge_method"] == "rebase"


def test_merge_pr_rejects_invalid_merge_method(tmp_path):
    """Only merge, squash, rebase are accepted; anything else raises ValueError."""
    cfg = _fake_config(tmp_path)
    (tmp_path / "key.pem").write_text("FAKE PEM")
    p = GitHubProvider(config=cfg, github_client=MagicMock())
    with pytest.raises(ValueError, match="merge_method"):
        p.merge_pr(1, tmp_path / "wd", merge_method="fast-forward")


def test_merge_pr_raises_runtime_error_on_github_exception(tmp_path):
    """A PyGithub GithubException (e.g. 409 merge conflict) becomes RuntimeError."""
    from github import GithubException
    cfg = _fake_config(tmp_path)
    (tmp_path / "key.pem").write_text("FAKE PEM")
    wd = tmp_path / "wd"
    fake_pr = MagicMock()
    fake_pr.merge.side_effect = GithubException(
        status=409, data={"message": "Merge conflict"}, headers=None
    )
    fake_repo = MagicMock()
    fake_repo.get_pull.return_value = fake_pr
    fake_client = MagicMock()
    fake_client.get_repo.return_value = fake_repo
    with patch("app.git_provider.github_provider.subprocess.run") as run:
        run.return_value = MagicMock(returncode=0, stdout=b"https://github.com/foo/bar.git\n")
        p = GitHubProvider(config=cfg, github_client=fake_client)
        with pytest.raises(RuntimeError, match="merge.*409|Merge conflict"):
            p.merge_pr(42, wd)


def test_merge_pr_raises_runtime_error_on_branch_protection_block(tmp_path):
    """Branch protection failures surface 405 with a Method Not Allowed message."""
    from github import GithubException
    cfg = _fake_config(tmp_path)
    (tmp_path / "key.pem").write_text("FAKE PEM")
    wd = tmp_path / "wd"
    fake_pr = MagicMock()
    fake_pr.merge.side_effect = GithubException(
        status=405,
        data={"message": "Required status check has not succeeded"},
        headers=None,
    )
    fake_repo = MagicMock()
    fake_repo.get_pull.return_value = fake_pr
    fake_client = MagicMock()
    fake_client.get_repo.return_value = fake_repo
    with patch("app.git_provider.github_provider.subprocess.run") as run:
        run.return_value = MagicMock(returncode=0, stdout=b"https://github.com/foo/bar.git\n")
        p = GitHubProvider(config=cfg, github_client=fake_client)
        with pytest.raises(RuntimeError, match="405|status check"):
            p.merge_pr(42, wd)


def test_merge_pr_raises_when_pr_already_merged(tmp_path):
    """If pr.merge() returns merged=False, surface a RuntimeError so callers don't
    silently report success. GitHub's API can return merged=False with a reason
    string when, e.g., the head SHA changed between read and merge."""
    cfg = _fake_config(tmp_path)
    (tmp_path / "key.pem").write_text("FAKE PEM")
    wd = tmp_path / "wd"
    fake_pr = MagicMock()
    fake_pr.merge.return_value = MagicMock(merged=False, sha=None)
    fake_repo = MagicMock()
    fake_repo.get_pull.return_value = fake_pr
    fake_client = MagicMock()
    fake_client.get_repo.return_value = fake_repo
    with patch("app.git_provider.github_provider.subprocess.run") as run:
        run.return_value = MagicMock(returncode=0, stdout=b"https://github.com/foo/bar.git\n")
        p = GitHubProvider(config=cfg, github_client=fake_client)
        with pytest.raises(RuntimeError, match="not merged"):
            p.merge_pr(42, wd)
