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
