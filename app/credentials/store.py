"""DISC-02: Fernet-encrypted credential store.

Single JSON file at $POLICYCODEX_CREDENTIAL_STORE_FILE (default /data/.credentials),
encrypted with the Fernet key at $POLICYCODEX_CREDENTIAL_KEY_FILE (default
/data/.credential-key, generated on first boot per DISC-01).

The store is process-local: read once at first use, written atomically
(temp-then-rename) on every set, and cached. Tests reset the cache via
_reset_cache() before each scenario.

Keys follow a dotted namespace: llm.<provider>.api_key, github_app.app_id,
github_app.installation_id, github_app.private_key_pem.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from threading import Lock

from cryptography.fernet import Fernet

_REQUIRED_FOR_BOOT = (
    "github_app.app_id",
    "github_app.installation_id",
    "github_app.private_key_pem",
)

_cache: dict | None = None
_fernet: Fernet | None = None
_lock = Lock()


def _key_file() -> Path:
    return Path(os.environ.get("POLICYCODEX_CREDENTIAL_KEY_FILE", "/data/.credential-key"))


def _store_file() -> Path:
    return Path(os.environ.get("POLICYCODEX_CREDENTIAL_STORE_FILE", "/data/.credentials"))


def _ensure_loaded() -> None:
    global _cache, _fernet
    if _cache is not None:
        return
    key_path = _key_file()
    if not key_path.is_file():
        raise RuntimeError(
            f"Credential-key file missing at {key_path}. The container "
            "entrypoint generates this on first boot; check that /data is "
            "mounted and that you are not running outside Docker without "
            "POLICYCODEX_CREDENTIAL_KEY_FILE set."
        )
    _fernet = Fernet(key_path.read_bytes().strip())
    store_path = _store_file()
    if store_path.is_file():
        encrypted = store_path.read_bytes()
        if encrypted.strip():
            _cache = json.loads(_fernet.decrypt(encrypted).decode("utf-8"))
        else:
            _cache = {}
    else:
        _cache = {}


def _flush() -> None:
    assert _fernet is not None and _cache is not None
    store_path = _store_file()
    store_path.parent.mkdir(parents=True, exist_ok=True)
    encrypted = _fernet.encrypt(json.dumps(_cache, sort_keys=True).encode("utf-8"))
    fd, tmp_name = tempfile.mkstemp(
        prefix=".credentials.", dir=str(store_path.parent),
    )
    try:
        os.write(fd, encrypted)
        os.close(fd)
        os.chmod(tmp_name, 0o600)
        os.replace(tmp_name, store_path)
    except Exception:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
        raise


def get(key: str) -> str:
    with _lock:
        _ensure_loaded()
        assert _cache is not None
        if key not in _cache:
            raise KeyError(key)
        return _cache[key]


def has(key: str) -> bool:
    with _lock:
        _ensure_loaded()
        assert _cache is not None
        return key in _cache


def set(key: str, value: str) -> None:
    with _lock:
        _ensure_loaded()
        assert _cache is not None
        _cache[key] = value
        _flush()


def all_keys() -> list[str]:
    with _lock:
        _ensure_loaded()
        assert _cache is not None
        return list(_cache.keys())


def first_boot_complete() -> bool:
    """True iff every key required to operate is present (no LLM check here;
    Local Llama configs may legitimately omit an API key)."""
    with _lock:
        _ensure_loaded()
        assert _cache is not None
        return all(k in _cache for k in _REQUIRED_FOR_BOOT)


def _reset_cache() -> None:
    """Test-only helper. Forces the next call to re-read from disk."""
    global _cache, _fernet
    with _lock:
        _cache = None
        _fernet = None
