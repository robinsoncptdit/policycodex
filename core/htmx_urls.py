"""HTMX fragment routes for the core app, segregated under the /htmx/ prefix.

Keeping HTMX endpoints under their own namespaced prefix means a future JSON
API at /api/v1/ cannot collide, and the fragment endpoints retire cleanly if a
SPA replaces the server-rendered views. No endpoints exist yet (APP-27 lays the
convention); APP-28c adds the first ones (PDF upload -> live extraction,
typed-table row-add). New fragment views go here and reverse as `htmx:<name>`.
"""
from django.urls import path  # noqa: F401  (used once endpoints land)

app_name = "htmx"

urlpatterns = []
