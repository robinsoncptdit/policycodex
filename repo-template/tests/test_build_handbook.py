"""Structural tests for the vendored handbook build (PUBLISH-06).

These assert the shape of repo-template/handbook/ and the build workflow.
They do not run Node; the Astro build smoke is a separate manual/CI step.
"""
from pathlib import Path

import yaml

REPO_TEMPLATE = Path(__file__).resolve().parents[1]
HANDBOOK = REPO_TEMPLATE / "handbook"
WORKFLOW = REPO_TEMPLATE / ".github" / "workflows" / "build-handbook.yml"
HANDBOOK_UPSTREAM = REPO_TEMPLATE.parent / "handbook"


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
    # staging copy, install, build, verify, artifact upload (build job)
    assert "cp -r policies/" in text
    assert "npm ci" in text
    assert "npm run build" in text
    assert "npm run verify" in text
    assert "actions/upload-pages-artifact" in text
    # PUBLISH-07: deploy job uses actions/deploy-pages
    assert "actions/deploy-pages@v5" in text


def test_workflow_grants_pages_artifact_permissions():
    wf = yaml.safe_load(WORKFLOW.read_text())
    perms = wf["permissions"]
    assert perms.get("pages") == "write"
    assert perms.get("id-token") == "write"


def test_workflow_serializes_builds_with_concurrency():
    wf = yaml.safe_load(WORKFLOW.read_text())
    concurrency = wf["concurrency"]
    assert concurrency["group"]
    # PUBLISH-07: Pages deploys should NOT be cancelled mid-flight; GitHub's
    # own guidance is cancel-in-progress: false for Pages, since cancelling
    # mid-deploy can corrupt the live site.
    assert concurrency["cancel-in-progress"] is False


def test_workflow_has_three_jobs_in_order():
    wf = yaml.safe_load(WORKFLOW.read_text())
    jobs = list(wf["jobs"].keys())
    assert jobs == ["preflight", "build", "deploy"], jobs


def test_preflight_job_queries_pages_api_and_declares_outputs():
    wf = yaml.safe_load(WORKFLOW.read_text())
    preflight = wf["jobs"]["preflight"]
    assert preflight["runs-on"] == "ubuntu-latest"
    assert preflight["permissions"] == {"contents": "read"}
    outputs = preflight["outputs"]
    assert "pages_configured" in outputs
    assert "site_url" in outputs
    # The check step must call the Pages API via gh.
    step_run = "\n".join(s.get("run", "") for s in preflight["steps"])
    assert "gh api" in step_run
    assert "repos/${{ github.repository }}/pages" in step_run


def test_build_job_needs_preflight_and_passes_site_url_env():
    wf = yaml.safe_load(WORKFLOW.read_text())
    build = wf["jobs"]["build"]
    assert build["needs"] == "preflight"
    # The "Build the handbook" step must receive ASTRO_SITE_URL from preflight.
    build_step = next(s for s in build["steps"] if s.get("name") == "Build the handbook")
    assert build_step["env"]["ASTRO_SITE_URL"] == "${{ needs.preflight.outputs.site_url }}"


def test_deploy_job_uses_deploy_pages_and_is_gated_on_preflight():
    wf = yaml.safe_load(WORKFLOW.read_text())
    deploy = wf["jobs"]["deploy"]
    # Must depend on both build (for artifact) and preflight (for the gate).
    assert deploy["needs"] == ["build", "preflight"]
    assert deploy["if"] == "needs.preflight.outputs.pages_configured == 'true'"
    env = deploy["environment"]
    assert env["name"] == "github-pages"
    assert env["url"] == "${{ steps.deployment.outputs.page_url }}"
    # Single deploy step pinned to v5.
    step = next(s for s in deploy["steps"] if s.get("uses", "").startswith("actions/deploy-pages"))
    assert step["uses"] == "actions/deploy-pages@v5"
    assert step["id"] == "deployment"


def test_upstream_and_vendored_astro_config_are_byte_equal():
    # sync-handbook.sh copies upstream handbook/astro.config.mjs over the
    # vendored copy. If they diverge, the next re-vendor silently reverts
    # the env-var reading change. Assert byte-equality to catch that.
    upstream = (HANDBOOK_UPSTREAM / "astro.config.mjs").read_bytes()
    vendored = (HANDBOOK / "astro.config.mjs").read_bytes()
    assert upstream == vendored


def test_vendored_astro_config_reads_site_url_env_var():
    text = (HANDBOOK / "astro.config.mjs").read_text()
    assert "process.env.ASTRO_SITE_URL" in text
    # Placeholder fallback for local builds without Pages.
    assert "'https://handbook.example.org'" in text
