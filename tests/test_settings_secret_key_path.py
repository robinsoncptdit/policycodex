"""F7: the real settings.py SECRET_KEY path delegates to env.get_secret_key.

Each case spawns a clean interpreter because django.setup() configures settings
once per process; we need to control env per case.
"""
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _import_settings(env_overrides):
    env = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": str(REPO_ROOT),
        "DJANGO_SETTINGS_MODULE": "policycodex_site.settings",
    }
    env.update(env_overrides)
    code = (
        "import django; django.setup();"
        "from django.conf import settings as s;"
        "import sys; sys.stdout.write(s.SECRET_KEY)"
    )
    return subprocess.run(
        [sys.executable, "-c", code], env=env, cwd=str(REPO_ROOT),
        capture_output=True, text=True,
    )


def test_settings_reads_key_file_when_debug_off(tmp_path):
    key_file = tmp_path / ".secret-key"
    key_file.write_text("real-file-key-not-insecure\n")
    r = _import_settings({"POLICYCODEX_SECRET_KEY_FILE": str(key_file)})
    assert r.returncode == 0, r.stderr
    assert r.stdout == "real-file-key-not-insecure"


def test_settings_refuses_insecure_default_when_debug_off():
    r = _import_settings({})
    assert r.returncode != 0
    assert "DEBUG is off" in r.stderr


def test_settings_uses_dev_key_when_debug_on():
    r = _import_settings({"DJANGO_DEBUG": "1"})
    assert r.returncode == 0, r.stderr
    assert r.stdout.startswith("django-insecure-")
