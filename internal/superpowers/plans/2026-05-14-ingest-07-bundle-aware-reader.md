# INGEST-07 Bundle-Aware Policy Reader Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A `BundleAwarePolicyReader` that scans a `policies/` root and yields one `LogicalPolicy` per inventory entry, collapsing `policies/<slug>/{policy.md, data.yaml}` bundles into a single record while leaving flat `policies/<slug>.md` files one-to-one. Fail loud on malformed bundles.

**Architecture:** New module `ingest/policy_reader.py` separate from `LocalFolderConnector`. Rationale: `LocalFolderConnector.walk()` is a primitive that yields every regular file recursively, exactly what the bundle reader has to NOT do (it must stop at bundle directory boundaries and treat them atomically). The reader uses `Path.iterdir()` directly on the `policies/` root and decides per top-level entry: flat `.md` file → flat `LogicalPolicy`; directory containing `policy.md` with `foundational: true` frontmatter and `data.yaml` → bundle `LogicalPolicy`; anything else → error. Frontmatter parsing is stdlib (split on `---\n` markers, `yaml.safe_load` the inner block). Data class is `@dataclass(frozen=True)`.

**Tech Stack:** Python 3.12 stdlib + `PyYAML>=6.0` (already in `ingest/requirements.txt`). No new runtime deps. pytest with `tmp_path` fixtures.

**Ticket reference:** `PolicyWonk-v0.1-Tickets.md` INGEST-07 (line 53). Foundational-policy bundle design: `internal/PolicyWonk-Foundational-Policy-Design.md`. Live example: `Diocese-of-Pensacola-Tallahassee/pt-policy@34a1671` `policies/document-retention/`.

**BASE:** `main` at SHA `d9da925`.

---

## Why a new module, not extending the connector

- `LocalFolderConnector.walk()` yields ALL regular files recursively, descending every directory. INGEST-07 needs the opposite stance at `policies/<slug>/` boundaries: treat the directory atomically, do NOT descend, return one record for the whole thing.
- INGEST-03 callers (extractors) and any future AI extraction path still need the file-by-file primitive. Modifying `walk()` to skip bundle dirs would break those callers; adding a new method to the connector still couples two distinct concepts in one class.
- `BundleAwarePolicyReader` is a higher-level concept: it knows the `policies/` convention; `LocalFolderConnector` does not. Keeping them separate matches the existing layering (connector primitive + extractor decorator + reader composer).

---

## File Structure

- Create: `ingest/policy_reader.py` — `BundleAwarePolicyReader`, `LogicalPolicy` dataclass, `BundleError` exception, `_split_frontmatter`, `_read_bundle`, `_read_flat` helpers.
- Create: `ingest/tests/test_policy_reader.py` — synthetic fixtures via `tmp_path`, diocese-agnostic.

No changes to existing `ingest/local_folder.py`, `ingest/extractors/`, or anywhere else.

---

## Task 1: Module scaffold + `LogicalPolicy` dataclass + happy-path flat-file test (TDD)

**Files:**
- Create: `ingest/policy_reader.py`
- Create: `ingest/tests/test_policy_reader.py`

- [ ] **Step 1: Write the failing test**

Create `ingest/tests/test_policy_reader.py`:

```python
"""Tests for BundleAwarePolicyReader."""
from pathlib import Path

import pytest

from ingest.policy_reader import (
    BundleAwarePolicyReader,
    BundleError,
    LogicalPolicy,
)


def _make_flat(policies_root: Path, slug: str, body: str = "# Body\n") -> Path:
    """Create a flat policies/<slug>.md file with minimal frontmatter."""
    p = policies_root / f"{slug}.md"
    p.write_text(
        f"---\ntitle: {slug.title()}\nowner: HR\n---\n{body}",
        encoding="utf-8",
    )
    return p


def test_flat_policy_yields_single_logical_policy(tmp_path):
    policies = tmp_path / "policies"
    policies.mkdir()
    _make_flat(policies, "onboarding")

    reader = BundleAwarePolicyReader(policies)
    results = list(reader.read())

    assert len(results) == 1
    p = results[0]
    assert isinstance(p, LogicalPolicy)
    assert p.slug == "onboarding"
    assert p.kind == "flat"
    assert p.policy_path == policies / "onboarding.md"
    assert p.data_path is None
    assert p.frontmatter["title"] == "Onboarding"
    assert p.foundational is False
    assert p.provides == ()
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd /Users/chuck/PolicyWonk && python -m pytest ingest/tests/test_policy_reader.py -v
```

