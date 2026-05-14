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


def _stub_logical_policy(
    *,
    slug: str = "retention",
    foundational: bool = True,
    provides: tuple[str, ...] = ("classifications", "retention-schedule"),
    policy_path: Path | None = None,
):
    """Build a stand-in for an ingest.policy_reader.LogicalPolicy."""
    from ingest.policy_reader import LogicalPolicy
    pp = policy_path or Path(f"/tmp/policies/{slug}/policy.md")
    return LogicalPolicy(
        slug=slug,
        kind="bundle",
        policy_path=pp,
        data_path=pp.parent / "data.yaml",
        frontmatter={},
        body="",
        foundational=foundational,
        provides=provides,
    )


def _run_check_with_mocked_reader(*, policies, onboarding=True, repo_url="https://example.com/x.git"):
    """Invoke the check with a mocked BundleAwarePolicyReader yielding `policies`."""
    from app.working_copy import checks as checks_module

    with override_settings(
        POLICYCODEX_ONBOARDING_COMPLETE=onboarding,
        POLICYCODEX_POLICY_REPO_URL=repo_url,
        POLICYCODEX_POLICY_BRANCH="main",
        POLICYCODEX_WORKING_COPY_ROOT="/tmp",
    ):
        with patch("app.working_copy.checks.Path.exists", return_value=True):
            with patch("app.working_copy.checks.BundleAwarePolicyReader") as MockReader:
                MockReader.return_value.read.return_value = iter(policies)
                return checks_module.foundational_policy_check(app_configs=None)


def test_happy_path_returns_no_errors():
    """One foundational policy providing both required capabilities passes."""
    policies = [_stub_logical_policy()]
    results = _run_check_with_mocked_reader(policies=policies)
    assert results == []


def test_missing_capability_returns_error_with_hint():
    """A foundational policy providing only one of two required capabilities fails."""
    policies = [
        _stub_logical_policy(provides=("classifications",))  # missing "retention-schedule"
    ]
    results = _run_check_with_mocked_reader(policies=policies)
    assert len(results) == 1
    err = results[0]
    from django.core.checks import Error
    assert isinstance(err, Error)
    assert err.id == "policycodex.E002"
    assert "retention-schedule" in err.msg
    assert "foundational: true" in err.hint


def test_two_missing_capabilities_returns_two_errors():
    """Multiple missing capabilities surface as separate Error entries."""
    policies = [
        _stub_logical_policy(provides=())  # missing both
    ]
    results = _run_check_with_mocked_reader(policies=policies)
    assert len(results) == 2
    ids = {r.id for r in results}
    assert ids == {"policycodex.E002"}
    msgs = " ".join(r.msg for r in results)
    assert "classifications" in msgs
    assert "retention-schedule" in msgs


def test_duplicate_capability_provider_returns_error():
    """Two foundational policies both providing the same capability is an Error."""
    policies = [
        _stub_logical_policy(slug="retention-a", provides=("classifications", "retention-schedule")),
        _stub_logical_policy(slug="retention-b", provides=("classifications", "retention-schedule")),
    ]
    results = _run_check_with_mocked_reader(policies=policies)
    # Both required capabilities now have 2 providers each: 2 E003 errors.
    from django.core.checks import Error
    assert len(results) == 2
    for r in results:
        assert isinstance(r, Error)
        assert r.id == "policycodex.E003"
    msgs = " ".join(r.msg for r in results)
    assert "retention-a" in msgs and "retention-b" in msgs


def test_non_foundational_policies_are_ignored_for_capability_count():
    """A policy with foundational=False does not satisfy a required capability."""
    policies = [
        _stub_logical_policy(foundational=False, provides=("classifications", "retention-schedule")),
    ]
    results = _run_check_with_mocked_reader(policies=policies)
    # Both required capabilities go unprovided.
    assert len(results) == 2
    assert all(r.id == "policycodex.E002" for r in results)


def test_broken_bundle_returns_error_with_file_hint():
    """If BundleAwarePolicyReader raises BundleError, the check returns Error E001."""
    from ingest.policy_reader import BundleError
    from django.core.checks import Error
    from app.working_copy import checks as checks_module

    with override_settings(
        POLICYCODEX_ONBOARDING_COMPLETE=True,
        POLICYCODEX_POLICY_REPO_URL="https://example.com/x.git",
        POLICYCODEX_WORKING_COPY_ROOT="/tmp",
    ):
        with patch("app.working_copy.checks.Path.exists", return_value=True):
            with patch("app.working_copy.checks.BundleAwarePolicyReader") as MockReader:
                MockReader.return_value.read.side_effect = BundleError(
                    "bundle data.yaml is not valid YAML: /tmp/policies/retention/data.yaml: "
                    "expected <block end>, but found '['"
                )
                results = checks_module.foundational_policy_check(app_configs=None)

    assert len(results) == 1
    err = results[0]
    assert isinstance(err, Error)
    assert err.id == "policycodex.E001"
    assert "Broken foundational-policy bundle" in err.msg
    assert "data.yaml" in err.msg  # the wrapped BundleError message
    assert "pull_working_copy" in err.hint


