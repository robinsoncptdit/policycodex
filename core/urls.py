"""URL routes for the core app."""
from django.urls import include, path

from . import views


urlpatterns = [
    path("", views.root_redirect, name="root"),
    path("accounts/password/change/", views.ForcedPasswordChangeView.as_view(), name="password_change"),
    path("health/", views.health, name="health"),
    # APP-27: HTMX fragment endpoints are segregated under /htmx/ (namespace
    # `htmx`). Empty for now; APP-28c adds the first fragment views.
    path("htmx/", include("core.htmx_urls")),
    path("catalog/", views.catalog, name="catalog"),
    path("policies/approve/", views.approve_pr, name="approve_pr"),
    path("policies/<slug:slug>/edit/", views.policy_edit, name="policy_edit"),
    path(
        "policies/<slug:slug>/foundational-edit/",
        views.foundational_edit,
        name="foundational_edit",
    ),
    path("policies/<slug:slug>/publish/", views.publish_policy, name="publish_policy"),
    path("policies/<slug:slug>/", views.policy_detail, name="policy_detail"),
]
