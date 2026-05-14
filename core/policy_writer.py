"""Render (frontmatter, body) back to a policy.md file payload.

Inverse of ingest.policy_reader._split_frontmatter. Used by APP-07 (the
edit form view) to write the user's changes back to the local working
copy before committing.

Lossless: any frontmatter key that was present on read is preserved on
write, even if the form does not expose it. This is what lets v0.1 ship
with a narrow editable surface (title + body) without dropping
AI-extracted metadata (owner, effective_date, retention, ...) the next
time the file is re-rendered.
"""
from __future__ import annotations

from typing import Mapping

import yaml


def _render_policy_md(frontmatter: Mapping[str, object], body: str) -> str:
    """Return a string in the form `---\\n<yaml>\\n---\\n<body>`.

    `yaml.safe_dump` is used with `sort_keys=False` and
    `default_flow_style=False` to produce a stable, human-readable
    block-style block. Empty frontmatter still emits the fences so the
    file shape is consistent across all policies.
    """
    if frontmatter:
        # Coerce to a plain dict so safe_dump handles Mapping types
        # (the reader returns a dict already, but being defensive is cheap).
        fm_text = yaml.safe_dump(
            dict(frontmatter),
            sort_keys=False,
            default_flow_style=False,
            allow_unicode=True,
        )
    else:
        fm_text = ""
    # `safe_dump` always terminates with a newline; concat the fences around it.
    return f"---\n{fm_text}---\n{body}"
