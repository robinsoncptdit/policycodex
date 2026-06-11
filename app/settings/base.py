"""SettingsPanel ABC + value types.

Every panel implements render() and save(). test(), setup_actions(),
danger_actions(), and can_access() have safe defaults.

Value types (SetupAction, DangerAction, SaveResult, TestResult,
HelpBlock) are frozen dataclasses so they cannot be mutated after
construction — passing them between view and template is read-only.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class HelpBlock:
    title: str
    body: str  # plain text, no Markdown — keep templates safe by default
    external_link_label: str | None = None
    external_link_url: str | None = None


@dataclass(frozen=True)
class SetupAction:
    label: str
    description: str
    cta_label: str
    cta_url: str  # GET URL or HTMX endpoint
    enabled: bool = True


@dataclass(frozen=True)
class DangerAction:
    label: str
    description: str
    cta_label: str
    cta_url: str   # POST URL with 3-step confirm middleware
    confirm_token: str = ""  # if non-empty, user must type this exactly


@dataclass(frozen=True)
class SaveResult:
    ok: bool
    message: str
    pr_url: str | None = None


@dataclass(frozen=True)
class TestResult:
    state: str  # "ok" | "error"
    message: str


class SettingsPanel(ABC):
    slug: str
    title: str
    nav_group: str  # "Credentials" | "Diocese" | "Admin" | "Danger"

    @abstractmethod
    def render(self, request):
        """Return an HttpResponse for GET /settings/<slug>/."""

    @abstractmethod
    def save(self, request):
        """Handle POST /settings/<slug>/. Return HttpResponse."""

    def test(self, request):
        """Handle POST /htmx/settings/<slug>/test/. Default: no test button."""
        return None

    def setup_actions(self, request) -> list[SetupAction]:
        return []

    def danger_actions(self, request) -> list[DangerAction]:
        return []

    def can_access(self, user) -> bool:
        return user.is_superuser
