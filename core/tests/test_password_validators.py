import pytest
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth import get_user_model

User = get_user_model()


def test_minimum_length_12():
    with pytest.raises(ValidationError) as exc:
        validate_password("Strong5!")  # 8 chars
    assert "too short" in str(exc.value).lower()


def test_common_password_rejected():
    with pytest.raises(ValidationError):
        validate_password("password1234")  # common + too obvious


def test_zxcvbn_rejects_predictable():
    """P@ssw0rd1234 is a leet-speak substitution; zxcvbn scores it 1 (< min_score 3)."""
    with pytest.raises(ValidationError):
        validate_password("P@ssw0rd1234")


def test_strong_passphrase_accepted():
    validate_password("kestrel-sapphire-meadow-91")  # should not raise


@pytest.mark.django_db
def test_similarity_to_username_rejected():
    user = User.objects.create_user(username="alicewilson", password="x")
    with pytest.raises(ValidationError):
        validate_password("alicewilson1234567", user=user)
