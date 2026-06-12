"""Users + role assignment + delete. v0.1 roles: Viewer / Editor / Admin
(Django groups; Admin == is_superuser). Reviewer/Publisher are v0.2."""
from __future__ import annotations

import secrets

from django.shortcuts import render

from app.settings.base import SettingsPanel
from app.settings.registry import register


_ROLE_NAMES = ("Viewer", "Editor", "Admin")


def _get_user_model():
    from django.contrib.auth import get_user_model
    return get_user_model()


def _get_group_model():
    from django.contrib.auth.models import Group
    return Group


def _user_role(user) -> str:
    if user.is_superuser:
        return "Admin"
    for name in ("Editor", "Viewer"):
        if user.groups.filter(name=name).exists():
            return name
    return "Viewer"


def _set_role(user, role: str) -> None:
    Group = _get_group_model()
    user.groups.clear()
    if role == "Admin":
        user.is_superuser = True
        # is_staff grants Django /admin/ access; intentional for v0.1.
        user.is_staff = True
        user.save()
        return
    user.is_superuser = False
    user.is_staff = False
    user.save()
    user.groups.add(Group.objects.get(name=role))


def _gen_temp_password() -> str:
    """16-char URL-safe random. Long enough to satisfy MinimumLength;
    random enough to defeat zxcvbn until the user changes it."""
    return secrets.token_urlsafe(12)


class UsersPanel(SettingsPanel):
    slug = "users"
    title = "Users and roles"
    nav_group = "Admin"

    def is_configured(self, request) -> bool:
        # Users panel is "configured" once at least one non-superuser has been added.
        from django.contrib.auth import get_user_model
        User = get_user_model()
        return User.objects.filter(is_superuser=False).exists()

    def render(self, request, *, message=None, error=None, last_temp=None):
        from app.settings.views import _nav_groups
        User = _get_user_model()
        users = (
            User.objects.all()
            .select_related("profile")
            .order_by("date_joined")
        )
        return render(request, "settings/panels/users.html", {
            "active_slug": self.slug,
            "panel_title": self.title,
            "nav_groups": _nav_groups(request),
            "users": [(u, _user_role(u)) for u in users],
            "role_choices": _ROLE_NAMES,
            "message": message,
            "error": error,
            "last_temp_password": last_temp,
        })

    def save(self, request):
        action = request.POST.get("action")
        if action == "add":
            return self._add(request)
        if action == "change_role":
            return self._change_role(request)
        if action == "delete":
            return self._delete(request)
        return self.render(request, error=f"Unknown action: {action}")

    def _add(self, request):
        User = _get_user_model()
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        role = request.POST.get("role", "Viewer")
        if not username or role not in _ROLE_NAMES:
            return self.render(request, error="Username and a valid role are required.")
        if User.objects.filter(username=username).exists():
            return self.render(request, error=f"User {username} already exists.")
        temp = _gen_temp_password()
        user = User.objects.create_user(username=username, email=email, password=temp)
        _set_role(user, role)
        return self.render(
            request,
            message=f"User {username} created. Give them this temporary password:",
            last_temp=temp,
        )

    def _change_role(self, request):
        User = _get_user_model()
        user_id = request.POST.get("user_id")
        role = request.POST.get("role")
        if role not in _ROLE_NAMES:
            return self.render(request, error="Invalid role.")
        user = User.objects.filter(pk=user_id).first()
        if user is None:
            return self.render(request, error="User not found.")
        # Prevent demoting the last superuser.
        if user.is_superuser and role != "Admin":
            if User.objects.filter(is_superuser=True).count() == 1:
                return self.render(
                    request,
                    error="Cannot demote the last administrator. Add another admin first.",
                )
        _set_role(user, role)
        return self.render(request, message=f"{user.username} is now {role}.")

    def _delete(self, request):
        User = _get_user_model()
        user_id = request.POST.get("user_id")
        confirm = request.POST.get("confirm_token", "")
        user = User.objects.filter(pk=user_id).first()
        if user is None:
            return self.render(request, error="User not found.")
        expected = f"DELETE {user.username}"
        if confirm != expected:
            return self.render(request, error=f"Confirmation must be exactly: {expected}")
        if user.is_superuser and User.objects.filter(is_superuser=True).count() == 1:
            return self.render(request, error="Cannot delete the last administrator.")
        username = user.username
        user.delete()
        return self.render(request, message=f"User {username} deleted.")


register(UsersPanel())
