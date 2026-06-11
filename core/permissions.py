"""Group-based access decorators.

v0.1 has three groups: Viewer / Editor / Admin. Each user is in zero or
one group. Admin is is_superuser=True. Group membership is the coarse
capability check; Django's per-permission system is unused in v0.1.
"""
from functools import wraps
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


_ROLE_ORDER = ("Viewer", "Editor", "Admin")


def _user_role_index(user):
    if user.is_superuser:
        return _ROLE_ORDER.index("Admin")
    for i, name in enumerate(_ROLE_ORDER):
        if user.groups.filter(name=name).exists():
            return i
    return -1


def require_role(minimum):
    """Require the user be in a group at or above `minimum` (Viewer/Editor/Admin)."""
    needed = _ROLE_ORDER.index(minimum)

    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapped(request, *args, **kwargs):
            if _user_role_index(request.user) < needed:
                raise PermissionDenied
            return view_func(request, *args, **kwargs)
        return wrapped
    return decorator
