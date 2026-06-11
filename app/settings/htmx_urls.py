from django.urls import path

from app.settings import views


urlpatterns = [
    path("<slug:slug>/test/", views.settings_panel_test, name="htmx_settings_test"),
]
