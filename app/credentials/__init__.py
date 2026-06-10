"""DISC-02: Fernet-encrypted credential store + provider env hydration.

On import, hydrates the env vars for whichever LLM provider was chosen,
and writes the GitHub App private key to a file path the SDK can read.
Safe to import before first-boot completes: missing keys are simply
no-ops (the relevant wizard screens have not yet been completed).
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
        if store.has("github_app.private_key_pem"):
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
    except RuntimeError:
        # First-boot, no credential-key yet. Wizard hasn't run.
        pass