Expected: ImportError (the module doesn't exist).

- [ ] **Step 3: Create minimal `policy_reader.py`**

Create `ingest/policy_reader.py`:

```python
"""Bundle-aware policy reader for the diocese's policy repo."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
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
```

- [ ] **Step 4: Run to confirm pass**

```bash
python -m pytest ingest/tests/test_policy_reader.py::test_flat_policy_yields_single_logical_policy -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ingest/policy_reader.py ingest/tests/test_policy_reader.py
git commit -m "feat(INGEST-07): BundleAwarePolicyReader + LogicalPolicy scaffold + flat read"
```

---

## Task 2: Bundle directory recognition (foundational happy path)

**Files:**
- Modify: `ingest/policy_reader.py`
- Modify: `ingest/tests/test_policy_reader.py`

- [ ] **Step 1: Write the failing tests**

Append to `ingest/tests/test_policy_reader.py`:

```python
def _make_bundle(
    policies_root: Path,
    slug: str,
    *,
    provides: list[str] | None = None,
    extra_frontmatter: dict | None = None,
    data_payload: dict | None = None,
) -> Path:
    """Create policies/<slug>/{policy.md, data.yaml} for a foundational bundle."""
    bundle = policies_root / slug
    bundle.mkdir()
    fm = {
        "title": slug.replace("-", " ").title(),
        "owner": "CFO",
        "foundational": True,
        "provides": provides or ["classifications"],
    }
    if extra_frontmatter:
        fm.update(extra_frontmatter)
    import yaml as _yaml
    fm_text = _yaml.safe_dump(fm, sort_keys=False).strip()
    (bundle / "policy.md").write_text(
        f"---\n{fm_text}\n---\n# {slug}\n", encoding="utf-8"
    )
    data = data_payload if data_payload is not None else {"classifications": [{"id": "x", "name": "X"}]}
    (bundle / "data.yaml").write_text(_yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return bundle


def test_bundle_yields_single_logical_policy(tmp_path):
    policies = tmp_path / "policies"
    policies.mkdir()
    _make_bundle(policies, "retention", provides=["classifications", "retention-schedule"])

    reader = BundleAwarePolicyReader(policies)
    results = list(reader.read())

    assert len(results) == 1
    p = results[0]
    assert p.slug == "retention"
    assert p.kind == "bundle"
    assert p.policy_path == policies / "retention" / "policy.md"
    assert p.data_path == policies / "retention" / "data.yaml"
    assert p.foundational is True
    assert p.provides == ("classifications", "retention-schedule")
```

- [ ] **Step 2: Run to confirm failure**

```bash
python -m pytest ingest/tests/test_policy_reader.py::test_bundle_yields_single_logical_policy -v
```

Expected: FAIL (iterdir hits the dir, the current `read()` only handles file `.md` entries; assertion fails because results is empty).

- [ ] **Step 3: Add bundle handling**

In `ingest/policy_reader.py`, extend `read()` to also handle directories. Add a `_read_bundle` helper. Replace the body of `read()`:

```python
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
```

Add `_read_bundle`:

```python
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

        # Validate data.yaml parses; do NOT cache the payload yet (callers fetch on demand).
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
```

- [ ] **Step 4: Run to confirm pass**

```bash
python -m pytest ingest/tests/test_policy_reader.py -v
```

Expected: both tests PASS.

- [ ] **Step 5: Commit**

```bash
git add ingest/policy_reader.py ingest/tests/test_policy_reader.py
git commit -m "feat(INGEST-07): bundle directory recognition (foundational + provides)"
```

---

## Task 3: Mixed structure + sort order

**Files:**
- Modify: `ingest/tests/test_policy_reader.py`

- [ ] **Step 1: Add the test**

Append:

```python
def test_mixed_structure_yields_alpha_sorted_entries(tmp_path):
    policies = tmp_path / "policies"
    policies.mkdir()
    # Intentionally not in alpha order:
    _make_flat(policies, "onboarding")
    _make_bundle(policies, "retention", provides=["classifications"])
    _make_flat(policies, "code-of-conduct")
    _make_bundle(policies, "appendix-a", provides=["retention-schedule"])

    reader = BundleAwarePolicyReader(policies)
    results = list(reader.read())

    slugs = [p.slug for p in results]
    assert slugs == ["appendix-a", "code-of-conduct", "onboarding", "retention"]
    kinds = {p.slug: p.kind for p in results}
    assert kinds == {
        "appendix-a": "bundle",
        "code-of-conduct": "flat",
        "onboarding": "flat",
        "retention": "bundle",
    }
```

- [ ] **Step 2: Run**

```bash
python -m pytest ingest/tests/test_policy_reader.py::test_mixed_structure_yields_alpha_sorted_entries -v
```

Expected: PASS (sort came in Task 2's `sorted(iterdir())`).

- [ ] **Step 3: Commit**

```bash
git add ingest/tests/test_policy_reader.py
git commit -m "test(INGEST-07): mixed flat/bundle entries return alpha-sorted"
```

---

## Task 4: Hidden entries and ignored top-level files

**Files:**
- Modify: `ingest/tests/test_policy_reader.py`

- [ ] **Step 1: Add the tests**

```python
def test_hidden_entries_skipped(tmp_path):
    policies = tmp_path / "policies"
    policies.mkdir()
    _make_flat(policies, "real")
    (policies / ".hidden.md").write_text("---\n---\nx", encoding="utf-8")
    hidden_dir = policies / ".dotdir"
    hidden_dir.mkdir()
    (hidden_dir / "policy.md").write_text("---\nfoundational: true\nprovides: [x]\n---\n", encoding="utf-8")

    reader = BundleAwarePolicyReader(policies)
    assert [p.slug for p in reader.read()] == ["real"]


def test_non_md_top_level_files_skipped(tmp_path):
    policies = tmp_path / "policies"
    policies.mkdir()
    _make_flat(policies, "real")
    (policies / "README.txt").write_text("ignore me", encoding="utf-8")
    (policies / "schema.json").write_text("{}", encoding="utf-8")

    reader = BundleAwarePolicyReader(policies)
    assert [p.slug for p in reader.read()] == ["real"]
```

- [ ] **Step 2: Run**

```bash
python -m pytest ingest/tests/test_policy_reader.py -v
```

Expected: both new tests PASS (the hidden skip is from `entry.name.startswith(".")`; the non-md file skip is from the `entry.suffix == ".md"` guard).

- [ ] **Step 3: Commit**

```bash
git add ingest/tests/test_policy_reader.py
git commit -m "test(INGEST-07): skip hidden entries and non-md top-level files"
```

---

## Task 5: Broken-bundle errors

**Files:**
- Modify: `ingest/tests/test_policy_reader.py`

- [ ] **Step 1: Add the tests**

```python
def test_bundle_missing_policy_md_raises(tmp_path):
    policies = tmp_path / "policies"
    policies.mkdir()
    bundle = policies / "retention"
    bundle.mkdir()
    (bundle / "data.yaml").write_text("classifications: []\n", encoding="utf-8")

    with pytest.raises(BundleError, match="missing policy.md"):
        list(BundleAwarePolicyReader(policies).read())


def test_bundle_missing_data_yaml_raises(tmp_path):
    policies = tmp_path / "policies"
    policies.mkdir()
    bundle = policies / "retention"
    bundle.mkdir()
    (bundle / "policy.md").write_text(
        "---\nfoundational: true\nprovides: [classifications]\n---\n", encoding="utf-8"
    )

    with pytest.raises(BundleError, match="missing data.yaml"):
        list(BundleAwarePolicyReader(policies).read())


def test_bundle_without_foundational_flag_raises(tmp_path):
    policies = tmp_path / "policies"
    policies.mkdir()
    _make_bundle(policies, "retention", extra_frontmatter={"foundational": False})

    with pytest.raises(BundleError, match="foundational"):
        list(BundleAwarePolicyReader(policies).read())


def test_bundle_without_provides_raises(tmp_path):
    policies = tmp_path / "policies"
    policies.mkdir()
    bundle = policies / "retention"
    bundle.mkdir()
    (bundle / "policy.md").write_text(
        "---\nfoundational: true\n---\n", encoding="utf-8"
    )
    (bundle / "data.yaml").write_text("classifications: []\n", encoding="utf-8")

    with pytest.raises(BundleError, match="provides"):
        list(BundleAwarePolicyReader(policies).read())


def test_bundle_with_empty_provides_raises(tmp_path):
    policies = tmp_path / "policies"
    policies.mkdir()
    bundle = policies / "retention"
    bundle.mkdir()
    (bundle / "policy.md").write_text(
        "---\nfoundational: true\nprovides: []\n---\n", encoding="utf-8"
    )
    (bundle / "data.yaml").write_text("classifications: []\n", encoding="utf-8")

    with pytest.raises(BundleError, match="provides"):
        list(BundleAwarePolicyReader(policies).read())


def test_bundle_with_non_list_provides_raises(tmp_path):
    policies = tmp_path / "policies"
    policies.mkdir()
    bundle = policies / "retention"
    bundle.mkdir()
    (bundle / "policy.md").write_text(
        "---\nfoundational: true\nprovides: classifications\n---\n", encoding="utf-8"
    )
    (bundle / "data.yaml").write_text("classifications: []\n", encoding="utf-8")

    with pytest.raises(BundleError, match="provides"):
        list(BundleAwarePolicyReader(policies).read())


def test_bundle_with_invalid_yaml_frontmatter_raises(tmp_path):
    policies = tmp_path / "policies"
    policies.mkdir()
    bundle = policies / "retention"
    bundle.mkdir()
    (bundle / "policy.md").write_text(
        "---\nfoundational: true\nprovides:\n  - [unbalanced\n---\n", encoding="utf-8"
    )
    (bundle / "data.yaml").write_text("classifications: []\n", encoding="utf-8")

    with pytest.raises(yaml.YAMLError):
        list(BundleAwarePolicyReader(policies).read())


def test_bundle_with_invalid_yaml_data_raises(tmp_path):
    policies = tmp_path / "policies"
    policies.mkdir()
    bundle = policies / "retention"
    bundle.mkdir()
    (bundle / "policy.md").write_text(
        "---\nfoundational: true\nprovides: [classifications]\n---\n", encoding="utf-8"
    )
    (bundle / "data.yaml").write_text("classifications:\n  - [unbalanced\n", encoding="utf-8")

    with pytest.raises(BundleError, match="data.yaml"):
        list(BundleAwarePolicyReader(policies).read())
```

- [ ] **Step 2: Run and confirm pass**

```bash
python -m pytest ingest/tests/test_policy_reader.py -v
```

Expected: all 8 new tests PASS (Task 2's `_read_bundle` covers most; the YAML-error case in frontmatter propagates from `yaml.safe_load`; the data.yaml error case is caught by the explicit `try/except` in `_read_bundle`).

Two `tmp_path`-related notes for the implementer:
1. `pytest.raises(BundleError, match="...")` uses a regex. Use literal substrings that cannot contain regex metacharacters (`"missing policy.md"`, `"missing data.yaml"`, `"provides"`, `"foundational"`, `"data.yaml"`). DO NOT match on the full `tmp_path` portion of the error message; the path may contain regex metacharacters on some systems.
2. `yaml.safe_load` returns `None` for empty input. The `_split_frontmatter` handler explicitly coerces `None → {}` so the foundational check still fires correctly.

- [ ] **Step 3: Commit**

```bash
git add ingest/tests/test_policy_reader.py
git commit -m "test(INGEST-07): broken-bundle error coverage (8 cases)"
```

---

## Task 6: Root-level error paths

**Files:**
- Modify: `ingest/tests/test_policy_reader.py`

- [ ] **Step 1: Add the tests**

```python
def test_missing_policies_root_raises(tmp_path):
    missing = tmp_path / "nope"
    with pytest.raises(FileNotFoundError, match="policies root"):
        list(BundleAwarePolicyReader(missing).read())


def test_policies_root_is_not_a_directory_raises(tmp_path):
    not_a_dir = tmp_path / "file.txt"
    not_a_dir.write_text("x", encoding="utf-8")
    with pytest.raises(NotADirectoryError, match="not a directory"):
        list(BundleAwarePolicyReader(not_a_dir).read())


def test_empty_policies_root_yields_no_entries(tmp_path):
    policies = tmp_path / "policies"
    policies.mkdir()
    assert list(BundleAwarePolicyReader(policies).read()) == []
```

- [ ] **Step 2: Run and commit**

```bash
python -m pytest ingest/tests/test_policy_reader.py -v
```

Expected: 3 new tests PASS.

```bash
git add ingest/tests/test_policy_reader.py
git commit -m "test(INGEST-07): root-dir error and empty-root coverage"
```

---

## Task 7: Final verification + handoff

**Files:**
- None modified.

- [ ] **Step 1: Confirm clean tree and full repo test pass**

```bash
git status
git log --oneline main..HEAD
cd /Users/chuck/PolicyWonk && python -m pytest -v
```

Expected: clean tree; 6 commits since BASE; full suite green (116 baseline + new tests from Tasks 1-6). Capture the total green count.

- [ ] **Step 2: Sanity-check against the real PT bundle**

The PT repo's `policies/document-retention/` bundle is live at `Diocese-of-Pensacola-Tallahassee/pt-policy@34a1671`. The implementing subagent will not clone PT (APP-05 owns that). For a confidence smoke, point the reader at the local /tmp/pt-policy-scaffold clone if it still exists, otherwise skip and note in self-report. The unit tests are authoritative.

```bash
if [ -d /tmp/pt-policy-scaffold/policies ]; then
  python -c "
from pathlib import Path
from ingest.policy_reader import BundleAwarePolicyReader
r = BundleAwarePolicyReader(Path('/tmp/pt-policy-scaffold/policies'))
for p in r.read():
    print(f'{p.slug}: kind={p.kind} foundational={p.foundational} provides={p.provides}')
"
else
  echo "no PT clone available for smoke; unit tests authoritative"
fi
```

Expected (if PT clone present): one line — `document-retention: kind=bundle foundational=True provides=('classifications', 'retention-schedule')`.

- [ ] **Step 3: Self-report**

Cover:
- Goal in one sentence.
- Files created (paths only).
- Commit list (`git log --oneline main..HEAD`).
- Test count before / after.
- Any spec gaps surfaced during implementation.
- Any judgment calls the reviewer should spot-check (e.g., the choice to validate but not cache data.yaml in `_read_bundle`).

- [ ] **Step 4: Handoff to code review**

Do not merge. Hand the branch + self-report back to the dispatching session for `superpowers:requesting-code-review`.

---

## Definition of Done

- `ingest/policy_reader.py` exists with `BundleAwarePolicyReader`, `LogicalPolicy` frozen dataclass, `BundleError` exception, `_split_frontmatter` and `_read_bundle` helpers.
- `ingest/tests/test_policy_reader.py` exists with at least 17 tests covering: flat happy path; bundle happy path; mixed/sort; hidden-entry skip; non-md file skip; 8 broken-bundle errors; 2 root-error cases; empty-root case.
- All tests pass from both `ingest/tests/` cwd and the repo root.
- Full repo suite remains green.
- No edits outside the two files listed in **File Structure**.
- No em dashes anywhere in new content.
- No PT-specific / "Pensacola-Tallahassee" / "PT" tokens in `ingest/policy_reader.py` or `ingest/tests/test_policy_reader.py` (the reader is diocese-agnostic; tests use synthetic `retention`/`onboarding`/`appendix-a` fixtures).
- `LocalFolderConnector` and its tests are untouched.
- 6 commits on the branch since BASE `d9da925`, all with `INGEST-07` in the message.
- The implementer's self-report includes the count of new tests and the green count of the full suite before/after.
