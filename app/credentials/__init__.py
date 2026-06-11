"""DISC-02: Fernet-encrypted credential store + provider env hydration.

On import, hydrates the env vars for whichever LLM provider was chosen,
and writes the GitHub App private key to a file path the SDK can read.
Safe to import before first-boot completes: missing keys are simply
no-ops (the relevant Settings panels have not yet been configured).
"""
from __future__ import annotations

import os
from pathlib import Path

from app.credentials import store

_LLM_ENV_MAP = {
    "claude": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "gemini": "GOOGLE_API_KEY",
    "azure-openai": "AZURE_OPENAI_API_KEY",
}


def hydrate_environment() -> None:
    """Best-effort env hydration. Never raises. Safe to call repeatedly."""
    try:
        if store.has("llm.provider"):
            provider = store.get("llm.provider")
            key_slug = f"llm.{provider}.api_key"
            env_name = _LLM_ENV_MAP.get(provider)
            if env_name and store.has(key_slug):
                os.environ[env_name] = store.get(key_slug)
        # Require all three GH-App fields together; partial config
        # (e.g., PEM written but app_id absent) would otherwise
        # raise KeyError on every settings import.
        if (
            store.has("github_app.private_key_pem")
            and store.has("github_app.app_id")
            and store.has("github_app.installation_id")
        ):
            pem_path = Path(os.environ.get(
                "POLICYCODEX_GITHUB_APP_KEY_PATH",
                "/data/.github-app-key.pem",
            ))
            pem_path.parent.mkdir(parents=True, exist_ok=True)
            pem_path.write_text(store.get("github_app.private_key_pem"), encoding="utf-8")
            os.chmod(pem_path, 0o600)
            os.environ["POLICYCODEX_GH_APP_ID"] = store.get("github_app.app_id")
            os.environ["POLICYCODEX_GH_INSTALLATION_ID"] = store.get("github_app.installation_id")
            os.environ["POLICYCODEX_GH_PRIVATE_KEY_PATH"] = str(pem_path)
        # DISC-pivot: policy_repo.* needs to flow into Django settings so
        # working_copy/config.py picks it up across worker requests.
        if store.has("policy_repo.url"):
            os.environ["POLICYCODEX_POLICY_REPO_URL"] = store.get("policy_repo.url")
        if store.has("policy_repo.branch"):
            os.environ["POLICYCODEX_POLICY_BRANCH"] = store.get("policy_repo.branch")
    except RuntimeError:
        # First-boot, no credential-key yet. Settings haven't been configured.
        pass
