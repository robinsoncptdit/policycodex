"""Shared fixtures for the inventory test package."""
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _stub_working_copy_config():
    """Prevent load_working_copy_config from raising when the env var is absent.

    Retry-view tests patch start_run and only care that it gets called;
    they should not fail because the test environment has no policy repo URL.
    """
    fake_cfg = type("Cfg", (), {"working_dir": Path("/tmp/test-working-copy")})()
    with patch("app.inventory.views.load_working_copy_config", return_value=fake_cfg):
        yield
