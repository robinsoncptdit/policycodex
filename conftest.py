"""Root pytest conftest.

Override the static-files storage backend during tests so that
{% static %} tags in templates resolve without a collected manifest.
CompressedManifestStaticFilesStorage (the production backend) raises
ValueError for any file that hasn't been through collectstatic; plain
StaticFilesStorage just returns the URL without manifest lookup.
"""
import pytest


@pytest.fixture(autouse=True)
def _use_plain_static_storage(settings):
    settings.STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }
