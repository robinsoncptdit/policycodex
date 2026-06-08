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

# An owner/repo GitHub URL: exactly two path segments (no deep paths like
# /tree/main or /blob/...), optional .git suffix and trailing slash.
_GITHUB_URL_RE = re.compile(r"^https://github\.com/[^/]+/[^/]+(?:\.git)?/?$")


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


class LLMProviderForm(forms.Form):
    PROVIDER_CHOICES = [
        ("claude", "Anthropic Claude (default)"),
        ("openai", "OpenAI"),
        ("gemini", "Google Gemini"),
        ("azure-openai", "Azure OpenAI"),
        ("local-llama", "Local Llama (self-hosted, no API key)"),
    ]

    provider = forms.ChoiceField(
        choices=PROVIDER_CHOICES,
        widget=forms.RadioSelect,
        initial="claude",
        label="LLM provider",
    )


class RetentionPolicyUploadForm(forms.Form):
    pdf_file = forms.FileField(
        label="Retention policy PDF",
        help_text="Upload your diocese's Document Retention Policy as a PDF.",
    )

    def clean_pdf_file(self):
        upload = self.cleaned_data["pdf_file"]
        if not upload.name.lower().endswith(".pdf"):
            raise forms.ValidationError("Upload a PDF file (.pdf).")
        return upload


_FORMS = {
    "github-repo": GitHubRepoForm,
    "llm-provider": LLMProviderForm,
}


def form_class_for(slug):
    """Return the Form class registered for a wizard step slug, or None."""
    return _FORMS.get(slug)
