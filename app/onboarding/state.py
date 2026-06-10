"""Session-backed wizard state for onboarding (APP-08).

Wraps a single Django session key. Mutating a nested dict inside a Django
session does NOT auto-flag it dirty, so every mutator sets
session.modified = True.
"""
from __future__ import annotations

from app.onboarding.wizard import first_step, index_of

SESSION_KEY = "onboarding"


class WizardState:
    def __init__(self, session):
        self._session = session
        if SESSION_KEY not in session:
            session[SESSION_KEY] = {
                "current_step": first_step().slug,
                "completed": [],
                "data": {},
            }
            session.modified = True

    @property
    def _store(self) -> dict:
        return self._session[SESSION_KEY]

    @property
    def current_step(self) -> str:
        return self._store.get("current_step", first_step().slug)

    def set_current(self, slug: str) -> None:
        self._store["current_step"] = slug
        self._session.modified = True

    def get_data(self, slug: str) -> dict:
        # Return a copy. Callers that mutate the result must write back through
        # set_data; otherwise they would change the session store without it
        # being flagged modified. APP-09..16 read this per screen.
        return dict(self._store["data"].get(slug, {}))

    def set_data(self, slug: str, data: dict) -> None:
        self._store["data"][slug] = data
        self._session.modified = True

    def mark_complete(self, slug: str) -> None:
        if slug not in self._store["completed"]:
            self._store["completed"].append(slug)
            self._session.modified = True

    def is_complete(self, slug: str) -> bool:
        return slug in self._store["completed"]

    def furthest_step(self) -> str:
        best_slug = first_step().slug
        best_idx = 0
        for slug in (self.current_step, *self._store["completed"]):
            idx = index_of(slug)
            if idx is not None and idx > best_idx:
                best_idx = idx
                best_slug = slug
        return best_slug

    def bootstrap_complete(self) -> bool:
        """All three bootstrap screens (admin, github-app, llm-provider) completed."""
        from app.credentials import store
        bootstrap_slugs = ("admin-account", "github-app", "llm-provider")
        if not all(self.is_complete(slug) for slug in bootstrap_slugs):
            return False
        try:
            return store.first_boot_complete()
        except RuntimeError:
            return False

    def all_data(self) -> dict:
        return dict(self._store["data"])

    def reset(self) -> None:
        self._session.pop(SESSION_KEY, None)
        self._session.modified = True
