"""Structural tests for the vendored handbook build (PUBLISH-06).

These assert the shape of repo-template/handbook/ and the build workflow.
They do not run Node; the Astro build smoke is a separate manual/CI step.
"""
from pathlib import Path

import yaml

REPO_TEMPLATE = Path(__file__).resolve().parents[1]
HANDBOOK = REPO_TEMPLATE / "handbook"
WORKFLOW = REPO_TEMPLATE / ".github" / "workflows" / "build-handbook.yml"


def test_vendored_handbook_has_core_files():
    for rel in (
        "package.json",
        "package-lock.json",
        "astro.config.mjs",
        "src/content.config.ts",
        "src/layouts/Base.astro",
        "scripts/verify-build.mjs",
    ):
        assert (HANDBOOK / rel).is_file(), f"vendored handbook missing {rel}"


def test_vendored_handbook_has_no_sample_content():
    policies = HANDBOOK / "src" / "content" / "policies"
    assert policies.is_dir(), "content/policies dir must exist (tracked via .gitkeep)"
    md_files = list(policies.rglob("*.md"))
    assert md_files == [], f"vendored handbook still ships sample content: {md_files}"
    assert (policies / ".gitkeep").is_file(), "content/policies must keep a .gitkeep"


def test_vendored_handbook_excludes_build_dirs():
    for junk in ("node_modules", "dist", ".astro"):
        assert not (HANDBOOK / junk).exists(), f"vendored handbook should not ship {junk}"


def test_workflow_exists_and_triggers_on_push_to_main():
    assert WORKFLOW.is_file(), "build-handbook.yml workflow missing"
    wf = yaml.safe_load(WORKFLOW.read_text())
    # PyYAML parses the bare `on:` key as boolean True.
    on = wf.get("on", wf.get(True))
    assert on["push"]["branches"] == ["main"]
    paths = on["push"]["paths"]
    assert "policies/**" in paths
    assert "handbook/**" in paths


def test_workflow_has_build_and_upload_steps():
    text = WORKFLOW.read_text()
    # staging copy, install, build, verify, artifact upload
    assert "cp -r policies/" in text
    assert "npm ci" in text
    assert "npm run build" in text
    assert "npm run verify" in text
    assert "actions/upload-pages-artifact" in text
    # build only - no deploy job in PUBLISH-06 (PUBLISH-07 owns serving)
    assert "actions/deploy-pages" not in text


def test_workflow_grants_pages_artifact_permissions():
    wf = yaml.safe_load(WORKFLOW.read_text())
    perms = wf["permissions"]
    assert perms.get("pages") == "write"
    assert perms.get("id-token") == "write"


def test_workflow_serializes_builds_with_concurrency():
    wf = yaml.safe_load(WORKFLOW.read_text())
    concurrency = wf["concurrency"]
    assert concurrency["group"]
    assert concurrency["cancel-in-progress"] is True
