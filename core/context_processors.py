"""Template context processors for the core app."""
from django.conf import settings


def source_url(request):
    """Expose the AGPL source-link target to every template."""
    return {"source_url": settings.POLICYCODEX_SOURCE_URL}
