"""Unit tests for onboarding finalization (APP-16)."""
import yaml

from app.onboarding.finalize import build_config_yaml
from app.onboarding.finalize import make_onboarding_branch_name, write_config_file


def test_build_config_yaml_emits_steps_in_wizard_order():
    all_data = {
        # Deliberately out of wizard order; output must be re-ordered.
        "address-scheme": {"scheme": "chapter-section-item"},
        "github-repo": {"mode": "connect", "repo_url": "https://github.com/d/r", "branch": "main"},
    }
    doc = yaml.safe_load(build_config_yaml(all_data))
    assert doc["schema_version"] == 1
    assert list(doc["onboarding"].keys()) == ["github-repo", "address-scheme"]
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


class _FakeProvider:
    def __init__(self):
        self.calls = []

    def branch(self, name, working_dir):
        self.calls.append(("branch", name))

    def commit(self, *, message, files, author_name, author_email, working_dir):
        self.calls.append(("commit", list(files)))
        return "deadbeef"

    def push(self, branch, working_dir):
        self.calls.append(("push", branch))

    def open_pr(self, *, title, body, head_branch, base_branch, working_dir):
        self.calls.append(("open_pr", head_branch, base_branch))
        return {"pr_number": 7, "url": "https://github.com/d/r/pull/7", "state": "drafted"}


def test_finalize_sequences_writes_config_and_scopes_commit(tmp_path):
    bundle_dir = tmp_path / "policies" / "document-retention"
    bundle_dir.mkdir(parents=True)
    provider = _FakeProvider()

    pr = finalize_onboarding(
        working_dir=tmp_path,
        config_yaml_text="schema_version: 1\n",
        bundle_dir=bundle_dir,
        provider=provider,
        author_name="A",
        author_email="a@x",
        base_branch="main",
        username="admin",
    )

    assert pr["pr_number"] == 7
    assert [c[0] for c in provider.calls] == ["branch", "commit", "push", "open_pr"]

    commit_files = [c for c in provider.calls if c[0] == "commit"][0][1]
    assert tmp_path / ".policycodex" / "config.yaml" in commit_files
    assert bundle_dir in commit_files
    assert all(".policycodex-staging" not in str(f) for f in commit_files)

    open_pr_call = [c for c in provider.calls if c[0] == "open_pr"][0]
    assert open_pr_call[2] == "main"

    assert (tmp_path / ".policycodex" / "config.yaml").is_file()
