"""Tests for the foundational-policy startup check."""
from pathlib import Path
from unittest.mock import patch

import pytest
from django.apps import apps as django_apps
from django.test import override_settings


def test_working_copy_app_is_installed():
    """app.working_copy must be in INSTALLED_APPS for the check to register."""
    app_labels = {app.label for app in django_apps.get_app_configs()}
    assert "working_copy" in app_labels


def test_working_copy_app_config_class_name():
    """The AppConfig subclass must NOT be named WorkingCopyConfig (collides with the
    dataclass of the same name in app/working_copy/config.py)."""
    cfg = django_apps.get_app_config("working_copy")
    assert type(cfg).__name__ == "WorkingCopyAppConfig"


def test_foundational_policy_check_is_registered():
    """The check function must be registered with Django's check framework."""
    from django.core.checks import registry
    check_names = {fn.__name__ for fn in registry.registry.get_checks()}
    assert "foundational_policy_check" in check_names


def test_check_runs_via_manage_py_check_command(monkeypatch):
    """`manage.py check` should invoke our check and not crash."""
    from django.core.management import call_command
    from io import StringIO

    # Use the onboarding-mode default (False) and clear repo URL so the
    # check returns a Warning rather than an Error (which would set exit
    # code 1 and make this assertion noisier).
    with override_settings(
        POLICYCODEX_ONBOARDING_COMPLETE=False,
        POLICYCODEX_POLICY_REPO_URL="",
    ):
        out = StringIO()
        # call_command raises SystemExit on Error-level findings; the
        # onboarding-mode Warning path keeps it quiet.
        call_command("check", stdout=out)
    # No assertion on output content here; the goal is "command ran".
