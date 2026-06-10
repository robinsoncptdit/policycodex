"""Tests for onboarding forms (APP-09 / DISC-03)."""
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from app.onboarding.forms import (
    GitHubRepoForm,
    RetentionPolicyUploadForm,
    form_class_for,
)


def test_registry_maps_github_repo():
    assert form_class_for("github-repo") is GitHubRepoForm
    assert form_class_for("configuration") is None


@pytest.mark.skip(reason="DISC-06: llm-provider form moves to its own screen handler")
def test_registry_maps_llm_provider():
    pass  # DISC-06 will register the new llm-provider form


def test_valid_connect():
    form = GitHubRepoForm(data={
        "mode": "connect",
        "repo_url": "https://github.com/acme/policies",
        "branch": "main",
    })
    assert form.is_valid(), form.errors
    assert form.cleaned_data["mode"] == "connect"
    assert form.cleaned_data["repo_url"] == "https://github.com/acme/policies"


def test_valid_create():
    form = GitHubRepoForm(data={
        "mode": "create",
        "org": "acme",
        "repo_name": "policies",
        "branch": "main",
    })
    assert form.is_valid(), form.errors
    assert form.cleaned_data["org"] == "acme"
    assert form.cleaned_data["repo_name"] == "policies"


def test_connect_requires_repo_url():
    form = GitHubRepoForm(data={"mode": "connect", "branch": "main"})
    assert not form.is_valid()
    assert "repo_url" in form.errors


def test_connect_rejects_non_github_url():
    form = GitHubRepoForm(data={
        "mode": "connect",
        "repo_url": "https://gitlab.com/acme/policies",
        "branch": "main",
    })
    assert not form.is_valid()
    assert "repo_url" in form.errors


def test_create_requires_org_and_repo_name():
    form = GitHubRepoForm(data={"mode": "create", "branch": "main"})
    assert not form.is_valid()
    assert "org" in form.errors
    assert "repo_name" in form.errors


def test_branch_defaults_to_main():
    # branch omitted -> field initial is "main"; an unbound form exposes it.
    form = GitHubRepoForm()
    assert form.fields["branch"].initial == "main"


def test_connect_rejects_deep_github_path():
    # A clone target is owner/repo, not a deep path like /tree/main.
    form = GitHubRepoForm(data={
        "mode": "connect",
        "repo_url": "https://github.com/acme/policies/tree/main",
        "branch": "main",
    })
    assert not form.is_valid()
    assert "repo_url" in form.errors


def test_connect_accepts_dot_git_and_trailing_slash():
    for url in (
        "https://github.com/acme/policies.git",
        "https://github.com/acme/policies/",
    ):
        form = GitHubRepoForm(data={"mode": "connect", "repo_url": url, "branch": "main"})
        assert form.is_valid(), (url, form.errors)


def test_retention_upload_requires_a_file():
    form = RetentionPolicyUploadForm(data={}, files={})
    assert not form.is_valid()
    assert "pdf_file" in form.errors


def test_retention_upload_rejects_non_pdf():
    upload = SimpleUploadedFile("policy.txt", b"hello", content_type="text/plain")
    form = RetentionPolicyUploadForm(data={}, files={"pdf_file": upload})
    assert not form.is_valid()
    assert "pdf_file" in form.errors


def test_retention_upload_accepts_pdf():
    upload = SimpleUploadedFile("policy.pdf", b"%PDF-1.4 ...", content_type="application/pdf")
    form = RetentionPolicyUploadForm(data={}, files={"pdf_file": upload})
    assert form.is_valid(), form.errors


def test_retention_upload_accepts_uppercase_extension():
    upload = SimpleUploadedFile("POLICY.PDF", b"%PDF-1.4 ...", content_type="application/pdf")
    form = RetentionPolicyUploadForm(data={}, files={"pdf_file": upload})
    assert form.is_valid(), form.errors


@pytest.mark.skip(reason="DISC-06: LLMProviderForm removed; new screen owns its form")
@pytest.mark.parametrize(
    "value", ["claude", "openai", "gemini", "azure-openai", "local-llama"]
)
def test_llm_provider_accepts_each_choice(value):
    pass


@pytest.mark.skip(reason="DISC-06: LLMProviderForm removed; new screen owns its form")
def test_llm_provider_rejects_unknown_choice():
    pass


@pytest.mark.skip(reason="DISC-06: LLMProviderForm removed; new screen owns its form")
def test_llm_provider_requires_a_choice():
    pass


@pytest.mark.skip(reason="DISC-06: LLMProviderForm removed; new screen owns its form")
def test_llm_provider_defaults_to_claude():
    pass
