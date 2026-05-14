"""Foundational-policy startup self-check (APP-21).

Validates that every required `provides:` capability is satisfied by
exactly one published foundational policy in the local working copy.

Failure severity is gated by the POLICYCODEX_ONBOARDING_COMPLETE setting:
- False (default): missing working copy or unset repo URL returns Warning,
  letting `manage.py runserver` start during the seven-screen onboarding
  wizard. Bundle-validity failures (broken data.yaml, missing or duplicate
  capability provider) are always Error.
- True: all failures are Error and the app refuses to serve.
"""
from __future__ import annotations

from typing import Sequence

from django.conf import settings
from django.core.checks import Error, Warning, register


REQUIRED_CAPABILITIES: tuple[str, ...] = ("classifications", "retention-schedule")


@register()
def foundational_policy_check(app_configs, **kwargs) -> Sequence:
    """Return a list of Error/Warning objects; empty list means pass."""
    # Stub: real logic lands in Task 4 onwards. Return [] so the registration
    # smoke tests in Task 3 pass without false-positive failures.
    return []
