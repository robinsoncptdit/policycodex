from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponseNotAllowed
from django.shortcuts import redirect

from app.settings import registry
from core.permissions import require_role


@require_role("Admin")
def settings_root(request):
    slug = registry.first_slug()
    if slug is None:
        raise Http404("No settings panels registered.")
    return redirect("settings_panel", slug=slug)


@require_role("Admin")
def settings_panel_view(request, slug):
    panel = registry.get_panel(slug)
    if panel is None:
        raise Http404(f"Unknown settings panel: {slug}")
    if not panel.can_access(request.user):
        raise PermissionDenied
    if request.method == "GET":
        return panel.render(request)
    if request.method == "POST":
        return panel.save(request)
    return HttpResponseNotAllowed(["GET", "POST"])


@require_role("Admin")
def settings_panel_test(request, slug):
    panel = registry.get_panel(slug)
    if panel is None:
        raise Http404(f"Unknown settings panel: {slug}")
    if not panel.can_access(request.user):
        raise PermissionDenied
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    result = panel.test(request)
    if result is None:
        raise Http404("Panel has no test endpoint.")
    return result
