"""DISC-05/06 followup: _signature() must be deterministic ACROSS Python
processes. Python's builtin hash() is randomized per-process via
PYTHONHASHSEED — using it for cross-request fingerprinting fails under
multi-worker gunicorn (the original DISC-05 bug Chuck caught walking the
wizard live).

These tests spawn a child Python with a different hash seed and assert
the signature matches the parent's. Without the SHA-256 fix the child's
hash() value diverges and the assert fires.
"""
from __future__ import annotations

import subprocess
import sys
import textwrap

_GITHUB_DRIVER = textwrap.dedent(
    """
    import os, sys
    sys.path.insert(0, %(repo)r)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "policycodex_site.settings")
    import django
    django.setup()
    from app.onboarding.screens.github_app import _signature
    data = {
        "app_id": "4021727",
        "installation_id": "139448951",
        "private_key_pem": "-----BEGIN RSA PRIVATE KEY-----\\nXYZ\\n-----END RSA PRIVATE KEY-----",
    }
    print(_signature(data))
    """
)

_LLM_DRIVER = textwrap.dedent(
    """
    import os, sys
    sys.path.insert(0, %(repo)r)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "policycodex_site.settings")
    import django
    django.setup()
    from app.onboarding.screens.llm_provider import _signature
    data = {"provider": "claude", "api_key": "sk-ant-abcdef"}
    print(_signature(data))
    """
)


def _run_in_subprocess(driver: str, hash_seed: str, repo_root: str) -> str:
    env = {
        "PATH": "/usr/bin:/bin",
        "PYTHONHASHSEED": hash_seed,
        "HOME": os.environ.get("HOME", "/tmp"),
        # DEBUG=1 satisfies the DISC-01 SECRET_KEY-off-when-DEBUG-off guard
        # so the subprocess can boot Django far enough to import the screens.
        "DJANGO_DEBUG": "1",
    }
    out = subprocess.check_output(
        [sys.executable, "-c", driver % {"repo": repo_root}],
        env=env,
        text=True,
        cwd=repo_root,
    )
    return out.strip()


def test_github_app_signature_is_deterministic_across_processes():
    """Two subprocesses with DIFFERENT PYTHONHASHSEED values must agree on
    the signature of the same PEM. Was failing under multi-worker gunicorn."""
    import os as _os
    repo = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))))
    a = _run_in_subprocess(_GITHUB_DRIVER, "1", repo)
    b = _run_in_subprocess(_GITHUB_DRIVER, "999", repo)
    assert a == b, f"signatures diverged across PYTHONHASHSEED: {a!r} vs {b!r}"


def test_llm_provider_signature_is_deterministic_across_processes():
    import os as _os
    repo = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))))
    a = _run_in_subprocess(_LLM_DRIVER, "1", repo)
    b = _run_in_subprocess(_LLM_DRIVER, "999", repo)
    assert a == b, f"signatures diverged across PYTHONHASHSEED: {a!r} vs {b!r}"


def test_github_app_signature_is_line_ending_canonical():
    """HTMX posts as urlencoded but the parent form is multipart; textareas
    can hit Django with different line endings on each path. Continue refused
    a just-tested form when CRLF/LF drift produced different SHA-256 outputs."""
    from app.onboarding.screens.github_app import _signature
    sig_crlf = _signature({"app_id": "1", "installation_id": "2",
                           "private_key_pem": "-----BEGIN-----\r\nXYZ\r\n-----END-----"})
    sig_lf = _signature({"app_id": "1", "installation_id": "2",
                         "private_key_pem": "-----BEGIN-----\nXYZ\n-----END-----"})
    sig_trailing_ws = _signature({"app_id": "1", "installation_id": "2",
                                  "private_key_pem": "  -----BEGIN-----\nXYZ\n-----END-----\n"})
    assert sig_crlf == sig_lf == sig_trailing_ws


def test_llm_provider_signature_strips_whitespace():
    """A copy-pasted API key with leading/trailing whitespace must fingerprint
    the same on Test Key and on Continue."""
    from app.onboarding.screens.llm_provider import _signature
    sig_clean = _signature({"provider": "claude", "api_key": "sk-ant-xyz"})
    sig_padded = _signature({"provider": "claude", "api_key": " sk-ant-xyz\n"})
    assert sig_clean == sig_padded


# Required for the subprocess helper above.
import os  # noqa: E402
