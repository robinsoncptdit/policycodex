"""DISC-02: Fernet-encrypted credential store.

Single JSON file at $POLICYCODEX_CREDENTIAL_STORE_FILE (default /data/.credentials),
encrypted with the Fernet key at $POLICYCODEX_CREDENTIAL_KEY_FILE (default
/data/.credential-key, generated on first boot per DISC-01).

The store is per-process cached but stays consistent across Gunicorn workers:
the cache is reloaded whenever the on-disk file's mtime changes, so a write on
one worker becomes visible to the others on their next access (a set() on worker
A flushes the file; worker B reloads on its next get/has). Writes are atomic
(temp-then-rename). Tests reset the cache via _reset_cache() before each
scenario.

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
_cache_mtime: float | None = None
_fernet: Fernet | None = None
_lock = Lock()


def _key_file() -> Path:
    return Path(os.environ.get("POLICYCODEX_CREDENTIAL_KEY_FILE", "/data/.credential-key"))


def _store_file() -> Path:
    return Path(os.environ.get("POLICYCODEX_CREDENTIAL_STORE_FILE", "/data/.credentials"))


def _ensure_loaded() -> None:
    global _cache, _fernet, _cache_mtime
    store_path = _store_file()
    disk_mtime = store_path.stat().st_mtime if store_path.is_file() else None
    # Reload when the cache is cold OR the on-disk store changed underneath us
    # (another Gunicorn worker wrote it). Without this, each worker's module
    # cache drifts and a key written on worker A is invisible to worker B.
    if _cache is not None and disk_mtime == _cache_mtime:
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
    if store_path.is_file():
        encrypted = store_path.read_bytes()
        if encrypted.strip():
            _cache = json.loads(_fernet.decrypt(encrypted).decode("utf-8"))
        else:
            _cache = {}
    else:
        _cache = {}
    _cache_mtime = disk_mtime


def _flush() -> None:
    global _cache_mtime
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
    # Record the mtime we just wrote so this worker does not pointlessly
    # reload its own freshly-written data on the next access.
    _cache_mtime = store_path.stat().st_mtime


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
    global _cache, _fernet, _cache_mtime
    with _lock:
        _cache = None
        _fernet = None
        _cache_mtime = None
