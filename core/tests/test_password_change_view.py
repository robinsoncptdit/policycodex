import pytest
from django.contrib.auth import get_user_model
from unittest.mock import patch

User = get_user_model()


@pytest.fixture
def admin_must_change(db):
    user = User.objects.create_superuser("admin2", "", "admin1234")
    user.profile.must_change_password = True
    user.profile.save()
    return user


def test_get_renders_form(client, admin_must_change):
    client.force_login(admin_must_change)
    response = client.get("/accounts/password/change/")
    assert response.status_code == 200
    assert b"New password" in response.content
    # PolicyCodex template, not django.contrib.admin's same-named one.
    assert b"Set a new password" in response.content
    assert b"id_old_password" in response.content
    assert (
        response.templates
        and response.templates[0].name == "core/password_change_form.html"
    )


def test_post_with_short_password_rejected(client, admin_must_change):
    client.force_login(admin_must_change)
    response = client.post("/accounts/password/change/", {
        "old_password": "admin1234",
        "new_password1": "short",
        "new_password2": "short",
    })
    assert response.status_code == 200  # form re-renders with errors
    admin_must_change.refresh_from_db()
    assert admin_must_change.profile.must_change_password is True  # not flipped


def test_post_with_strong_password_flips_flag(client, admin_must_change):
    """zxcvbn min_score 3 plus 12-char min plus common-password check."""
    client.force_login(admin_must_change)
    response = client.post("/accounts/password/change/", {
        "old_password": "admin1234",
        "new_password1": "kestrel-sapphire-meadow-91",
        "new_password2": "kestrel-sapphire-meadow-91",
    })
    assert response.status_code == 302  # redirected on success
    admin_must_change.refresh_from_db()
    assert admin_must_change.profile.must_change_password is False


def test_success_redirects_to_lifecycle_destination(client, admin_must_change):
    client.force_login(admin_must_change)
    with patch("core.views.lifecycle_state") as mock_state:
        mock_state.return_value.next_url = "/settings/github-app/"
        response = client.post("/accounts/password/change/", {
            "old_password": "admin1234",
            "new_password1": "kestrel-sapphire-meadow-91",
            "new_password2": "kestrel-sapphire-meadow-91",
        })
    assert response.status_code == 302
    assert response.url == "/settings/github-app/"
