"""Reset PolicyCodex: three escalating destructive actions."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from django.shortcuts import render

from app.credentials import store
from app.settings.base import SettingsPanel
from app.settings.registry import register


def _credential_store_path() -> Path:
    return Path(os.environ.get("POLICYCODEX_CREDENTIAL_STORE_FILE", "/data/.credentials"))


def _working_copy_root() -> Path:
    # Mirror app.working_copy.config: prefer the env var, then /data/working-copy
    # in Docker, then ~/.policycodex/working-copies for dev outside Docker.
    root_raw = os.environ.get("POLICYCODEX_WORKING_COPY_ROOT", "")
    if root_raw:
        return Path(os.path.expanduser(root_raw))
    if Path("/data").exists():
        return Path("/data/working-copy")
    return Path.home() / ".policycodex" / "working-copies"


def _clear_credentials() -> None:
    path = _credential_store_path()
    if path.exists():
        path.unlink()
    store._reset_cache()


def _clear_working_copy() -> None:
    root = _working_copy_root()
    if root.exists():
        shutil.rmtree(root, ignore_errors=True)


def _clear_other_users(acting_user) -> int:
    """Delete every user except the one performing the reset."""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    qs = User.objects.exclude(pk=acting_user.pk)
    count = qs.count()
    qs.delete()
    return count


def _clear_inventory_runs() -> None:
    try:
        from app.inventory.models import InventoryRun, InventoryItem
        InventoryItem.objects.all().delete()
        InventoryRun.objects.all().delete()
    except Exception:
        pass


class ResetPanel(SettingsPanel):
    slug = "reset"
    title = "Reset PolicyCodex"
    nav_group = "Danger"

    def render(self, request, *, message=None, error=None):
        from app.settings.views import _nav_groups
        return render(request, "settings/panels/reset.html", {
            "active_slug": self.slug,
            "panel_title": self.title,
            "nav_groups": _nav_groups(),
            "message": message,
            "error": error,
        })

    def save(self, request):
        action = request.POST.get("action")
        token = request.POST.get("confirm_token", "")
        if action == "clear_credentials":
            if token != "CLEAR":
                return self.render(request, error="Type CLEAR to confirm.")
            _clear_credentials()
            return self.render(request, message="Credential store cleared.")
        if action == "disconnect_everything":
            if token != "DISCONNECT":
                return self.render(request, error="Type DISCONNECT to confirm.")
            _clear_credentials()
            _clear_working_copy()
            return self.render(request, message="Disconnected: credential store + working copy gone.")
        if action == "factory_reset":
            if token != "RESET POLICYCODEX":
                return self.render(request, error="Type RESET POLICYCODEX to confirm.")
            _clear_credentials()
            _clear_working_copy()
            removed = _clear_other_users(request.user)
            _clear_inventory_runs()
            return self.render(
                request,
                message=f"Factory reset complete. {removed} non-admin users removed.",
            )
        return self.render(request, error=f"Unknown action: {action}")


register(ResetPanel())
