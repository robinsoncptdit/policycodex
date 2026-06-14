"""Deploy-time settings helpers (REPO-05).

Pure functions that translate an environment mapping into Django setting
values. Kept separate from settings.py so they are unit-testable without
reloading Django. settings.py calls these with os.environ.
"""
from __future__ import annotations

import os
from pathlib import Path

# The historical insecure dev key. Used only when DEBUG is on and no
# DJANGO_SECRET_KEY is supplied, so `manage.py runserver` keeps working
# locally with zero config. Never used when DEBUG is off.
_DEV_SECRET_KEY = "django-insecure-77@z8v71u2tc7%7qp)rpg7!cctxh32l5+_**y%4uw9+j(9f(&w"

_TRUTHY = ("1", "true", "yes")

_DEFAULT_SOURCE_URL = "https://github.com/robinsoncptdit/policycodex"


class SettingsError(Exception):
    """Raised when a required deploy-time setting is missing."""


def get_debug(environ) -> bool:
    return environ.get("DJANGO_DEBUG", "").strip().lower() in _TRUTHY


def get_secret_key(environ, debug: bool) -> str:
    # DISC-01: the container entrypoint writes the key to a file under /data
    # and points POLICYCODEX_SECRET_KEY_FILE at it. A real file key always wins
    # so the container boots without DJANGO_SECRET_KEY in the environment.
    key_file = environ.get("POLICYCODEX_SECRET_KEY_FILE", "").strip()
    if key_file and os.path.isfile(key_file):
        try:
            with open(key_file, "r", encoding="utf-8") as fh:
                file_key = fh.read().strip()
        except OSError as exc:
            # The file is explicitly configured but unreadable (bad permissions,
            # or swapped/removed after the isfile check). Surface an actionable
            # error rather than a bare traceback at settings import.
            raise SettingsError(
                f"POLICYCODEX_SECRET_KEY_FILE is set to {key_file!r} but the "
                f"file could not be read: {exc}"
            ) from exc
        if file_key:
            return file_key
    key = environ.get("DJANGO_SECRET_KEY", "").strip()
    if key:
        return key
    if debug:
        return _DEV_SECRET_KEY
    raise SettingsError(
        "DJANGO_SECRET_KEY must be set when DEBUG is off. Generate one and "
        "pass it via the environment, or set POLICYCODEX_SECRET_KEY_FILE "
        "(see .env.example)."
    )


def get_allowed_hosts(environ) -> list[str]:
    raw = environ.get("DJANGO_ALLOWED_HOSTS", "").strip()
    if not raw:
        return ["localhost", "127.0.0.1"]
    return [h.strip() for h in raw.split(",") if h.strip()]


def get_db_path(environ, base_dir: Path, data_dir: Path = Path("/data")) -> Path:
    # Explicit POLICYCODEX_DB_PATH always wins. Otherwise, when the container
    # data volume is mounted, persist there so the DB survives a container
    # recreate even if .env omits the path. Local (non-container) runs have no
    # data volume and fall back to the repo-root sqlite file.
    raw = environ.get("POLICYCODEX_DB_PATH", "").strip()
    if raw:
        return Path(raw)
    if data_dir.is_dir():
        return data_dir / "db.sqlite3"
    return base_dir / "db.sqlite3"


def get_source_url(environ) -> str:
    return environ.get("POLICYCODEX_SOURCE_URL", "").strip() or _DEFAULT_SOURCE_URL
