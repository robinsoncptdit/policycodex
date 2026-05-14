"""URL routes for the core app."""
from django.urls import path

from . import views


urlpatterns = [
    path("", views.root_redirect, name="root"),
    path("health/", views.health, name="health"),
    path("catalog/", views.catalog, name="catalog"),
    path("policies/approve/", views.approve_pr, name="approve_pr"),
    path("policies/<slug:slug>/edit/", views.policy_edit, name="policy_edit"),
]
