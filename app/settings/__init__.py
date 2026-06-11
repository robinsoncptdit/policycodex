# TODO: delete _autoload_panels and _PlaceholderGitHubApp when the real
# GitHub App panel lands; real panel modules will register themselves on
# import via app.settings.registry.register().
def _autoload_panels():
    from django.http import HttpResponse
    from app.settings.base import SettingsPanel
    from app.settings.registry import register

    class _PlaceholderGitHubApp(SettingsPanel):
        slug = "github-app"
        title = "GitHub App"
        nav_group = "Credentials"
        def render(self, request):
            return HttpResponse("GitHub App settings panel (coming soon).", status=200)
        def save(self, request):
            return HttpResponse("Stub save.", status=200)

    register(_PlaceholderGitHubApp())
    import app.settings.panels.llm_provider  # noqa: F401


_autoload_panels()
