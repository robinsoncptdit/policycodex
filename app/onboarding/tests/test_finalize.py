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
