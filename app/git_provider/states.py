"""Branch <-> slug naming convention helpers for PolicyCodex policy branches.

v0.1 conventions covered:

- `policycodex/draft-<slug>` (optionally `-<suffix>`): the canonical APP-04
  convention. `slug_to_branch_prefix` writes this form; `branch_to_slug`
  recovers the trailing portion as the slug (any suffix becomes part of the
  returned slug, since the helpers cannot distinguish suffix from slug bytes
  without an external schema).

- `policycodex/edit-<slug>-<8-hex-chars>`: the APP-07 edit-form convention,
  where each edit gets an 8-character hex UUID suffix to disambiguate
  concurrent edits. `branch_to_slug` strips the trailing `-<8 hex>` block to
  recover the underlying slug.

These helpers are pure string functions: importable without Django or GitHub
deps, trivial to test.
"""
from __future__ import annotations

import re

_DRAFT_PREFIX = "policycodex/draft-"
_EDIT_PREFIX = "policycodex/edit-"
_EDIT_SUFFIX_RE = re.compile(r"^(?P<slug>.+)-(?P<hex>[0-9a-f]{8})$")


def slug_to_branch_prefix(slug: str) -> str:
    """Return the canonical draft branch name for an edit of the given policy slug.

    Note: APP-07's edit form generates its own per-edit branch name via
    `core.views._make_branch_name` (which uses the `edit-` prefix with a
    UUID suffix). This helper provides the round-trippable canonical form
    used in tests and any future caller that wants the prefix without a
    suffix.
    """
    return f"{_DRAFT_PREFIX}{slug}"


def branch_to_slug(branch: str) -> str | None:
    """Recover the slug from a PolicyCodex policy branch name.

    Recognizes both `policycodex/draft-<slug>[-<suffix>]` (APP-04) and
    `policycodex/edit-<slug>-<8-hex>` (APP-07). Returns None for branches
    that do not follow either convention.

    For `edit-` branches, the trailing `-<8-hex>` block is stripped before
    returning the slug. For `draft-` branches, any trailing suffix becomes
    part of the returned slug; callers that care about exact-match should
    compare against the canonical `slug_to_branch_prefix(slug)`.
    """
    if not branch:
        return None
    if branch.startswith(_EDIT_PREFIX):
        tail = branch[len(_EDIT_PREFIX):]
        m = _EDIT_SUFFIX_RE.match(tail)
        if not m:
            return None
        return m.group("slug")
    if branch.startswith(_DRAFT_PREFIX):
        tail = branch[len(_DRAFT_PREFIX):]
        return tail or None
    return None
