"""Screen 7 (retention-policy) handler for the onboarding wizard (APP-15).

Custom flow, separate from the generic single-form step:
  GET                      -> upload form, or the review screen if a draft is staged
  POST action=extract      -> save PDF, extract text, run AI, stage draft, show review
  POST action=accept       -> scaffold the bundle from the staged draft, finish
  POST action=reupload     -> discard the staged draft, back to the upload form
  POST action=back/save_exit -> standard wizard navigation

The draft is staged on disk under the working copy (never the session) so a
large schedule cannot bloat the session.
"""
from __future__ import annotations

import logging
import shutil
from pathlib import Path

import yaml
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.http import require_POST

from ai.claude_provider import ClaudeProvider
from ai.retention_extract import (
    RetentionExtractionError,
    build_data_yaml,
    extract_retention_bundle,
)
from app.onboarding import wizard
from app.onboarding.forms import RetentionPolicyUploadForm
from app.onboarding.state import WizardState
from app.onboarding.scaffold import scaffold_retention_bundle
from app.working_copy.config import load_working_copy_config
from ingest.extractors import extract as extract_text
from ingest.extractors import pdf_has_embedded_images
from app.git_provider.github_provider import GitHubProvider
from app.onboarding.finalize import build_config_yaml, finalize_onboarding
from core.git_identity import get_git_author

logger = logging.getLogger(__name__)

STEP_SLUG = "retention-policy"
DEFAULT_TITLE = "Document Retention Policy"
DEFAULT_OWNER = "CFO"
_NARRATIVE_STUB = (
    "# Document Retention Policy\n\n"
    "This foundational policy was bootstrapped from the uploaded source "
    "document during onboarding. Edit the narrative here; manage the "
    "classifications and retention schedule through the typed-table editor.\n"
)


def _paths():
    config = load_working_copy_config()
    policies_dir = config.working_dir / "policies"
    staging = config.working_dir / ".policycodex-staging" / STEP_SLUG
    return policies_dir, staging


def _base_ctx(target, state):
    return {
        "step": target,
        "index": wizard.index_of(target.slug) + 1,
        "total": len(wizard.STEPS),
        "prev_step": wizard.prev_step(target.slug),
        "is_last": wizard.is_last(target.slug),
        "is_complete": state.is_complete(target.slug),
        "multipart": True,
    }


def _render_upload(request, target, state, form=None, error=None):
    ctx = _base_ctx(target, state)
    ctx["form"] = form or RetentionPolicyUploadForm()
    ctx["error"] = error
    return render(request, "onboarding/retention_policy_upload.html", ctx)


def _render_review(request, target, state, draft):
    ctx = _base_ctx(target, state)
    ctx["classifications"] = draft.get("classifications", [])
    ctx["retention_schedule"] = draft.get("retention_schedule", [])
    return render(request, "onboarding/retention_policy_review.html", ctx)


def _load_draft(staging: Path):
    draft_file = staging / "draft.yaml"
    if not draft_file.is_file():
        return None
    return yaml.safe_load(draft_file.read_text(encoding="utf-8"))


