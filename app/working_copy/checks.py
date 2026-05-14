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

from pathlib import Path
from typing import Sequence

from django.conf import settings
from django.core.checks import Error, Warning, register

from app.working_copy.config import load_working_copy_config
from ingest.policy_reader import BundleAwarePolicyReader, BundleError


REQUIRED_CAPABILITIES: tuple[str, ...] = ("classifications", "retention-schedule")


@register()
def foundational_policy_check(app_configs, **kwargs) -> Sequence:
    """Return a list of Error/Warning objects; empty list means pass."""
    onboarding_complete = bool(getattr(settings, "POLICYCODEX_ONBOARDING_COMPLETE", False))

    # Resolve the working copy config. Unset POLICYCODEX_POLICY_REPO_URL is
    # an infrastructure-level failure: Warning during onboarding, Error after.
    try:
        config = load_working_copy_config()
    except RuntimeError as exc:
        if onboarding_complete:
            return [Error(
                f"Working copy not configured: {exc}",
                hint="Set POLICYCODEX_POLICY_REPO_URL to the diocese's policy repo URL.",
                id="policycodex.E004",
            )]
        return [Warning(
            f"Working copy not yet configured: {exc}",
            hint="Complete the onboarding wizard to set POLICYCODEX_POLICY_REPO_URL.",
            id="policycodex.W001",
        )]

    policies_dir = config.working_dir / "policies"
    if not policies_dir.exists():
        if onboarding_complete:
            return [Error(
                f"Policies directory not found: {policies_dir}",
                hint="Run `python manage.py pull_working_copy` to sync the diocese's policy repo.",
                id="policycodex.E005",
            )]
        return [Warning(
            f"Policies directory not yet present: {policies_dir}",
            hint="The onboarding wizard will run `pull_working_copy` to create it.",
            id="policycodex.W002",
        )]

    # Bundle-validity failures (broken YAML, missing files) propagate as
    # Error regardless of onboarding state.
    try:
        policies = list(BundleAwarePolicyReader(policies_dir).read())
    except BundleError as exc:
        return [Error(
            f"Broken foundational-policy bundle: {exc}",
            hint="Fix the offending file in the diocese's policy repo and re-sync via `python manage.py pull_working_copy`.",
            id="policycodex.E001",
        )]

    # Capability validation: every required capability must be provided by
    # exactly one foundational policy.
    errors = []
    for capability in REQUIRED_CAPABILITIES:
        providers = [p for p in policies if p.foundational and capability in p.provides]
        if len(providers) == 0:
            errors.append(Error(
                f"No foundational policy provides the `{capability}` capability.",
                hint=(
                    f"Add a policy bundle whose policy.md declares `foundational: true` "
                    f"and `provides: [{capability}, ...]`. See "
                    "internal/PolicyWonk-Foundational-Policy-Design.md."
                ),
                id="policycodex.E002",
            ))
        elif len(providers) > 1:
            paths = ", ".join(str(p.policy_path) for p in providers)
            errors.append(Error(
                f"Multiple foundational policies provide the `{capability}` capability: {paths}",
                hint=(
                    f"Only one policy should declare `provides: [{capability}]`. "
                    "Remove the duplicate or merge."
                ),
                id="policycodex.E003",
            ))

    return errors
