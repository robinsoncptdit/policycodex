"""Per-policy .policymeta.yaml sidecar reader.

The sidecar stores app-managed metadata that does NOT belong in the
policy's frontmatter (because it would clutter the published markdown).
Today it carries `pr_number`; future fields may include the head-branch
name or the last-known PR state.

Flat policies: `<working_dir>/policies/<slug>.policymeta.yaml`
Bundle policies: `<working_dir>/policies/<slug>/.policymeta.yaml`
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml


class PolicymetaError(RuntimeError):
    """Raised when a .policymeta.yaml file is present but malformed."""


def _candidate_paths(working_dir: Path, slug: str) -> list[Path]:
    policies_dir = working_dir / "policies"
    return [
        policies_dir / f"{slug}.policymeta.yaml",       # flat
        policies_dir / slug / ".policymeta.yaml",       # bundle
    ]


def read_pr_number_for(working_dir: Path, slug: str) -> Optional[int]:
    """Return the PR number tracked for `slug`, or None if no sidecar exists.

    Raises:
        PolicymetaError: If a sidecar exists but is not valid YAML, or if it
            is valid YAML but missing the required `pr_number` field.
    """
    for candidate in _candidate_paths(working_dir, slug):
        if not candidate.exists():
            continue
        try:
            data = yaml.safe_load(candidate.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise PolicymetaError(
                f"policymeta sidecar is not valid YAML: {candidate}: {exc}"
            ) from exc
        if not isinstance(data, dict) or "pr_number" not in data:
            raise PolicymetaError(
                f"policymeta sidecar at {candidate} is missing required field "
                f"`pr_number`"
            )
        try:
            return int(data["pr_number"])
        except (TypeError, ValueError) as exc:
            raise PolicymetaError(
                f"policymeta `pr_number` at {candidate} is not an integer: "
                f"{data['pr_number']!r}"
            ) from exc
    return None
