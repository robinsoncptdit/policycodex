def _autoload_panels():
    import app.settings.panels.github_app  # noqa: F401  -- first slug
    import app.settings.panels.llm_provider  # noqa: F401
    import app.settings.panels.policy_repo  # noqa: F401
    import app.settings.panels.configuration  # noqa: F401
    import app.settings.panels.users  # noqa: F401
    import app.settings.panels.reset  # noqa: F401


_autoload_panels()
