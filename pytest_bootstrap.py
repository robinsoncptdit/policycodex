"""Pytest bootstrap plugin (test-only).

DEBUG defaults to False (REPO-05), which makes DJANGO_SECRET_KEY required at
settings-import time. pytest-django touches settings inside its
`pytest_load_initial_conftests` hook, which can run before a rootdir
conftest is imported. Loading this as a plugin via `addopts = -p
pytest_bootstrap` (see pytest.ini) runs it during plugin registration,
before any settings access, so the throwaway key is always in place.

This keeps DEBUG=False under tests (matching production) without baking a
secret key into settings.py. Not part of the shipping artifact.
"""
import os

os.environ.setdefault("DJANGO_SECRET_KEY", "test-insecure-key-not-for-production")
