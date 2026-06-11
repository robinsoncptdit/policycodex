import importlib
_mod = importlib.import_module("core.migrations.0002_seed_default_admin")
_seed_default_admin_callable = _mod._seed_default_admin_callable
