"""Tests for the Django-User-to-Git-author mapping (APP-02)."""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser

from core.git_identity import get_git_author


@pytest.fixture
def User():
    return get_user_model()


def test_full_name_and_email(db, User):
    user = User.objects.create_user(
        username="alice",
        email="alice@example.com",
        first_name="Alice",
        last_name="Anderson",
    )
    assert get_git_author(user) == ("Alice Anderson", "alice@example.com")


def test_username_falls_back_when_no_full_name(db, User):
    user = User.objects.create_user(
        username="bob",
        email="bob@example.com",
    )
    assert get_git_author(user) == ("bob", "bob@example.com")


def test_synthesized_email_when_user_has_no_email(db, User):
    user = User.objects.create_user(username="carol")
    assert get_git_author(user) == ("carol", "carol@policycodex.local")


def test_first_name_only(db, User):
    user = User.objects.create_user(
        username="dave",
        email="dave@example.com",
        first_name="Dave",
    )
    # Django's get_full_name() returns "First " stripped -> "Dave".
    name, email = get_git_author(user)
    assert name == "Dave"
    assert email == "dave@example.com"


def test_last_name_only(db, User):
    user = User.objects.create_user(
        username="eve",
        email="eve@example.com",
        last_name="Edwards",
    )
    name, email = get_git_author(user)
    assert name == "Edwards"
    assert email == "eve@example.com"


def test_full_name_with_no_email_synthesizes_email_from_username(db, User):
    user = User.objects.create_user(
        username="frank",
        first_name="Frank",
        last_name="Foster",
    )
    assert get_git_author(user) == ("Frank Foster", "frank@policycodex.local")


def test_anonymous_user_raises_value_error():
    with pytest.raises(ValueError, match="authenticated"):
        get_git_author(AnonymousUser())


def test_none_raises_value_error():
    with pytest.raises(ValueError, match="None"):
        get_git_author(None)


def test_returns_tuple_of_strings(db, User):
    user = User.objects.create_user(
        username="grace",
        email="grace@example.com",
        first_name="Grace",
        last_name="Green",
    )
    result = get_git_author(user)
    assert isinstance(result, tuple)
    assert len(result) == 2
    assert isinstance(result[0], str)
    assert isinstance(result[1], str)
