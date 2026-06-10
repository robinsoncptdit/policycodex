"""URL routes for the onboarding wizard (DISC-03)."""
from django.urls import include, path

from . import views

urlpatterns = [
    path("", views.onboarding_root, name="onboarding"),
    path("inventory/", include("app.inventory.urls")),
    path("<slug:step>/", views.onboarding_step, name="onboarding_step"),
]
