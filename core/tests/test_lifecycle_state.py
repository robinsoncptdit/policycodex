import pytest
from unittest.mock import patch
from cryptography.fernet import Fernet


@pytest.fixture
def credential_env(tmp_path, monkeypatch):
    from app.credentials import store
    key_file = tmp_path / ".credential-key"
    key_file.write_bytes(Fernet.generate_key())
    monkeypatch.setenv("POLICYCODEX_CREDENTIAL_KEY_FILE", str(key_file))
    monkeypatch.setenv("POLICYCODEX_CREDENTIAL_STORE_FILE", str(tmp_path / ".credentials"))
    store._reset_cache()
    yield


def test_no_github_app_returns_github_app(credential_env):
    from core.lifecycle import lifecycle_state, ConfigureState
    state = lifecycle_state(None)
    assert state.state is ConfigureState.NO_GITHUB_APP
    assert state.next_url == "/settings/github-app/"


def test_gh_app_set_no_llm_returns_llm(credential_env):
    from app.credentials import store
    from core.lifecycle import lifecycle_state, ConfigureState
    store.set("github_app.app_id", "1")
    store.set("github_app.installation_id", "2")
    store.set("github_app.private_key_pem", "PEM")
    state = lifecycle_state(None)
    assert state.state is ConfigureState.NO_LLM
    assert state.next_url == "/settings/llm-provider/"


def test_gh_app_and_llm_set_no_repo_returns_repo(credential_env):
    from app.credentials import store
    from core.lifecycle import lifecycle_state, ConfigureState
    store.set("github_app.app_id", "1")
    store.set("github_app.installation_id", "2")
    store.set("github_app.private_key_pem", "PEM")
    store.set("llm.provider", "claude")
    state = lifecycle_state(None)
    assert state.state is ConfigureState.NO_REPO
    assert state.next_url == "/settings/policy-repo/"


def test_everything_set_returns_catalog(credential_env):
    from app.credentials import store
    from core.lifecycle import lifecycle_state, ConfigureState
    store.set("github_app.app_id", "1")
    store.set("github_app.installation_id", "2")
    store.set("github_app.private_key_pem", "PEM")
    store.set("llm.provider", "claude")
    store.set("policy_repo.url", "https://github.com/diocese/policies")
    state = lifecycle_state(None)
    # REPO_EMPTY detection (a GitHub call) is deferred; until then this is READY.
    assert state.state is ConfigureState.READY
    assert state.next_url == "/catalog/"


def test_no_credential_store_returns_github_app(monkeypatch):
    """When /data/.credential-key is missing (dev outside Docker), lifecycle
    must not raise; treat as fully-unconfigured."""
    from app.credentials import store
    from core.lifecycle import lifecycle_state, ConfigureState
    monkeypatch.setenv("POLICYCODEX_CREDENTIAL_KEY_FILE", "/nonexistent/.key")
    monkeypatch.setenv("POLICYCODEX_CREDENTIAL_STORE_FILE", "/nonexistent/.store")
    store._reset_cache()
    state = lifecycle_state(None)
    assert state.state is ConfigureState.NO_GITHUB_APP
    assert state.next_url == "/settings/github-app/"
