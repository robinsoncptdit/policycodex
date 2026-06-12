from django.urls import path

from app.inventory import views


urlpatterns = [
    path("", views.inventory_page, name="inventory"),
    path("upload/", views.inventory_upload, name="inventory_upload"),
]
