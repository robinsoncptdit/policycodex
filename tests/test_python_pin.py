"""Guards that the Python version pin (REPO-11) stays consistent across the repo.

Plain file-scanning tests (no Django context), mirroring tests/test_docker_packaging.py.
The .python-version file and the Dockerfile base image must agree on the target
minor version, and the Django floor must justify the >=3.12 Python floor.
"""
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


def _read(name: str) -> str:
    return (_ROOT / name).read_text(encoding="utf-8")


def test_python_version_file_declares_supported_minor():
    raw = _read(".python-version").strip()
    assert re.fullmatch(r"3\.\d+(\.\d+)?", raw), f"unexpected .python-version: {raw!r}"
    major, minor = (int(part) for part in raw.split(".")[:2])
    assert (major, minor) >= (3, 12), "floor is 3.12 (set by Django 6.0)"


def test_dockerfile_base_matches_python_version():
    pin = _read(".python-version").strip()
    pin_minor = ".".join(pin.split(".")[:2])
    match = re.search(r"FROM python:(\d+\.\d+)", _read("Dockerfile"))
    assert match, "Dockerfile has no pinned python base image"
    assert match.group(1) == pin_minor, (
        f"Dockerfile base {match.group(1)} != .python-version {pin_minor}"
    )


def test_django_floor_justifies_python_floor():
    # Django 6.0 is what sets the >=3.12 floor; the requirement must pin >=6.0
    # so the Python floor is actually justified by the declared Django floor.
    match = re.search(
        r"^django>=(\d+)\.(\d+)", _read("app/requirements.txt"),
        re.IGNORECASE | re.MULTILINE,
    )
    assert match, "app/requirements.txt does not pin a django floor"
    assert (int(match.group(1)), int(match.group(2))) >= (6, 0), (
        "django floor must be >=6.0 to justify the >=3.12 Python floor"
    )
