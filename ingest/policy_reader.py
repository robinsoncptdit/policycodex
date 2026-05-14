"""Bundle-aware policy reader for the diocese's policy repo."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Mapping

import yaml


class BundleError(ValueError):
    """A policies/<slug>/ entry could not be interpreted as a flat policy or a valid bundle."""


_FRONTMATTER_RE = re.compile(
    r"\A---\s*\n(?P<fm>.*?)\n---\s*\n(?P<body>.*)\Z",
    re.DOTALL,
)


@dataclass(frozen=True)
class LogicalPolicy:
    """One entry in the diocese's policy inventory."""

    slug: str
    kind: str                       # "flat" or "bundle"
    policy_path: Path               # path to the policy.md file
    data_path: Path | None          # path to data.yaml for bundles, None for flat
    frontmatter: Mapping[str, object]
    body: str
    foundational: bool
    provides: tuple[str, ...]


def _split_frontmatter(text: str) -> tuple[Mapping[str, object], str]:
    """Return (frontmatter dict, body). Empty frontmatter -> {}. Missing -> ({}, full text)."""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    fm_raw = m.group("fm")
    fm = yaml.safe_load(fm_raw) or {}
    if not isinstance(fm, Mapping):
        raise BundleError(f"frontmatter is not a YAML mapping: {fm_raw!r}")
    return fm, m.group("body")


class BundleAwarePolicyReader:
    """Walks the top level of a policies/ directory and yields LogicalPolicy entries."""

    def __init__(self, policies_root: Path) -> None:
        self.policies_root = Path(policies_root)

    def read(self) -> Iterator[LogicalPolicy]:
        if not self.policies_root.exists():
            raise FileNotFoundError(f"policies root not found: {self.policies_root}")
        if not self.policies_root.is_dir():
            raise NotADirectoryError(f"policies root is not a directory: {self.policies_root}")

        for entry in sorted(self.policies_root.iterdir()):
            if entry.name.startswith("."):
                continue
            if entry.is_file() and entry.suffix == ".md":
                yield self._read_flat(entry)
            elif entry.is_dir():
                yield self._read_bundle(entry)

    def _read_bundle(self, bundle_dir: Path) -> LogicalPolicy:
        policy_md = bundle_dir / "policy.md"
        data_yaml = bundle_dir / "data.yaml"
        if not policy_md.is_file():
            raise BundleError(f"bundle missing policy.md: {bundle_dir}")
        if not data_yaml.is_file():
            raise BundleError(f"bundle missing data.yaml: {bundle_dir}")

        text = policy_md.read_text(encoding="utf-8")
        fm, body = _split_frontmatter(text)
        if not fm.get("foundational"):
            raise BundleError(
                f"bundle policy.md missing 'foundational: true' frontmatter: {policy_md}"
            )
        provides = fm.get("provides")
        if not isinstance(provides, list) or not provides:
            raise BundleError(
                f"bundle policy.md missing non-empty 'provides:' list: {policy_md}"
            )

        # Validate data.yaml parses; do NOT cache the payload here (callers fetch on demand).
        data_text = data_yaml.read_text(encoding="utf-8")
        try:
            parsed = yaml.safe_load(data_text)
        except yaml.YAMLError as exc:
            raise BundleError(f"bundle data.yaml is not valid YAML: {data_yaml}: {exc}") from exc
        if parsed is not None and not isinstance(parsed, Mapping):
            raise BundleError(f"bundle data.yaml must be a YAML mapping at top level: {data_yaml}")

        return LogicalPolicy(
            slug=bundle_dir.name,
            kind="bundle",
            policy_path=policy_md,
            data_path=data_yaml,
            frontmatter=fm,
            body=body,
            foundational=True,
            provides=tuple(provides),
        )

    def _read_flat(self, path: Path) -> LogicalPolicy:
        text = path.read_text(encoding="utf-8")
        fm, body = _split_frontmatter(text)
        return LogicalPolicy(
            slug=path.stem,
            kind="flat",
            policy_path=path,
            data_path=None,
            frontmatter=fm,
            body=body,
            foundational=bool(fm.get("foundational", False)),
            provides=tuple(fm.get("provides", ()) or ()),
        )
