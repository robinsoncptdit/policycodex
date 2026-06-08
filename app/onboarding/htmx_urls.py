"""APP-28c: onboarding HTMX fragment routes, mounted under /htmx/onboarding/.
No app_name: names fold into the parent `htmx` namespace (reverse as
`htmx:onboarding_screen7`)."""
from django.urls import path

from app.onboarding import retention_policy

urlpatterns = [
    path("screen7/", retention_policy.screen7_fragment, name="onboarding_screen7"),
]
