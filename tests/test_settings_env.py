"""Unit tests for policycodex_site.env (REPO-05 deploy-time settings helpers)."""
from pathlib import Path

import pytest

from policycodex_site import env

_DEV_DEFAULT = "django-insecure-77@z8v71u2tc7%7qp)rpg7!cctxh32l5+_**y%4uw9+j(9f(&w"


def test_secret_key_uses_env_when_set():
    assert env.get_secret_key({"DJANGO_SECRET_KEY": "abc"}, debug=False) == "abc"


def test_secret_key_falls_back_to_dev_default_in_debug():
    assert env.get_secret_key({}, debug=True) == _DEV_DEFAULT


def test_secret_key_required_when_not_debug():
    with pytest.raises(env.SettingsError):
        env.get_secret_key({}, debug=False)


def test_debug_defaults_off():
    assert env.get_debug({}) is False


@pytest.mark.parametrize("raw", ["1", "true", "TRUE", "yes", "Yes"])
def test_debug_truthy(raw):
    assert env.get_debug({"DJANGO_DEBUG": raw}) is True


@pytest.mark.parametrize("raw", ["0", "false", "no", ""])
def test_debug_falsy(raw):
    assert env.get_debug({"DJANGO_DEBUG": raw}) is False


def test_allowed_hosts_default_is_localhost():
    assert env.get_allowed_hosts({}) == ["localhost", "127.0.0.1"]


def test_allowed_hosts_parses_csv_and_strips():
    assert env.get_allowed_hosts(
        {"DJANGO_ALLOWED_HOSTS": "example.org, 10.0.0.5 ,localhost"}
    ) == ["example.org", "10.0.0.5", "localhost"]


def test_db_path_default_is_base_dir_without_data_volume(tmp_path):
    # No env var and no mounted data volume (local dev): fall back to base_dir.
    missing_volume = tmp_path / "no-such-data"
    assert (
        env.get_db_path({}, tmp_path, data_dir=missing_volume)
        == tmp_path / "db.sqlite3"
    )


def test_db_path_prefers_data_volume_when_present(tmp_path):
    # No env var but the container data volume is mounted: persist there so the
    # DB survives container recreate even if .env omits POLICYCODEX_DB_PATH.
    volume = tmp_path / "data"
    volume.mkdir()
    assert (
        env.get_db_path({}, tmp_path, data_dir=volume) == volume / "db.sqlite3"
    )


def test_db_path_env_wins_over_data_volume(tmp_path):
    # An explicit POLICYCODEX_DB_PATH always wins, volume present or not.
    volume = tmp_path / "data"
    volume.mkdir()
    assert env.get_db_path(
        {"POLICYCODEX_DB_PATH": "/custom/x.sqlite3"}, tmp_path, data_dir=volume
    ) == Path("/custom/x.sqlite3")


def test_db_path_uses_env(tmp_path):
    assert env.get_db_path({"POLICYCODEX_DB_PATH": "/data/x.sqlite3"}, tmp_path) == Path(
        "/data/x.sqlite3"
    )


def test_source_url_default_placeholder():
    assert env.get_source_url({}) == "https://github.com/robinsoncptdit/policycodex"


def test_source_url_uses_env():
    assert env.get_source_url({"POLICYCODEX_SOURCE_URL": "https://x.test/repo"}) == (
        "https://x.test/repo"
    )
