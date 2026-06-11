from django.urls import path

from app.settings import views


urlpatterns = [
    path("", views.settings_root, name="settings_root"),
    path("<slug:slug>/", views.settings_panel_view, name="settings_panel"),
]
