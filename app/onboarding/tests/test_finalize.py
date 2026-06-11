"""Unit tests for onboarding finalization (APP-16)."""
from unittest.mock import patch

import yaml

from app.onboarding.finalize import build_config_yaml
from app.onboarding.finalize import make_onboarding_branch_name, write_config_file


def test_build_config_yaml_emits_steps_in_wizard_order():
    all_data = {
        # Deliberately out of wizard order; output must be re-ordered.
        "configuration": {"address_scheme": "chapter-section-item"},
        "github-repo": {"mode": "connect", "repo_url": "https://github.com/d/r", "branch": "main"},
    }
    doc = yaml.safe_load(build_config_yaml(all_data))
    assert doc["schema_version"] == 1
    # github-repo is index 3, configuration is index 4 in DISC-03 STEPS order.
    assert list(doc["onboarding"].keys()) == ["github-repo", "configuration"]
    assert doc["onboarding"]["github-repo"]["repo_url"] == "https://github.com/d/r"


def test_build_config_yaml_excludes_secret_fields():
    all_data = {"llm-provider": {"provider": "claude", "api_key": "sk-x", "auth_token": "t"}}
    doc = yaml.safe_load(build_config_yaml(all_data))
    assert doc["onboarding"]["llm-provider"] == {"provider": "claude"}


def test_build_config_yaml_omits_steps_not_in_data():
    doc = yaml.safe_load(build_config_yaml({}))
    assert doc["onboarding"] == {}


def test_write_config_file_creates_dir_and_returns_path(tmp_path):
    p = write_config_file(tmp_path, "schema_version: 1\n")
    assert p == tmp_path / ".policycodex" / "config.yaml"
    assert p.read_text(encoding="utf-8") == "schema_version: 1\n"


def test_write_config_file_appends_trailing_newline(tmp_path):
    p = write_config_file(tmp_path, "a: b")
    assert p.read_text(encoding="utf-8").endswith("\n")


def test_make_onboarding_branch_name_is_prefixed_and_unique():
    a = make_onboarding_branch_name()
    b = make_onboarding_branch_name()
    assert a.startswith("policycodex/onboarding-")
    assert a != b


from app.onboarding.finalize import finalize_onboarding


class _UnusedProvider:
    """Stub; finalize_onboarding hands this to propose_change, which we patch."""


def test_finalize_writes_config_and_funnels_through_propose_change(tmp_path):
    """finalize_onboarding writes the config file then calls propose_change
    with the exact files scoped to commit (config + bundle_dir, no staging).

    propose_change's branch/commit/push/open_pr sequencing + clean-tree
    guarantees are covered in app/git_provider/tests/test_propose.py.
    """
    bundle_dir = tmp_path / "policies" / "document-retention"
    bundle_dir.mkdir(parents=True)
    fake_pr = {"pr_number": 7, "url": "https://github.com/d/r/pull/7", "state": "drafted"}

    with patch(
        "app.onboarding.finalize.propose_change", return_value=fake_pr
    ) as mock_propose:
        pr = finalize_onboarding(
            working_dir=tmp_path,
            config_yaml_text="schema_version: 1\n",
            bundle_dir=bundle_dir,
            provider=_UnusedProvider(),
            author_name="A",
            author_email="a@x",
            base_branch="main",
            username="admin",
        )

    assert pr["pr_number"] == 7
    assert (tmp_path / ".policycodex" / "config.yaml").is_file()

    mock_propose.assert_called_once()
    kwargs = mock_propose.call_args.kwargs
    assert kwargs["default_branch"] == "main"
    assert kwargs["branch_name"].startswith("policycodex/onboarding-")
    assert kwargs["commit_message"] == (
        "Initialize diocese configuration and document-retention policy"
    )
    assert kwargs["pr_title"] == "Initialize policy repository"
    assert tmp_path / ".policycodex" / "config.yaml" in kwargs["files"]
    assert bundle_dir in kwargs["files"]
    assert all(".policycodex-staging" not in str(f) for f in kwargs["files"])


def test_finalize_with_drafts_dir_appends_draft_files(tmp_path):
    """When drafts_dir is supplied, *.md and *.audit.yaml files are appended to
    the commit payload, and the PR body lists the drafted policies."""
    bundle_dir = tmp_path / "policies" / "document-retention"
    bundle_dir.mkdir(parents=True)
    drafts_dir = tmp_path / "policies"
    (drafts_dir / "code-of-conduct.md").write_text("# Code\n")
    (drafts_dir / "code-of-conduct.audit.yaml").write_text("confidence: 0.9\n")
    fake_pr = {"pr_number": 8, "url": "https://github.com/d/r/pull/8", "state": "drafted"}

    with patch(
        "app.onboarding.finalize.propose_change", return_value=fake_pr
    ) as mock_propose:
        pr = finalize_onboarding(
            working_dir=tmp_path,
            config_yaml_text="schema_version: 1\n",
            bundle_dir=bundle_dir,
            drafts_dir=drafts_dir,
            provider=_UnusedProvider(),
            author_name="A",
            author_email="a@x",
            base_branch="main",
            username="admin",
        )

    assert pr["pr_number"] == 8
    kwargs = mock_propose.call_args.kwargs
    files = kwargs["files"]
    # Config + bundle + code-of-conduct.md + code-of-conduct.audit.yaml
    assert drafts_dir / "code-of-conduct.md" in files
    assert drafts_dir / "code-of-conduct.audit.yaml" in files
    assert bundle_dir in files
    # PR body mentions the drafted policy.
    assert "code-of-conduct" in kwargs["pr_body"]
    assert "Drafted policies" in kwargs["pr_body"]


def test_finalize_without_drafts_dir_unchanged_behavior(tmp_path):
    """Omitting drafts_dir keeps the original two-file commit (config + bundle)."""
    bundle_dir = tmp_path / "policies" / "document-retention"
    bundle_dir.mkdir(parents=True)
    fake_pr = {"pr_number": 9, "url": "https://github.com/d/r/pull/9", "state": "drafted"}

    with patch(
        "app.onboarding.finalize.propose_change", return_value=fake_pr
    ) as mock_propose:
        finalize_onboarding(
            working_dir=tmp_path,
            config_yaml_text="schema_version: 1\n",
            bundle_dir=bundle_dir,
            provider=_UnusedProvider(),
            author_name="A",
            author_email="a@x",
            base_branch="main",
            username="admin",
        )

    kwargs = mock_propose.call_args.kwargs
    assert len(kwargs["files"]) == 2
    assert "Drafted policies" not in kwargs["pr_body"]