def handle(request, target, state):
    policies_dir, staging = _paths()

    if request.method == "GET":
        # Same ahead-jump gating as the generic view.
        furthest = state.furthest_step()
        if wizard.index_of(STEP_SLUG) > wizard.index_of(furthest):
            return redirect("onboarding_step", step=furthest)
        draft = _load_draft(staging)
        if draft is not None:
            return _render_review(request, target, state, draft)
        return _render_upload(request, target, state)

    action = request.POST.get("action")
    if action == "back":
        prev = wizard.prev_step(STEP_SLUG)
        return redirect("onboarding_step", step=prev.slug if prev else STEP_SLUG)
    if action == "save_exit":
        messages.info(request, "Your progress is saved. Resume onboarding any time.")
        return redirect("catalog")

    if action == "extract":
        form = RetentionPolicyUploadForm(request.POST, request.FILES)
        if not form.is_valid():
            return _render_upload(request, target, state, form=form)
        staging.mkdir(parents=True, exist_ok=True)
        source_pdf = staging / "source.pdf"
        with source_pdf.open("wb") as fh:
            for chunk in form.cleaned_data["pdf_file"].chunks():
                fh.write(chunk)
        try:
            text = extract_text(source_pdf)
            if not text.strip():
                if pdf_has_embedded_images(source_pdf):
                    guard_error = (
                        "This looks like a scanned PDF (an image with no text "
                        "layer), so there is nothing to extract automatically. "
                        "Upload a text-based PDF of the policy and try again."
                    )
                else:
                    guard_error = (
                        "We could not find any readable text in that document. "
                        "Check that it is a text-based PDF and try again."
                    )
                shutil.rmtree(staging, ignore_errors=True)
                return _render_upload(request, target, state, error=guard_error)
            bundle = extract_retention_bundle(ClaudeProvider(), text)
            data_yaml_text = build_data_yaml(bundle)
        except RetentionExtractionError as exc:
            return _render_upload(
                request, target, state,
                error=f"Could not read that document automatically: {exc}. "
                      "Try a different PDF.",
            )
        except Exception as exc:  # noqa: BLE001 - onboarding must not 500 on a
            # bad upload (corrupt/non-PDF bytes reaching the parser) or an AI
            # provider outage (missing key, network). Degrade to a friendly
            # re-prompt, mirroring core/views.py's "view must always render".
            logger.warning("APP-15 retention extraction failed: %s", exc)
            return _render_upload(
                request, target, state,
                error="We couldn't process that document. Check that it is a "
                      "valid PDF and try again. If the problem persists, the AI "
                      "service may be unavailable; contact your administrator.",
            )
        draft = {
            "title": DEFAULT_TITLE,
            "owner": DEFAULT_OWNER,
            "classifications": bundle.get("classifications", []),
            "retention_schedule": bundle.get("retention_schedule", []),
            "data_yaml": data_yaml_text,
        }
        (staging / "draft.yaml").write_text(
            yaml.safe_dump(draft, sort_keys=False, allow_unicode=True), encoding="utf-8"
        )
        return _render_review(request, target, state, draft)

    if action == "reupload":
        if staging.exists():
            shutil.rmtree(staging)
        return _render_upload(request, target, state)

    if action == "accept":
        draft = _load_draft(staging)
        if draft is None:
            return _render_upload(request, target, state)
        bundle_dir = scaffold_retention_bundle(
            policies_dir,
            title=draft["title"],
            owner=draft["owner"],
            narrative=_NARRATIVE_STUB,
            data_yaml_text=draft["data_yaml"],
            source_pdf=staging / "source.pdf" if (staging / "source.pdf").is_file() else None,
        )
        config = load_working_copy_config()
        author_name, author_email = get_git_author(request.user)
        config_yaml_text = build_config_yaml(state.all_data())
        try:
            pr = finalize_onboarding(
                working_dir=config.working_dir,
                config_yaml_text=config_yaml_text,
                bundle_dir=bundle_dir,
                provider=GitHubProvider(),
                author_name=author_name,
                author_email=author_email,
                base_branch=config.branch,
                username=request.user.get_username(),
            )
        except (RuntimeError, ValueError) as exc:
            logger.error("APP-16 onboarding finalize failed: %s", exc)
            messages.error(
                request,
                "Couldn't publish your configuration to the policy repository. "
                "Your choices are saved locally; ask your administrator to retry.",
            )
            return _render_review(request, target, state, draft)
        shutil.rmtree(staging.parent, ignore_errors=True)
        state.mark_complete(STEP_SLUG)
        messages.success(
            request,
            f"Onboarding complete. Configuration pull request opened: {pr.get('url', '')}",
        )
        return redirect("catalog")

    # Unknown action: re-render current state defensively.
    draft = _load_draft(staging)
    if draft is not None:
        return _render_review(request, target, state, draft)
    return _render_upload(request, target, state)


# --- APP-28c: HTMX fragment dispatch -------------------------------------
#
# The fragment path returns a #screen7-body partial swap for in-page actions
# and an HX-Redirect for navigation / a finished accept. It runs alongside
# handle() (the no-JS full-page fallback), which is left intact. The real
# business logic lives in the shared downstream services both paths call.


def _render_body(request, *, mode, form=None, error=None, classifications=None, retention_schedule=None):
    html = render_to_string("onboarding/_screen7_body.html", {
        "mode": mode,
        "form": form or RetentionPolicyUploadForm(),
        "error": error,
        "classifications": classifications or [],
        "retention_schedule": retention_schedule or [],
    }, request=request)
    return HttpResponse(html)


def _hx_redirect(url):
    resp = HttpResponse(status=204)
    resp["HX-Redirect"] = url
    return resp


