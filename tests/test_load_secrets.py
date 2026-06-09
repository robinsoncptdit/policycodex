"""Tests for the docker/load-secrets.sh entrypoint helper (REPO-17).

The helper sources `/secrets/config.env` and auto-exports each KEY=VALUE
line into the process env so the LLM SDKs (and any future env-driven
config) can read them. Path overridable via POLICYCODEX_CONFIG_PATH so
these tests can drive it against tmp files instead of a real bind mount.

Subprocess-based, no Docker required: we `sh -c '. load-secrets.sh && env'`
in a real shell with a controlled env, then assert on the captured output.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_HELPER = _ROOT / "docker" / "load-secrets.sh"


def _run(secrets_path: str | None) -> subprocess.CompletedProcess[str]:
    """Source the helper in a fresh POSIX shell and capture the resulting env."""
    env = {"PATH": "/usr/bin:/bin"}
    if secrets_path is not None:
        env["POLICYCODEX_CONFIG_PATH"] = secrets_path
    return subprocess.run(
        ["sh", "-c", '. "$1" && env', "sh", str(_HELPER)],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def test_load_secrets_exports_keys_into_env(tmp_path):
    secrets = tmp_path / "config.env"
    secrets.write_text("ANTHROPIC_API_KEY=sk-test\nOTHER=v\n", encoding="utf-8")

    result = _run(str(secrets))

    assert result.returncode == 0, result.stderr
    assert "ANTHROPIC_API_KEY=sk-test" in result.stdout
    assert "OTHER=v" in result.stdout


def test_load_secrets_silent_when_file_missing(tmp_path):
    missing = tmp_path / "does-not-exist.env"

    result = _run(str(missing))

    assert result.returncode == 0
    assert result.stderr == ""
    # The keys must not appear when there's no file to source.
    assert "ANTHROPIC_API_KEY" not in result.stdout


def test_load_secrets_silent_when_file_empty(tmp_path):
    empty = tmp_path / "config.env"
    empty.write_text("", encoding="utf-8")

    result = _run(str(empty))

    assert result.returncode == 0
    assert result.stderr == ""
