from django.urls import path

from app.inventory import views


urlpatterns = [
    path("status/", views.status_fragment, name="htmx_inventory_status"),
]
