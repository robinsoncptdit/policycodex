"""Configure-state machine. Inspects the credential store and returns
where to send the user next.

States:
  NO_GITHUB_APP    -> /settings/github-app/
  NO_LLM           -> /settings/llm-provider/
  NO_REPO          -> /settings/policy-repo/
  REPO_EMPTY       -> /settings/policy-repo/ (detected by GitHub API; v0.2)
  READY            -> /catalog/

Every credential read goes through app.credentials.store. If the store
is unavailable (running outside Docker without /data mounted), treat
the state as NO_GITHUB_APP — the safest assumption.
"""
from dataclasses import dataclass
from enum import Enum


class ConfigureState(Enum):
    NO_GITHUB_APP = "no_github_app"
    NO_LLM = "no_llm"
    NO_REPO = "no_repo"
    REPO_EMPTY = "repo_empty"
    READY = "ready"


_DESTINATIONS = {
    ConfigureState.NO_GITHUB_APP: "/settings/github-app/",
    ConfigureState.NO_LLM: "/settings/llm-provider/",
    ConfigureState.NO_REPO: "/settings/policy-repo/",
    ConfigureState.REPO_EMPTY: "/settings/policy-repo/",
    ConfigureState.READY: "/catalog/",
}

_BANNER_MESSAGES = {
    ConfigureState.NO_GITHUB_APP:
        "Set up GitHub access in Settings -> GitHub App. One click and "
        "PolicyCodex creates the App for you.",
    ConfigureState.NO_LLM:
        "Connect your AI provider in Settings -> AI provider.",
    ConfigureState.NO_REPO:
        "Choose your policy repository in Settings -> Policy repository.",
    ConfigureState.REPO_EMPTY:
        "Initialize your policy repo from the Policy repository panel.",
    ConfigureState.READY: None,
}


@dataclass(frozen=True)
class LifecycleState:
    state: ConfigureState
    next_url: str
    banner: str | None


def _store_check():
    from app.credentials import store
    try:
        has_gh = (
            store.has("github_app.app_id")
            and store.has("github_app.installation_id")
            and store.has("github_app.private_key_pem")
        )
        has_llm = store.has("llm.provider")
        has_repo = store.has("policy_repo.url")
    except RuntimeError:
        # Credential store unavailable (no /data/.credential-key). Treat as
        # fully unconfigured — safest first-boot assumption.
        return False, False, False
    return has_gh, has_llm, has_repo


def lifecycle_state(request):
    """Return the LifecycleState for the current credential-store state.

    The request argument is unused today but reserved for future per-user
    state (e.g., a returning admin who has not yet acknowledged an
    interrupted run). Keep the signature stable.
    """
    has_gh, has_llm, has_repo = _store_check()
    if not has_gh:
        state = ConfigureState.NO_GITHUB_APP
    elif not has_llm:
        state = ConfigureState.NO_LLM
    elif not has_repo:
        state = ConfigureState.NO_REPO
    else:
        # REPO_EMPTY detection requires a GitHub API call. v0.1 treats this
        # as READY; the empty-repo case is handled by the Policy Repo panel's
        # "Initialize this repo" setup action.
        state = ConfigureState.READY
    return LifecycleState(
        state=state,
        next_url=_DESTINATIONS[state],
        banner=_BANNER_MESSAGES[state],
    )
