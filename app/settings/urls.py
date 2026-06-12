from django.urls import path

from app.settings import views
from app.settings.panels import github_app_manifest


urlpatterns = [
    path("", views.settings_root, name="settings_root"),
    path("github-app/manifest/start/", github_app_manifest.manifest_start, name="github_app_manifest_start"),
    path("github-app/manifest/callback/", github_app_manifest.manifest_callback, name="github_app_manifest_callback"),
    path("<slug:slug>/", views.settings_panel_view, name="settings_panel"),
]
