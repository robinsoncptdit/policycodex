"""GitHub App configuration loader (read-only, no caching)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class GitHubConfig:
    app_id: int
    installation_id: int
    private_key_path: Path


def _parse_value(raw: str) -> str:
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in ('"', "'"):
        return raw[1:-1]
    return raw


def _parse_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        raise FileNotFoundError(f"PolicyCodex config not found at {path}")
    result: dict[str, str] = {}
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, raw_value = line.partition("=")
            result[key.strip()] = _parse_value(raw_value)
    return result


def _default_config_path() -> Path:
    return Path(os.path.expanduser("~/.config/policycodex/config.env"))


_REQUIRED_KEYS = (
    "POLICYCODEX_GH_APP_ID",
    "POLICYCODEX_GH_INSTALLATION_ID",
    "POLICYCODEX_GH_PRIVATE_KEY_PATH",
)


def _from_env() -> GitHubConfig | None:
    """Read the GH App config from process env. Returns None if any required
    key is absent — caller falls back to the legacy config.env file.

    DISC-02's app.credentials.hydrate_environment() writes these three env
    vars on every Django startup when the credential store has them, so
    the in-app wizard is the authoritative source in production.
    """
    if not all(os.environ.get(k) for k in _REQUIRED_KEYS):
        return None
    return GitHubConfig(
        app_id=int(os.environ["POLICYCODEX_GH_APP_ID"]),
        installation_id=int(os.environ["POLICYCODEX_GH_INSTALLATION_ID"]),
        private_key_path=Path(os.environ["POLICYCODEX_GH_PRIVATE_KEY_PATH"]),
    )


def load_github_config(path: Path | None = None) -> GitHubConfig:
    if path is None:
        from_env = _from_env()
        if from_env is not None:
            return from_env
        env_override = os.getenv("POLICYCODEX_CONFIG_PATH")
        path = Path(env_override) if env_override else _default_config_path()
    values = _parse_env_file(path)
    missing = [k for k in _REQUIRED_KEYS if k not in values or not values[k]]
    if missing:
        raise ValueError(f"Missing required keys in {path}: {missing}")
    return GitHubConfig(
        app_id=int(values["POLICYCODEX_GH_APP_ID"]),
        installation_id=int(values["POLICYCODEX_GH_INSTALLATION_ID"]),
        private_key_path=Path(values["POLICYCODEX_GH_PRIVATE_KEY_PATH"]),
    )
