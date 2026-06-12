from django.urls import path

from app.inventory import views


urlpatterns = [
    path("", views.inventory_page, name="inventory"),
    path("upload/", views.inventory_upload, name="inventory_upload"),
    path("item/<int:item_id>/retry/", views.retry_item, name="inventory_retry_item"),
    path("run/<int:run_id>/retry/", views.retry_run, name="inventory_retry_run"),
]
