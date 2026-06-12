"""Diocese configuration: address scheme + versioning + reviewer roles +
retention defaults. Save opens a PR to .policycodex/config.yaml via the
existing propose_change service."""
from __future__ import annotations

import uuid

import yaml

from django import forms
from django.shortcuts import render

from app.git_provider.github_provider import GitHubProvider
from app.git_provider.propose import propose_change
from app.working_copy.config import load_working_copy_config
from app.settings.base import SettingsPanel
from app.settings.registry import register


ADDRESS_SCHEMES = [
    ("chapter-section-item", "Chapter-Section-Item (LA default)"),
    ("department-code", "Department code (Catholic healthcare)"),
]
VERSIONING = [
    ("semver", "Semantic versioning (1.0, 1.1, 2.0) — recommended"),
]
_CONFIG_REL_PATH = ".policycodex/config.yaml"


class _Form(forms.Form):
    address_scheme = forms.ChoiceField(choices=ADDRESS_SCHEMES, initial="chapter-section-item")
    versioning = forms.ChoiceField(choices=VERSIONING, initial="semver")
    reviewer_roles = forms.CharField(
        initial="CFO,HR Director,General Counsel",
        help_text="Comma-separated list of reviewer titles.",
    )
    retention_admin_years = forms.IntegerField(initial=7, min_value=1, max_value=99)
    retention_operational_years = forms.IntegerField(initial=3, min_value=1, max_value=99)

    def to_yaml(self) -> str:
        data = self.cleaned_data
        return yaml.safe_dump({
            "schema_version": 1,
            "address_scheme": data["address_scheme"],
            "versioning": data["versioning"],
            "reviewer_roles": [r.strip() for r in data["reviewer_roles"].split(",") if r.strip()],
            "retention_defaults": {
                "admin_years": data["retention_admin_years"],
                "operational_years": data["retention_operational_years"],
            },
        }, sort_keys=False)


class ConfigurationPanel(SettingsPanel):
    slug = "configuration"
    title = "Configuration"
    nav_group = "Diocese"

    def is_configured(self, request) -> bool:
        from app.credentials import store
        return store.has("diocese.config_pushed") and bool(store.get("diocese.config_pushed"))

    def render(self, request, *, form=None, message=None, error=None, pr_url=None):
        from app.settings.views import _nav_groups
        return render(request, "settings/panels/configuration.html", {
            "active_slug": self.slug,
            "panel_title": self.title,
            "nav_groups": _nav_groups(request),
            "form": form or _Form(),
            "message": message,
            "error": error,
            "pr_url": pr_url,
        })

    def save(self, request):
        form = _Form(request.POST)
        if not form.is_valid():
            return self.render(request, form=form)
        try:
            config = load_working_copy_config()
        except RuntimeError as exc:
            return self.render(request, form=form,
                               error=f"Policy repository is not configured: {exc}")
        # Write the YAML to disk before opening the PR. propose_change reads
        # files from the working copy on the new branch.
        config_path = config.working_dir / _CONFIG_REL_PATH
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(form.to_yaml(), encoding="utf-8")
        author_email = request.user.email or f"{request.user.username}@policycodex"
        commit_message = (
            "Update diocese configuration\n\n"
            "Co-Authored-By: PolicyCodex <bot@policycodex>\n"
            f"Co-Authored-By: {request.user.username} <{author_email}>"
        )
        try:
            pr = propose_change(
                provider=GitHubProvider(),
                working_dir=config.working_dir,
                default_branch=config.branch,
                branch_name=f"policycodex/config-{uuid.uuid4().hex[:8]}",
                files=[config_path],
                commit_message=commit_message,
                author_name=request.user.username,
                author_email=author_email,
                pr_title="Update diocese configuration",
                pr_body="Saved from PolicyCodex Settings → Diocese configuration.",
            )
        except Exception as exc:  # noqa: BLE001 surfaced to user
            return self.render(request, form=form, error=str(exc))
        from app.credentials import store
        store.set("diocese.config_pushed", "true")
        return self.render(request, form=form,
                           message="Configuration change submitted.",
                           pr_url=pr.get("url"))


register(ConfigurationPanel())
