"""F1 regression: the /inventory/ views must forward every required
run_inventory_pass keyword to start_run. test_runner.py fully mocks
run_inventory_pass, so the real keyword-only signature is exercised only here
at the view -> start_run boundary."""
from __future__ import annotations

import inspect
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile

from ai.inventory import run_inventory_pass

User = get_user_model()


def _required_kwonly(func) -> set[str]:
    return {
        name
        for name, p in inspect.signature(func).parameters.items()
        if p.kind is inspect.Parameter.KEYWORD_ONLY and p.default is inspect.Parameter.empty
    }


@pytest.fixture
def editor(db):
    u = User.objects.create_user("ed", password="x")
    u.profile.must_change_password = False
    u.profile.save()
    u.groups.add(Group.objects.get(name="Editor"))
    return u


@pytest.mark.django_db
def test_upload_forwards_required_orchestrator_kwargs(client, editor, tmp_path):
    client.force_login(editor)
    captured: dict = {}

    def fake_start_run(run, stage_dir, working_dir, **pass_kwargs):
        captured["pass_kwargs"] = pass_kwargs
        return None

    fake_config = SimpleNamespace(working_dir=tmp_path, branch="main")
    upload = SimpleUploadedFile("policy.pdf", b"%PDF-1.4 fake", content_type="application/pdf")

    with (
        patch("app.inventory.views.start_run", side_effect=fake_start_run),
        patch("app.inventory.views._staging_root", return_value=tmp_path / "stage"),
        patch("app.inventory.views.load_working_copy_config", return_value=fake_config),
        patch("app.inventory.views.load_foundational_taxonomy",
              return_value={"classifications": []}, create=True),
        patch("app.inventory.views.GitHubProvider", return_value=object(), create=True),
        patch("app.inventory.views.ClaudeProvider", return_value=object(), create=True),
    ):
        response = client.post("/inventory/upload/", {"files": [upload]})

    assert response.status_code in (302, 200)
    assert "pass_kwargs" in captured, "inventory_upload never called start_run"
    forwarded = set(captured["pass_kwargs"])
    # The runner supplies manifest + working_dir; the view must supply every
    # OTHER required keyword-only arg of run_inventory_pass.
    required = _required_kwonly(run_inventory_pass) - {"manifest", "working_dir"}
    missing = required - forwarded
    assert not missing, f"inventory_upload omitted required orchestrator kwargs: {missing}"
