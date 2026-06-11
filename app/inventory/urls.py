"""Inventory URL module (DISC-10 stub; DISC-12 wires the real view)."""
from django.urls import path

from app.inventory import views

urlpatterns = [
    path("", views.inventory_page_stub, name="inventory"),
]
