"""Django AppConfig for the working_copy app.

The class is named WorkingCopyAppConfig (NOT WorkingCopyConfig) to avoid
colliding with the WorkingCopyConfig dataclass in app/working_copy/config.py.
Django auto-discovers the checks module via the ready() hook below.
"""
from django.apps import AppConfig


class WorkingCopyAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "app.working_copy"
    label = "working_copy"

    def ready(self) -> None:
        # Import the checks module so its @register() decorators run on app load.
        from app.working_copy import checks  # noqa: F401
