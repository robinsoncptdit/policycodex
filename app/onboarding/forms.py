"""Onboarding wizard forms + a slug->form registry (APP-09).

Each wizard step may register a Django Form here. The generic
`onboarding_step` view binds the registered form, validates it on
`continue`, and persists `cleaned_data` into WizardState. Steps without a
registered form keep the skeleton's no-op save behavior.

APP-09 ships the first step's form (github-repo). It captures the repo
choice only; cloning/creating the repo is deferred to wizard-completion
provisioning (APP-15/16).
"""
from __future__ import annotations

import re

from django import forms

# Mirrors app/git_provider/github_provider.py's owner/repo URL shape.
_GITHUB_URL_RE = re.compile(r"^https://github\.com/[^/]+/.+?(?:\.git)?/?$")


class GitHubRepoForm(forms.Form):
    MODE_CHOICES = [
        ("connect", "Connect an existing repository"),
        ("create", "Create a new repository"),
    ]

    mode = forms.ChoiceField(
        choices=MODE_CHOICES,
        widget=forms.RadioSelect,
        initial="connect",
        label="Repository",
    )
    repo_url = forms.URLField(
        required=False,
        label="Existing repository URL",
        help_text="For Connect: https://github.com/<org>/<repo>",
    )
    org = forms.CharField(
        required=False,
        label="GitHub organization or owner",
        help_text="For Create",
    )
    repo_name = forms.CharField(
        required=False,
        label="New repository name",
        help_text="For Create",
    )
    branch = forms.CharField(initial="main", label="Default branch")

    def clean(self):
        cleaned = super().clean()
        mode = cleaned.get("mode")
        if mode == "connect":
            url = cleaned.get("repo_url")
            if not url:
                self.add_error("repo_url", "Provide the existing repository URL.")
            elif not _GITHUB_URL_RE.match(url):
                self.add_error(
                    "repo_url",
                    "Must be an https://github.com/<org>/<repo> URL.",
                )
        elif mode == "create":
            if not cleaned.get("org"):
                self.add_error("org", "Provide the organization or owner.")
            if not cleaned.get("repo_name"):
                self.add_error("repo_name", "Provide the new repository name.")
        return cleaned


_FORMS = {
    "github-repo": GitHubRepoForm,
}


def form_class_for(slug):
    """Return the Form class registered for a wizard step slug, or None."""
    return _FORMS.get(slug)
