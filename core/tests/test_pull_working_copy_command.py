"""Tests for the pull_working_copy management command."""
from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.test import override_settings


@pytest.fixture
def settings_for_command(tmp_path):
    with override_settings(
        POLICYCODEX_POLICY_REPO_URL="https://github.com/example/policy.git",
        POLICYCODEX_POLICY_BRANCH="main",
        POLICYCODEX_WORKING_COPY_ROOT=str(tmp_path),
    ):
        yield tmp_path


def test_command_invokes_manager_sync(settings_for_command):
    out = StringIO()
    with patch("core.management.commands.pull_working_copy.WorkingCopyManager") as MgrCls:
        with patch("core.management.commands.pull_working_copy.GitHubProvider") as ProvCls:
            instance = MgrCls.return_value
            instance.sync.return_value = settings_for_command / "policy"

            call_command("pull_working_copy", stdout=out)

    ProvCls.assert_called_once()
    MgrCls.assert_called_once()
    instance.sync.assert_called_once_with()
    assert "policy" in out.getvalue()
    assert "synced" in out.getvalue()


def test_command_raises_with_clear_message_when_repo_url_missing():
    out = StringIO()
    with override_settings(
        POLICYCODEX_POLICY_REPO_URL="",
        POLICYCODEX_POLICY_BRANCH="main",
        POLICYCODEX_WORKING_COPY_ROOT="/tmp/wc",
    ):
        with pytest.raises(RuntimeError, match="POLICYCODEX_POLICY_REPO_URL"):
            call_command("pull_working_copy", stdout=out)


def test_command_propagates_sync_error(settings_for_command):
    out = StringIO()
    err = StringIO()
    with patch("core.management.commands.pull_working_copy.WorkingCopyManager") as MgrCls:
        with patch("core.management.commands.pull_working_copy.GitHubProvider"):
            MgrCls.return_value.sync.side_effect = RuntimeError("git pull failed (exit 1): nope")
            with pytest.raises(RuntimeError, match="git pull failed"):
                call_command("pull_working_copy", stdout=out, stderr=err)