def test_broken_bundle_is_error_even_during_onboarding():
    """Onboarding mode does NOT downgrade bundle-validity errors. Broken bundles
    are always Error because they signal real policy-repo brokenness, not a
    not-yet-setup state."""
    from ingest.policy_reader import BundleError
    from django.core.checks import Error
    from app.working_copy import checks as checks_module

    with override_settings(
        POLICYCODEX_ONBOARDING_COMPLETE=False,  # onboarding mode
        POLICYCODEX_POLICY_REPO_URL="https://example.com/x.git",
        POLICYCODEX_WORKING_COPY_ROOT="/tmp",
    ):
        with patch("app.working_copy.checks.Path.exists", return_value=True):
            with patch("app.working_copy.checks.BundleAwarePolicyReader") as MockReader:
                MockReader.return_value.read.side_effect = BundleError("oops")
                results = checks_module.foundational_policy_check(app_configs=None)

    assert len(results) == 1
    assert isinstance(results[0], Error)
    assert results[0].id == "policycodex.E001"


# Onboarding-gated infrastructure failures: missing env var, missing policies dir.

def test_unset_repo_url_during_onboarding_returns_warning():
    """POLICYCODEX_ONBOARDING_COMPLETE=False + unset repo URL -> Warning."""
    from app.working_copy import checks as checks_module
    from django.core.checks import Warning

    with override_settings(
        POLICYCODEX_ONBOARDING_COMPLETE=False,
        POLICYCODEX_POLICY_REPO_URL="",
    ):
        results = checks_module.foundational_policy_check(app_configs=None)

    assert len(results) == 1
    assert isinstance(results[0], Warning)
    assert results[0].id == "policycodex.W001"
    assert "POLICYCODEX_POLICY_REPO_URL" in results[0].msg
    assert "onboarding" in results[0].hint.lower()


def test_unset_repo_url_post_onboarding_returns_error():
    """POLICYCODEX_ONBOARDING_COMPLETE=True + unset repo URL -> Error."""
    from app.working_copy import checks as checks_module
    from django.core.checks import Error

    with override_settings(
        POLICYCODEX_ONBOARDING_COMPLETE=True,
        POLICYCODEX_POLICY_REPO_URL="",
    ):
        results = checks_module.foundational_policy_check(app_configs=None)

    assert len(results) == 1
    assert isinstance(results[0], Error)
    assert results[0].id == "policycodex.E004"


def test_missing_policies_dir_during_onboarding_returns_warning():
    """POLICYCODEX_ONBOARDING_COMPLETE=False + policies dir missing -> Warning."""
    from app.working_copy import checks as checks_module
    from django.core.checks import Warning

    with override_settings(
        POLICYCODEX_ONBOARDING_COMPLETE=False,
        POLICYCODEX_POLICY_REPO_URL="https://example.com/x.git",
        POLICYCODEX_WORKING_COPY_ROOT="/tmp",
    ):
        with patch("app.working_copy.checks.Path.exists", return_value=False):
            results = checks_module.foundational_policy_check(app_configs=None)

    assert len(results) == 1
    assert isinstance(results[0], Warning)
    assert results[0].id == "policycodex.W002"
    assert "pull_working_copy" in results[0].hint


def test_missing_policies_dir_post_onboarding_returns_error():
    """POLICYCODEX_ONBOARDING_COMPLETE=True + policies dir missing -> Error."""
    from app.working_copy import checks as checks_module
    from django.core.checks import Error

    with override_settings(
        POLICYCODEX_ONBOARDING_COMPLETE=True,
        POLICYCODEX_POLICY_REPO_URL="https://example.com/x.git",
        POLICYCODEX_WORKING_COPY_ROOT="/tmp",
    ):
        with patch("app.working_copy.checks.Path.exists", return_value=False):
            results = checks_module.foundational_policy_check(app_configs=None)

    assert len(results) == 1
    assert isinstance(results[0], Error)
    assert results[0].id == "policycodex.E005"
