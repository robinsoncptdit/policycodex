"""HTMX fragment routes for the core app, segregated under the /htmx/ prefix.

Keeping HTMX endpoints under their own namespaced prefix means a future JSON
API at /api/v1/ cannot collide, and the fragment endpoints retire cleanly if a
SPA replaces the server-rendered views. APP-28b reserves `foundational_row`;
APP-28c fills in the real view body. New fragment views go here and reverse as
`htmx:<name>`.
"""
from django.urls import include, path

from core import views as core_views

app_name = "htmx"

urlpatterns = [
    path("inventory/", include("app.inventory.htmx_urls")),
    path("foundational/<slug:slug>/row/", core_views.foundational_row, name="foundational_row"),
]
