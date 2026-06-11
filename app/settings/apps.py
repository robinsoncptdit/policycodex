from django.apps import AppConfig


class SettingsAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "app.settings"
    label = "settings_panel"  # avoid clashing with django.conf.settings
