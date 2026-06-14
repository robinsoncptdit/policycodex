def test_services_module_imports():
    import importlib
    mod = importlib.import_module("core.services")
    assert hasattr(mod, "build_catalog")


def test_ai_stays_django_free():
    import ai.retention_extract as r, inspect
    src = inspect.getsource(r)
    assert "import django" not in src and "from app" not in src and "import app" not in src
