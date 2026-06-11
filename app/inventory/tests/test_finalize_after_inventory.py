"""DISC-14: finalize_after_inventory opens ONE PR with config + retention bundle + drafts."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.mark.django_db
def test_finalize_opens_one_pr_with_everything(tmp_path):
    from app.inventory.models import InventoryRun, InventoryItem
    from app.inventory.finalize import finalize_after_inventory

    wd = tmp_path / "wc"
    (wd / ".policycodex").mkdir(parents=True)
    (wd / "policies" / "document-retention").mkdir(parents=True)
    (wd / "policies" / "document-retention" / "policy.md").write_text("# Retention\n")
    (wd / "policies" / "code-of-conduct.md").write_text("# Code\n")
    (wd / "policies" / "code-of-conduct.audit.yaml").write_text("confidence: 0.9\n")

    run = InventoryRun.objects.create(status="completed", total=1, completed=1)
    InventoryItem.objects.create(
        run=run, source_filename="code.pdf", slug="code-of-conduct", status="done"
    )

    with patch("app.inventory.finalize.finalize_onboarding") as fin, \
         patch("app.inventory.finalize.GitHubProvider"), \
         patch("app.inventory.finalize.load_working_copy_config"):
        fin.return_value = {"url": "https://github.com/x/y/pull/42"}
        finalize_after_inventory(
            run,
            working_dir=wd,
            config_yaml_text="schema_version: 1\n",
            bundle_dir=wd / "policies" / "document-retention",
        )

    args, kwargs = fin.call_args
    assert kwargs["bundle_dir"] == wd / "policies" / "document-retention"
    assert "drafts_dir" in kwargs
    assert kwargs["drafts_dir"] == wd / "policies"
    assert kwargs["config_yaml_text"] == "schema_version: 1\n"
    run.refresh_from_db()
    assert run.pr_url == "https://github.com/x/y/pull/42"


@pytest.mark.django_db
def test_finalize_records_pr_error_on_failure(tmp_path):
    from app.inventory.models import InventoryRun
    from app.inventory.finalize import finalize_after_inventory

    wd = tmp_path / "wc"
    (wd / "policies" / "document-retention").mkdir(parents=True)
    (wd / "policies" / "document-retention" / "policy.md").write_text("# Retention\n")

    run = InventoryRun.objects.create(status="completed", total=0, completed=0)
    with patch("app.inventory.finalize.finalize_onboarding", side_effect=RuntimeError("git push 401")), \
         patch("app.inventory.finalize.GitHubProvider"), \
         patch("app.inventory.finalize.load_working_copy_config"):
        with pytest.raises(RuntimeError):
            finalize_after_inventory(
                run,
                working_dir=wd,
                config_yaml_text="schema_version: 1\n",
                bundle_dir=wd / "policies" / "document-retention",
            )
    run.refresh_from_db()
    # finalize_after_inventory raises; status_fragment catches and records pr_error.
    # The run.pr_url stays empty since the call failed before saving.
    assert not run.pr_url


@pytest.mark.django_db
def test_finalize_drafts_dir_passed_as_policies_subdir(tmp_path):
    """drafts_dir is always working_dir/policies regardless of what's in it."""
    from app.inventory.models import InventoryRun
    from app.inventory.finalize import finalize_after_inventory

    wd = tmp_path / "wc"
    (wd / "policies").mkdir(parents=True)

    run = InventoryRun.objects.create(status="completed", total=0, completed=0)
    with patch("app.inventory.finalize.finalize_onboarding") as fin, \
         patch("app.inventory.finalize.GitHubProvider"), \
         patch("app.inventory.finalize.load_working_copy_config"):
        fin.return_value = {"url": "https://github.com/x/y/pull/99"}
        finalize_after_inventory(
            run,
            working_dir=wd,
            config_yaml_text="schema_version: 1\n",
            bundle_dir=wd / "policies" / "document-retention",
        )

    kwargs = fin.call_args.kwargs
    assert kwargs["drafts_dir"] == wd / "policies"
