def _autoload_panels():
    """Phase-by-phase autoload. Once Phase 4 lands the real modules, each
    panel module registers itself on import. Until then, register the
    smoke-test panel below so /settings/ has a target."""
    from django.http import HttpResponse
    from app.settings.base import SettingsPanel
    from app.settings.registry import register

    class _PlaceholderGitHubApp(SettingsPanel):
        slug = "github-app"
        title = "GitHub App"
        nav_group = "Credentials"
        def render(self, request):
            return HttpResponse("Stub: replaced in phase-4-19.", status=200)
        def save(self, request):
            return HttpResponse("Stub save.", status=200)

    register(_PlaceholderGitHubApp())


_autoload_panels()
