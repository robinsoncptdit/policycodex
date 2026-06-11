"""URL routes for the inventory page (DISC-12)."""
from django.urls import path

from app.inventory import views

urlpatterns = [
    path("", views.inventory_page, name="inventory"),
]
