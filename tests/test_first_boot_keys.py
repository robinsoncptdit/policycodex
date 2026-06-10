"""DISC-01: entrypoint generates SECRET_KEY + credential-store key on first boot."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

ENTRYPOINT = Path(__file__).parent.parent / "docker" / "entrypoint.sh"


def _run_entrypoint(tmp_path, data_dir, env=None):
    """Invoke the entrypoint up to the gunicorn exec line.

    The test substitutes a stub `manage.py` so `migrate` is a no-op and stops
    before `exec gunicorn`. Returns (returncode, /data file map).
    """
    stub = tmp_path / "manage.py"
    stub.write_text("#!/usr/bin/env python3\nimport sys\nsys.exit(0)\n")
    stub.chmod(0o755)
    # Replace `exec gunicorn ...` so the script exits without trying to start
    # the WSGI server.
    test_entrypoint = tmp_path / "entrypoint.sh"
    body = ENTRYPOINT.read_text()
    body = body.replace("exec gunicorn", "exit 0\nexec gunicorn")
    test_entrypoint.write_text(body)
    test_entrypoint.chmod(0o755)
    result = subprocess.run(
        ["sh", str(test_entrypoint)],
        cwd=tmp_path,
        env={
            "PATH": "/usr/bin:/bin",
            "POLICYCODEX_DATA_DIR": str(data_dir),
            **(env or {}),
        },
        capture_output=True,
        text=True,
    )
    files = {p.name: p.read_bytes() for p in Path(data_dir).iterdir() if p.is_file()}
    return result.returncode, files


def test_first_boot_generates_secret_key(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    rc, files = _run_entrypoint(tmp_path, data)
    assert rc == 0
    assert ".secret-key" in files
    assert len(files[".secret-key"]) >= 50


def test_first_boot_generates_credential_key(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    rc, files = _run_entrypoint(tmp_path, data)
    assert rc == 0
    assert ".credential-key" in files
    # Fernet keys are 44 chars urlsafe-base64.
    assert len(files[".credential-key"].strip()) == 44


def test_second_boot_does_not_overwrite_keys(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    (data / ".secret-key").write_bytes(b"existing-secret-key-value-from-prior-boot-do-not-touch")
    (data / ".credential-key").write_bytes(b"existing-credential-key-value-do-not-touch-it-44ch=")
    rc, files = _run_entrypoint(tmp_path, data)
    assert rc == 0
    assert files[".secret-key"] == b"existing-secret-key-value-from-prior-boot-do-not-touch"
    assert files[".credential-key"] == b"existing-credential-key-value-do-not-touch-it-44ch="


def test_data_dir_files_are_mode_600(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    _run_entrypoint(tmp_path, data)
    for name in (".secret-key", ".credential-key"):
        mode = (data / name).stat().st_mode & 0o777
        assert mode == 0o600, f"{name} has mode {oct(mode)}, expected 0o600"
