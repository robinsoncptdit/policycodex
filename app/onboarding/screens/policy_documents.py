"""DISC-10: Screen 7 policy-documents -- multi-upload, validates, stages, kicks off inventory."""
from __future__ import annotations

import os
import uuid
from pathlib import Path

from django.shortcuts import redirect, render

from app.onboarding import wizard

STEP_SLUG = "policy-documents"
ALLOWED_EXT = {".pdf", ".docx", ".md", ".txt"}
MAX_FILE_BYTES = 25 * 1024 * 1024
MAX_TOTAL_BYTES = 500 * 1024 * 1024


def _staging_root() -> Path:
    raw = os.environ.get("POLICYCODEX_INGEST_STAGING_ROOT", "")
    return Path(raw) if raw else Path("/data/ingest-staging")


def _ctx(target, state, error=None):
    return {
        "step": target,
        "index": wizard.index_of(target.slug) + 1,
        "total": len(wizard.STEPS),
        "prev_step": wizard.prev_step(target.slug),
        "next_step": wizard.next_step(target.slug),
        "is_last": wizard.is_last(target.slug),
        "is_complete": state.is_complete(target.slug),
        "multipart": True,
        "error": error,
    }


def _validate(files):
    total = 0
    for f in files:
        ext = Path(f.name).suffix.lower()
        if ext not in ALLOWED_EXT:
            return f"Unsupported file type: {f.name}"
        if f.size > MAX_FILE_BYTES:
            return f"File too large: {f.name} (limit 25 MB)"
        total += f.size
    if total > MAX_TOTAL_BYTES:
        return "Total upload too large (limit 500 MB)."
    return None


def handle(request, target, state):
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "save_exit":
            return redirect("catalog")
        if action == "back":
            prev = wizard.prev_step(STEP_SLUG)
            return redirect("onboarding_step", step=prev.slug if prev else STEP_SLUG)
        if action == "continue":
            files = request.FILES.getlist("files")
            if not files:
                return render(
                    request,
                    "onboarding/policy_documents.html",
                    _ctx(target, state, error="Drop at least one document."),
                )
            err = _validate(files)
            if err:
                return render(
                    request,
                    "onboarding/policy_documents.html",
                    _ctx(target, state, error=err),
                )
            run_id = uuid.uuid4().hex[:12]
            stage_dir = _staging_root() / run_id
            stage_dir.mkdir(parents=True, exist_ok=True)
            for f in files:
                with (stage_dir / f.name).open("wb") as fh:
                    for chunk in f.chunks():
                        fh.write(chunk)
            state.set_data(STEP_SLUG, {"run_id": run_id, "stage_dir": str(stage_dir)})
            state.mark_complete(STEP_SLUG)
            return redirect("inventory")
    return render(request, "onboarding/policy_documents.html", _ctx(target, state))
