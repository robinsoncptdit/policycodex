import pytest
from pathlib import Path
from unittest.mock import patch


@pytest.mark.django_db
def test_finalize_opens_one_pr_with_drafts_only(tmp_path):
    from app.inventory.models import InventoryRun, InventoryItem
    from app.inventory.finalize import finalize_after_inventory

    wd = tmp_path / "wc"
    (wd / "policies").mkdir(parents=True)
    (wd / "policies" / "code-of-conduct.md").write_text("# Code\n")
    (wd / "policies" / "code-of-conduct.audit.yaml").write_text("confidence: 0.9\n")

    run = InventoryRun.objects.create(status="completed", total=1, completed=1)
    InventoryItem.objects.create(run=run, source_filename="code.pdf",
                                 slug="code-of-conduct", status="done")

    with patch("app.inventory.finalize.propose_change") as propose, \
         patch("app.inventory.finalize.GitHubProvider"):
        propose.return_value = {"url": "https://github.com/x/y/pull/42"}
        finalize_after_inventory(run, working_dir=wd)

    run.refresh_from_db()
    assert run.pr_url == "https://github.com/x/y/pull/42"
    propose.assert_called_once()
    kwargs = propose.call_args.kwargs
    # files is now a list[Path], not a dict; no config_yaml_text, no bundle_dir.
    assert "files" in kwargs
    assert "config_yaml_text" not in kwargs
    assert "bundle_dir" not in kwargs


@pytest.mark.django_db
def test_finalize_no_drafts_is_noop(tmp_path):
    from app.inventory.models import InventoryRun
    from app.inventory.finalize import finalize_after_inventory

    wd = tmp_path / "wc"
    (wd / "policies").mkdir(parents=True)

    run = InventoryRun.objects.create(status="completed", total=0, completed=0)
    with patch("app.inventory.finalize.propose_change") as propose:
        finalize_after_inventory(run, working_dir=wd)
    propose.assert_not_called()
