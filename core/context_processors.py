"""Template context processors for the core app."""
from django.conf import settings


def source_url(request):
    """Expose the AGPL source-link target to every template."""
    return {"source_url": settings.POLICYCODEX_SOURCE_URL}


def _safe_lifecycle_state(request):
    """Wrap lifecycle_state so a credential-store fault never breaks a request."""
    from core.lifecycle import lifecycle_state
    try:
        return lifecycle_state(request)
    except Exception:
        # Intentionally broad — render path must never raise.
        return None


def configure_banner(request):
    if not request.user.is_authenticated:
        return {"configure_banner": None}
    state = _safe_lifecycle_state(request)
    if state is None or state.banner is None:
        return {"configure_banner": None}
    return {
        "configure_banner": {
            "message": state.banner,
            "next_url": state.next_url,
        }
    }
