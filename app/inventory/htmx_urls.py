"""HTMX URL routes for inventory. DISC-13 wires the live status endpoint;
DISC-12 needs the URL name to resolve in templates."""
from django.urls import path
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required


@login_required
def _status_stub(request):
    """Returns an empty fragment until DISC-13 lands the real polling view."""
    return HttpResponse("<div></div>")


urlpatterns = [
    path("status/", _status_stub, name="htmx_inventory_status"),
]
