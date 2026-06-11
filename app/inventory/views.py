"""DISC-10: placeholder views until DISC-12 lands the real inventory page."""
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse


@login_required
def inventory_page_stub(request):
    """DISC-10: placeholder until DISC-12 lands the real page."""
    return HttpResponse("Inventory page lands in DISC-12.")
