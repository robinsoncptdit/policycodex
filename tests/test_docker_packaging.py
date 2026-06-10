"""Structural guards for the REPO-05 Docker packaging (no docker daemon needed)."""
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


def _read(name: str) -> str:
    return (_ROOT / name).read_text(encoding="utf-8")


def test_packaging_files_exist():
    for name in (
        "Dockerfile",
        "docker-compose.yml",
        "docker-compose.pull.yml",
        ".env.example",
        "install.sh",
        "docker/entrypoint.sh",
        ".dockerignore",
    ):
        assert (_ROOT / name).is_file(), f"missing {name}"


def test_dockerfile_installs_git_and_runs_gunicorn():
    text = _read("Dockerfile")
    assert "install" in text and "git" in text  # app shells out to git
    assert "collectstatic" in text


def test_entrypoint_migrates_and_execs_gunicorn():
    text = _read("docker/entrypoint.sh")
    assert "migrate" in text
    assert "gunicorn" in text


def test_build_compose_builds_and_mounts_secrets_readonly():
    text = _read("docker-compose.yml")
    assert "build:" in text
    assert "/secrets:ro" in text
    assert "policycodex-data:/data" in text


def test_pull_compose_references_registry_image():
    text = _read("docker-compose.pull.yml")
    assert "image:" in text
    assert "ghcr.io/" in text
    assert "build:" not in text  # Profile B pulls, does not build


def test_dockerignore_excludes_env_files():
    # install.sh seeds a populated .env BEFORE `compose up --build`; without
    # this exclusion the diocese's SECRET_KEY bakes into the image layers.
    lines = [line.strip() for line in _read(".dockerignore").splitlines()]
    assert ".env" in lines, ".env must be excluded from the Docker build context"
    assert ".env.*" in lines, ".env.* must be excluded from the Docker build context"


def test_env_example_documents_required_keys():
    text = _read(".env.example")
    for key in (
        "DJANGO_SECRET_KEY",
        "DJANGO_ALLOWED_HOSTS",
        "POLICYCODEX_DB_PATH",
        "POLICYCODEX_CONFIG_PATH",
        "POLICYCODEX_SOURCE_URL",
    ):
        assert key in text, f"{key} not documented in .env.example"


def test_env_example_holds_no_real_secret_values():
    # Keys are present but must ship empty (no leaked credential).
    for line in _read(".env.example").splitlines():
        if line.startswith("DJANGO_SECRET_KEY="):
            assert line.strip() == "DJANGO_SECRET_KEY="


def test_dockerfile_does_not_copy_load_secrets_helper():
    # DISC-01: load-secrets.sh is no longer sourced by the entrypoint; its
    # COPY + chmod lines were removed from the Dockerfile. DISC-15 will
    # delete the file itself. The Dockerfile must not re-add those lines.
    text = _read("Dockerfile")
    assert "COPY docker/load-secrets.sh" not in text
    assert "chmod +x /usr/local/bin/load-secrets.sh" not in text
