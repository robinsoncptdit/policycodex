"""Map a Django User to a Git author identity.

Consumed by callers of :class:`app.git_provider.GitHubProvider.commit`, which
takes ``author_name`` and ``author_email`` as positional args. The point of
this module is to keep the User-to-author mapping in one place so callers don't
each invent their own fallback rules.
"""

from __future__ import annotations


def get_git_author(user) -> tuple[str, str]:
    """Map a Django ``User`` to a ``(name, email)`` tuple for Git commits.

    Rules:

    * ``name`` is the user's full name when set, otherwise the username.
    * ``email`` is the user's email when set, otherwise a synthesized
      ``{username}@policycodex.local`` placeholder so Git still gets a
      syntactically valid address.

    A ``None`` user or an unauthenticated user (e.g. ``AnonymousUser``) raises
    ``ValueError``. Callers should gate this on ``request.user.is_authenticated``
    before calling.
    """
    if user is None:
        raise ValueError("get_git_author requires an authenticated user, got None")

    # AnonymousUser and any other unauthenticated principal must not produce a
    # commit identity. Checking the attribute defensively rather than importing
    # AnonymousUser keeps this function importable outside a Django request
    # context (e.g. from management commands or unit tests).
    is_authenticated = getattr(user, "is_authenticated", False)
    if not is_authenticated:
        raise ValueError(
            "get_git_author requires an authenticated user; "
            "got an unauthenticated principal"
        )

    full_name = ""
    get_full_name = getattr(user, "get_full_name", None)
    if callable(get_full_name):
        # ``get_full_name`` on the default User model returns ``"First Last"``
        # already stripped, but be defensive in case a custom user model
        # returns something with surrounding whitespace.
        full_name = (get_full_name() or "").strip()

    username = getattr(user, "username", "") or ""
    email = getattr(user, "email", "") or ""

    name = full_name or username
    if not name:
        # Should not happen for a real authenticated user, but if both
        # full name and username are empty, we cannot produce a usable
        # identity.
        raise ValueError(
            "get_git_author cannot derive a name: user has no full name and no username"
        )

    if not email:
        email = f"{username}@policycodex.local" if username else f"{name}@policycodex.local"

    return (name, email)
