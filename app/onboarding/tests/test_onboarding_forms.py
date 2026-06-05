"""Tests for onboarding forms (APP-09)."""
from django.core.files.uploadedfile import SimpleUploadedFile

from app.onboarding.forms import GitHubRepoForm, RetentionPolicyUploadForm, form_class_for


def test_registry_maps_github_repo():
    assert form_class_for("github-repo") is GitHubRepoForm
    assert form_class_for("address-scheme") is None


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
