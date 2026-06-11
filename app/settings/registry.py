"""Panel registry. Panels are listed in nav order; the first slug is the
landing page when the user hits /settings/."""
from typing import Sequence

from app.settings.base import SettingsPanel


_PANELS: list[SettingsPanel] = []


def register(panel: SettingsPanel) -> SettingsPanel:
    _PANELS.append(panel)
    return panel


def all_panels() -> Sequence[SettingsPanel]:
    return tuple(_PANELS)


def get_panel(slug: str) -> SettingsPanel | None:
    for p in _PANELS:
        if p.slug == slug:
            return p
    return None


def first_slug() -> str | None:
    return _PANELS[0].slug if _PANELS else None
