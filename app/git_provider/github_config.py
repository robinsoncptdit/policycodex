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


def load_github_config(path: Path | None = None) -> GitHubConfig:
    if path is None:
        env_override = os.getenv("POLICYCODEX_CONFIG_PATH")
        path = Path(env_override) if env_override else _default_config_path()
    values = _parse_env_file(path)
    required = (
        "POLICYCODEX_GH_APP_ID",
        "POLICYCODEX_GH_INSTALLATION_ID",
        "POLICYCODEX_GH_PRIVATE_KEY_PATH",
    )
    missing = [k for k in required if k not in values or not values[k]]
    if missing:
        raise ValueError(f"Missing required keys in {path}: {missing}")
    return GitHubConfig(
        app_id=int(values["POLICYCODEX_GH_APP_ID"]),
        installation_id=int(values["POLICYCODEX_GH_INSTALLATION_ID"]),
        private_key_path=Path(values["POLICYCODEX_GH_PRIVATE_KEY_PATH"]),
    )
