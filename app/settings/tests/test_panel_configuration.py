import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.fixture
def admin(db):
    u = User.objects.get(username="admin")
    u.profile.must_change_password = False
    u.profile.save()
    u.email = "admin@diocese.example"
    u.save()
    return u


def _fake_config(tmp_path):
    # Mimic load_working_copy_config()'s return shape.
    cfg = MagicMock()
    cfg.working_dir = tmp_path
    cfg.branch = "main"
    return cfg


def test_get_renders_with_la_defaults(client, admin):
    client.force_login(admin)
    response = client.get("/settings/configuration/")
    assert response.status_code == 200
    assert b"chapter-section-item" in response.content
    assert b"semver" in response.content
    assert b"CFO" in response.content


def test_save_opens_a_pr_with_human_co_author(client, admin, tmp_path):
    client.force_login(admin)
    with patch("app.settings.panels.configuration.propose_change") as mock_propose, \
         patch("app.settings.panels.configuration.load_working_copy_config",
               return_value=_fake_config(tmp_path)), \
         patch("app.settings.panels.configuration.GitHubProvider"):
        mock_propose.return_value = {"url": "https://github.com/x/y/pull/42"}
        client.post("/settings/configuration/", {
            "address_scheme": "chapter-section-item",
            "versioning": "semver",
            "reviewer_roles": "CFO,HR Director,General Counsel",
            "retention_admin_years": "7",
            "retention_operational_years": "3",
        })
    mock_propose.assert_called_once()
    kwargs = mock_propose.call_args.kwargs
    assert "Co-Authored-By: admin <admin@diocese.example>" in kwargs["commit_message"]


def test_save_propose_failure_renders_error(client, admin, tmp_path):
    client.force_login(admin)
    with patch("app.settings.panels.configuration.propose_change",
               side_effect=RuntimeError("git push 403")), \
         patch("app.settings.panels.configuration.load_working_copy_config",
               return_value=_fake_config(tmp_path)), \
         patch("app.settings.panels.configuration.GitHubProvider"):
        response = client.post("/settings/configuration/", {
            "address_scheme": "chapter-section-item",
            "versioning": "semver",
            "reviewer_roles": "CFO",
            "retention_admin_years": "7",
            "retention_operational_years": "3",
        })
    assert response.status_code == 200
    assert b"git push 403" in response.content


def test_custom_values_persist_to_yaml(client, admin, tmp_path):
    """The YAML written to the repo carries the user's choices, not defaults."""
    client.force_login(admin)
    with patch("app.settings.panels.configuration.propose_change") as mock_propose, \
         patch("app.settings.panels.configuration.load_working_copy_config",
               return_value=_fake_config(tmp_path)), \
         patch("app.settings.panels.configuration.GitHubProvider"):
        mock_propose.return_value = {"url": "https://github.com/x/y/pull/1"}
        client.post("/settings/configuration/", {
            "address_scheme": "department-code",
            "versioning": "semver",
            "reviewer_roles": "COO,Compliance Officer",
            "retention_admin_years": "10",
            "retention_operational_years": "5",
        })
    # The panel writes the YAML to disk before calling propose_change.
    config_path = tmp_path / ".policycodex" / "config.yaml"
    assert config_path.exists()
    yaml_body = config_path.read_text(encoding="utf-8")
    assert "department-code" in yaml_body
    assert "COO" in yaml_body
    assert "10" in yaml_body
