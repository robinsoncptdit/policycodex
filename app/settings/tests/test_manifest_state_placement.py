import json
import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.fixture
def admin(db):
    u = User.objects.get(username="admin")
    u.profile.must_change_password = False
    u.profile.save()
    return u


def test_redirect_url_has_no_query_string(client, admin):
    client.force_login(admin)
    response = client.get("/settings/github-app/manifest/start/")
    assert response.status_code == 200
    # Parse the hidden manifest input's JSON value.
    body = response.content.decode()
    start = body.index('name="manifest"')
    value_start = body.index('value="', start) + len('value="')
    value_end = body.index('"', value_start)
    raw = body[value_start:value_end]
    # Django auto-escapes the value attribute; decode the entities.
    raw = raw.replace("&quot;", '"').replace("&#x27;", "'").replace("&amp;", "&")
    manifest = json.loads(raw)
    assert "?" not in manifest["redirect_url"], (
        f"redirect_url must not contain a query string; got {manifest['redirect_url']!r}"
    )
    assert manifest["redirect_url"].endswith("/settings/github-app/manifest/callback/")


def test_state_is_separate_form_field(client, admin):
    client.force_login(admin)
    response = client.get("/settings/github-app/manifest/start/")
    body = response.content
    # A hidden input named "state" is present and non-empty.
    assert b'name="state"' in body
    # Pull out the value.
    start = body.index(b'name="state"')
    value_start = body.index(b'value="', start) + len(b'value="')
    value_end = body.index(b'"', value_start)
    state = body[value_start:value_end]
    assert len(state) >= 16, f"state token should be substantial; got {state!r}"


def test_callback_still_validates_state_from_query_params(client, admin):
    """The callback reads state from request.GET — that flow is unchanged."""
    client.force_login(admin)
    session = client.session
    session["github_app_manifest_state"] = "matching-state"
    session.save()
    response = client.get(
        "/settings/github-app/manifest/callback/?code=abc&state=mismatched"
    )
    assert b"state validation failed" in response.content.lower()
