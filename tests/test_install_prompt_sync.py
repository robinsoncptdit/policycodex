"""Guards that INSTALL-WITH-CLAUDE.md and README.md stay in lockstep with the
live Docker install path.

Plain file-scanning tests (no Django context), mirroring tests/test_docker_packaging.py
and tests/test_python_pin.py. The Claude-Code prompt walks a non-technical admin
through the real install, so it names real files, env keys, install commands, and
URL routes; the README install section walks a developer-IT-director through the
same path. If any of those move and the docs are not updated in the same change,
one of these tripwires goes red.

These cannot verify the prose is *accurate* (a human still reviews that). They
verify the docs have not been left pointing at files/keys/commands/routes that
no longer exist, which is the failure mode the CLAUDE.md mandate exists to
prevent.
"""
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_PROMPT_NAME = "INSTALL-WITH-CLAUDE.md"


def _read(name: str) -> str:
    return (_ROOT / name).read_text(encoding="utf-8")


def _prompt() -> str:
    return _read(_PROMPT_NAME)


# Files the prompt tells the admin to clone, copy, run, or read. Each must
# still exist on disk; a rename without updating the prompt fails here.
_REFERENCED_FILES = (
    "install.sh",
    ".env.example",
    "config.env.example",
    "docker-compose.yml",
    "docker/entrypoint.sh",
    "docker/load-secrets.sh",
    "Dockerfile",
    "README.md",
    "HOWTO-GitHub-Team-Setup.md",
    "app/git_provider/github_config.py",
    "core/management/commands/run_inventory_pass.py",
)

# Required GitHub App keys from app/git_provider/github_config.py. The
# config.env.example template must enumerate all of them: any added there
# without updating the template would mean a real install hits a
# load_github_config() FileNotFoundError/ValueError instead of just an
# unfilled value -- the template is meant to remove that footgun.
_REQUIRED_GH_KEYS = (
    "POLICYCODEX_GH_APP_ID",
    "POLICYCODEX_GH_INSTALLATION_ID",
    "POLICYCODEX_GH_PRIVATE_KEY_PATH",
)

# LLM provider env names the prompt names by convention. Each must appear
# in the template (active or commented) so an admin who picks a non-default
# provider in wizard step 6 doesn't have to know which env var the SDK reads.
_LLM_PROVIDER_KEYS = (
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "GOOGLE_API_KEY",
    "AZURE_OPENAI_API_KEY",
)

# Install-critical env keys. Each must appear in BOTH .env.example AND the
# prompt: drop/rename in .env.example -> the env-side assert fails; drop the
# guidance from the prompt -> the prompt-side assert fails.
_ENV_KEYS = (
    "DJANGO_SECRET_KEY",
    "DJANGO_ALLOWED_HOSTS",
    "POLICYCODEX_DB_PATH",
    "POLICYCODEX_CONFIG_PATH",
    "DJANGO_SUPERUSER_USERNAME",
)

# URL fragments the login-first flow depends on, paired with the URLconf file
# that must still define them. If a route moves, the prompt would send the
# admin to a dead URL; this keeps the two honest together.
_ROUTE_TOKENS = (
    ("/health/", "core/urls.py", "health/"),
    ("/catalog/", "core/urls.py", "catalog/"),
    ("/onboarding/", "policycodex_site/urls.py", "onboarding/"),
    ("/login/", "policycodex_site/urls.py", "login/"),
)


def test_prompt_exists_and_is_substantial():
    text = _prompt()
    assert len(text) > 2000, "install prompt is suspiciously short"


def test_prompt_references_only_existing_files():
    text = _prompt()
    for name in _REFERENCED_FILES:
        assert (_ROOT / name).is_file(), f"prompt references missing file: {name}"
        assert name in text, f"prompt no longer mentions tracked file: {name}"


def test_env_keys_present_in_both_example_and_prompt():
    env_example = _read(".env.example")
    text = _prompt()
    for key in _ENV_KEYS:
        assert key in env_example, f"{key} missing from .env.example"
        assert key in text, f"prompt no longer documents env key: {key}"


def test_install_command_matches_install_script():
    # The prompt promises ./install.sh runs `docker compose up --build`.
    assert "docker compose up --build" in _read("install.sh")
    assert "install.sh" in _prompt()
    assert "docker compose up --build" in _prompt()


def test_login_first_routes_still_exist():
    text = _prompt()
    for url_fragment, urlconf, route in _ROUTE_TOKENS:
        assert url_fragment in text, f"prompt dropped the {url_fragment} step"
        assert route in _read(urlconf), (
            f"{route} no longer defined in {urlconf}; prompt {url_fragment} is stale"
        )


def test_maintainer_discipline_survives():
    # The "update me when the Docker path moves" contract must stay in the file
    # AND in the auto-loaded standing context (CLAUDE.md), or the lockstep rots.
    assert "For maintainers" in _prompt()
    assert _PROMPT_NAME in _read("CLAUDE.md")


def test_load_secrets_helper_not_sourced_by_entrypoint():
    # DISC-01: the entrypoint no longer sources load-secrets.sh (that
    # helper and the /secrets bind-mount model is replaced by the
    # /data-volume key-file model). DISC-15 will delete the file itself.
    text = _read("docker/entrypoint.sh")
    assert ". /usr/local/bin/load-secrets.sh" not in text, (
        "entrypoint still sources the legacy load-secrets.sh; DISC-01 removed it"
    )


# REPO-19: the README install walkthrough must walk through login + admin
# creation, not just the wizard. `/onboarding/`, `/catalog/`, and `/` are
# all login_required, so a first-run admin who follows the README straight
# from boot to the wizard URL is bounced to /login/ with no documented
# credentials step. Mirrors `_ROUTE_TOKENS` for INSTALL-WITH-CLAUDE.md.
_README_LOGIN_TOKENS = (
    "/login/",
    "createsuperuser",
)


def test_config_env_example_covers_required_github_keys():
    template = _read("config.env.example")
    github_config = _read("app/git_provider/github_config.py")
    for key in _REQUIRED_GH_KEYS:
        assert key in github_config, (
            f"{key} no longer required by github_config.py; "
            "either restore it or drop it from _REQUIRED_GH_KEYS"
        )
        assert key in template, (
            f"config.env.example missing {key}; the template must enumerate "
            "every key github_config.load_github_config requires"
        )


def test_config_env_example_covers_all_llm_provider_keys():
    template = _read("config.env.example")
    prompt = _prompt()
    for key in _LLM_PROVIDER_KEYS:
        assert key in template, f"config.env.example missing {key}"
        assert key in prompt, f"prompt no longer names {key}; sync regression"


def test_prompt_uses_config_env_example_in_phase_5():
    # Phase 5 must tell the admin to `cp config.env.example` rather than
    # punting on what keys belong in config.env. A rename of the template
    # without updating the prompt trips here.
    text = _prompt()
    assert "config.env.example" in text, (
        "prompt no longer references config.env.example; admins are back to "
        "reading Python source to figure out which keys belong in config.env"
    )


def test_readme_install_walkthrough_documents_login_step():
    readme = _read("README.md")
    quick_start = readme.find("## Quick Start")
    roadmap = readme.find("## Roadmap")
    assert quick_start != -1, "Quick Start heading missing from README"
    assert roadmap != -1 and roadmap > quick_start, (
        "Roadmap heading missing or precedes Quick Start in README"
    )
    install_section = readme[quick_start:roadmap]
    for token in _README_LOGIN_TOKENS:
        assert token in install_section, (
            f"README install walkthrough no longer documents {token!r}; "
            "REPO-19 sync regression"
        )
