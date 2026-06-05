"""Finalize onboarding: commit the diocese config + first foundational bundle.

The wizard collects per-screen choices into WizardState. On the final "accept"
of screen 7, this module serializes those choices to `.policycodex/config.yaml`
in the working copy and opens a single PR that contains both the config file and
the scaffolded `policies/document-retention/` bundle (written by
app.onboarding.scaffold in APP-15).

Secrets never reach the repo: build_config_yaml drops any key whose name marks
it as a credential (the GitHub token and LLM API key live in
~/.config/policycodex/, per project convention). The commit stages only the
explicit paths passed to the provider; it never runs `git add .`, so the
onboarding staging dir and the raw uploaded PDF are never swept into the repo.
"""
from __future__ import annotations

import uuid
from pathlib import Path

import yaml

from app.onboarding import wizard

CONFIG_SCHEMA_VERSION = 1
CONFIG_DIR_NAME = ".policycodex"
CONFIG_FILE_NAME = "config.yaml"

# A wizard field is treated as a secret (and excluded from the committed config)
# when its key contains any of these markers. Keeps credentials out of the repo
# as future screens (e.g. llm-provider) add an api_key field.
_SECRET_KEY_MARKERS = (
    "token", "secret", "password", "api_key", "apikey", "credential",
)


def _is_secret_key(key: str) -> bool:
    low = str(key).lower()
    return any(marker in low for marker in _SECRET_KEY_MARKERS)


def _scrub_secrets(step_data: dict) -> dict:
    return {k: v for k, v in step_data.items() if not _is_secret_key(k)}


def build_config_yaml(all_data: dict) -> str:
    """Serialize wizard choices to YAML for committing to the policy repo.

    Steps are emitted in wizard order for stable diffs; secret-named fields are
    dropped; only steps present in `all_data` appear.
    """
    onboarding: dict = {}
    for step in wizard.STEPS:
        if step.slug in all_data:
            onboarding[step.slug] = _scrub_secrets(all_data[step.slug])
    doc = {"schema_version": CONFIG_SCHEMA_VERSION, "onboarding": onboarding}
    return yaml.safe_dump(doc, sort_keys=False, allow_unicode=True)


def write_config_file(working_dir: Path, config_yaml_text: str) -> Path:
    """Write `.policycodex/config.yaml` under the working copy. Returns its path."""
    config_dir = Path(working_dir) / CONFIG_DIR_NAME
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / CONFIG_FILE_NAME
    text = config_yaml_text if config_yaml_text.endswith("\n") else config_yaml_text + "\n"
    config_path.write_text(text, encoding="utf-8")
    return config_path


def make_onboarding_branch_name() -> str:
    """policycodex/onboarding-<short-uuid>. Distinct from edit branches so the
    catalog's slug-mapped gate lookup ignores it (this PR is repo init, not a
    single-policy edit)."""
    return f"policycodex/onboarding-{uuid.uuid4().hex[:8]}"
