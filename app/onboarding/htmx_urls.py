"""APP-28c / DISC-05: onboarding HTMX fragment routes, mounted under /htmx/onboarding/.
No app_name: names fold into the parent `htmx` namespace (reverse as
`htmx:onboarding_screen7`, `htmx:htmx_github_app_test`)."""
from django.urls import path

from app.onboarding import retention_policy
from app.onboarding.screens import github_app

urlpatterns = [
    path("screen7/", retention_policy.screen7_fragment, name="onboarding_screen7"),
    path("github-app/test/", github_app.test_connection, name="htmx_github_app_test"),
]