def _do_extract(request, staging):
    form = RetentionPolicyUploadForm(request.POST, request.FILES)
    if not form.is_valid():
        return _render_body(request, mode="upload", form=form)
    staging.mkdir(parents=True, exist_ok=True)
    source_pdf = staging / "source.pdf"
    with source_pdf.open("wb") as fh:
        for chunk in form.cleaned_data["pdf_file"].chunks():
            fh.write(chunk)
    try:
        text = extract_text(source_pdf)
        if not text.strip():
            if pdf_has_embedded_images(source_pdf):
                guard_error = (
                    "This looks like a scanned PDF (an image with no text "
                    "layer), so there is nothing to extract automatically. "
                    "Upload a text-based PDF of the policy and try again."
                )
            else:
                guard_error = (
                    "We could not find any readable text in that document. "
                    "Check that it is a text-based PDF and try again."
                )
            shutil.rmtree(staging, ignore_errors=True)
            return _render_body(request, mode="upload", error=guard_error)
        bundle = extract_retention_bundle(ClaudeProvider(), text)
        data_yaml_text = build_data_yaml(bundle)
    except RetentionExtractionError as exc:
        return _render_body(
            request, mode="upload",
            error=f"Could not read that document automatically: {exc}. "
                  "Try a different PDF.",
        )
    except Exception as exc:  # noqa: BLE001 - onboarding must not 500 on a
        # bad upload (corrupt/non-PDF bytes reaching the parser) or an AI
        # provider outage (missing key, network). Degrade to a friendly
        # re-prompt, mirroring core/views.py's "view must always render".
        logger.warning("APP-15 retention extraction failed: %s", exc)
        return _render_body(
            request, mode="upload",
            error="We couldn't process that document. Check that it is a "
                  "valid PDF and try again. If the problem persists, the AI "
                  "service may be unavailable; contact your administrator.",
        )
    draft = {
        "title": DEFAULT_TITLE,
        "owner": DEFAULT_OWNER,
        "classifications": bundle.get("classifications", []),
        "retention_schedule": bundle.get("retention_schedule", []),
        "data_yaml": data_yaml_text,
    }
    (staging / "draft.yaml").write_text(
        yaml.safe_dump(draft, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    return _render_body(
        request, mode="review",
        classifications=draft["classifications"],
        retention_schedule=draft["retention_schedule"],
    )


def _do_accept(request, state, policies_dir, staging):
    draft = _load_draft(staging)
    if draft is None:
        return _render_body(request, mode="upload")
    bundle_dir = scaffold_retention_bundle(
        policies_dir,
        title=draft["title"],
        owner=draft["owner"],
        narrative=_NARRATIVE_STUB,
        data_yaml_text=draft["data_yaml"],
        source_pdf=staging / "source.pdf" if (staging / "source.pdf").is_file() else None,
    )
    config = load_working_copy_config()
    author_name, author_email = get_git_author(request.user)
    config_yaml_text = build_config_yaml(state.all_data())
    try:
        pr = finalize_onboarding(
            working_dir=config.working_dir,
            config_yaml_text=config_yaml_text,
            bundle_dir=bundle_dir,
            provider=GitHubProvider(),
            author_name=author_name,
            author_email=author_email,
            base_branch=config.branch,
            username=request.user.get_username(),
        )
    except (RuntimeError, ValueError) as exc:
        logger.error("APP-16 onboarding finalize failed: %s", exc)
        messages.error(
            request,
            "Couldn't publish your configuration to the policy repository. "
            "Your choices are saved locally; ask your administrator to retry.",
        )
        return _render_body(
            request, mode="review",
            classifications=draft.get("classifications", []),
            retention_schedule=draft.get("retention_schedule", []),
        )
    shutil.rmtree(staging.parent, ignore_errors=True)
    state.mark_complete(STEP_SLUG)
    messages.success(
        request,
        f"Onboarding complete. Configuration pull request opened: {pr.get('url', '')}",
    )
    return _hx_redirect(reverse("catalog"))


@login_required
@require_POST
def screen7_fragment(request):
    """HTMX endpoint (APP-28c): all screen-7 actions return a #screen7-body
    fragment swap, except navigation (back/save_exit) and a finished accept,
    which return an HX-Redirect so the browser performs a real page change."""
    state = WizardState(request.session)
    policies_dir, staging = _paths()
    action = request.POST.get("action")

    if action == "back":
        prev = wizard.prev_step(STEP_SLUG)
        target_slug = prev.slug if prev else STEP_SLUG
        return _hx_redirect(reverse("onboarding_step", kwargs={"step": target_slug}))
    if action == "save_exit":
        messages.info(request, "Your progress is saved. Resume onboarding any time.")
        return _hx_redirect(reverse("catalog"))
    if action == "extract":
        return _do_extract(request, staging)
    if action == "reupload":
        if staging.exists():
            shutil.rmtree(staging)
        return _render_body(request, mode="upload")
    if action == "accept":
        return _do_accept(request, state, policies_dir, staging)

    draft = _load_draft(staging)
    if draft is not None:
        return _render_body(request, mode="review",
                            classifications=draft.get("classifications", []),
                            retention_schedule=draft.get("retention_schedule", []))
    return _render_body(request, mode="upload")
