"""URL routes for the core app."""
from django.urls import path

from . import views


urlpatterns = [
    path("health/", views.health, name="health"),
    path("catalog/", views.catalog, name="catalog"),
]
