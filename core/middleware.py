from django.shortcuts import redirect
from django.urls import reverse


_EXEMPT_PREFIXES = (
    "/login/",
    "/logout/",
    "/accounts/password/change/",
    "/health/",
    "/static/",
    "/admin/login/",
    "/admin/logout/",
)


class ForcePasswordChangeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            if not any(request.path.startswith(p) for p in _EXEMPT_PREFIXES):
                profile = getattr(request.user, "profile", None)
                if profile is not None and profile.must_change_password:
                    change_url = reverse("password_change")
                    return redirect(f"{change_url}?next={request.path}")
        return self.get_response(request)
