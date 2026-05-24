"""URL routes for the onboarding wizard (APP-08)."""
from django.urls import path

from . import views

urlpatterns = [
    path("", views.onboarding_root, name="onboarding"),
    path("<slug:step>/", views.onboarding_step, name="onboarding_step"),
]
