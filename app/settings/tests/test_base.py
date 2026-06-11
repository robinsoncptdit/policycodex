import pytest
from dataclasses import is_dataclass, FrozenInstanceError


def test_settings_panel_is_abstract():
    from app.settings.base import SettingsPanel
    with pytest.raises(TypeError):
        SettingsPanel()


def test_concrete_panel_default_test_returns_none():
    from app.settings.base import SettingsPanel

    class P(SettingsPanel):
        slug = "x"
        title = "X"
        nav_group = "Credentials"
        def render(self, request): pass
        def save(self, request): pass

    assert P().test(None) is None


def test_concrete_panel_default_setup_and_danger_empty():
    from app.settings.base import SettingsPanel

    class P(SettingsPanel):
        slug = "x"
        title = "X"
        nav_group = "Credentials"
        def render(self, request): pass
        def save(self, request): pass

    assert P().setup_actions(None) == []
    assert P().danger_actions(None) == []


def test_panel_default_can_access_admin_only():
    from app.settings.base import SettingsPanel
    from unittest.mock import MagicMock

    class P(SettingsPanel):
        slug = "x"
        title = "X"
        nav_group = "Credentials"
        def render(self, request): pass
        def save(self, request): pass

    admin = MagicMock(is_superuser=True)
    in_admin_group = MagicMock(is_superuser=False)
    in_admin_group.groups.filter.return_value.exists.return_value = True
    not_admin = MagicMock(is_superuser=False)
    not_admin.groups.filter.return_value.exists.return_value = False

    assert P().can_access(admin) is True
    assert P().can_access(in_admin_group) is True
    assert P().can_access(not_admin) is False


def test_dataclasses_are_frozen():
    from app.settings.base import SetupAction, DangerAction, SaveResult, TestResult, HelpBlock
    for cls in (SetupAction, DangerAction, SaveResult, TestResult, HelpBlock):
        assert is_dataclass(cls)
    r = SaveResult(ok=True, message="x")
    with pytest.raises(FrozenInstanceError):
        r.ok = False  # type: ignore[misc]


def test_save_result_carries_state():
    from app.settings.base import SaveResult
    r = SaveResult(ok=True, message="Saved.", pr_url="https://github.com/x/y/pull/1")
    assert r.ok is True
    assert r.pr_url == "https://github.com/x/y/pull/1"


def test_test_result_color_coded():
    from app.settings.base import TestResult
    ok = TestResult(state="ok", message="Connected.")
    err = TestResult(state="error", message="401")
    assert ok.state == "ok"
    assert err.state == "error"
