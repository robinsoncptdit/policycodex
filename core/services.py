"""Service functions for the catalog and policy-edit flows (F5 thin-views refactor).

Business logic extracted from core/views.py so the views are thin request/response
wrappers (frontend-portability rule). Collaborators (provider, reader, propose_change,
render/yaml helpers) are injected by the caller, keeping these functions pure of
GitHub/network state and keeping the existing core.views.* patch targets live for
the view test suite. propose_change (app.git_provider.propose) stays the git
primitive these services call via the injected propose_fn.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def build_catalog(policies_dir, working_dir, *, reader_cls, load_taxonomy, gate_lookup_fn) -> dict:
    """Assemble catalog rows + gap count + pending-review list from the working copy.

    Pure assembly: no request, no render, no Django. Collaborators are injected so
    callers control provider/reader/taxonomy resolution and so the existing
    core.views patch targets keep intercepting. Returns
    {"rows": [...], "gap_count": int, "pending_review": [...]}.
    """
    from ai.gap_detection import is_gap, known_types

    policies = list(reader_cls(policies_dir).read())
    gate_lookup = gate_lookup_fn(working_dir)

    try:
        taxonomy = load_taxonomy(policies_dir, ["classifications"])
    except Exception as exc:  # noqa: BLE001 - catalog must always render
        logger.warning("AI-13 taxonomy load failed (%s); gap detection off", exc)
        taxonomy = None
    known = known_types((taxonomy or {}).get("classifications"))

    rows = []
    gap_count = 0
    for policy in policies:
        gap = bool(known) and is_gap(policy.frontmatter.get("category"), known)
        if gap:
            gap_count += 1
        entry = gate_lookup.get(policy.slug, {"gate": "published", "pr": None})
        rows.append({"policy": policy, "gate": entry["gate"], "is_gap": gap})

    pending_review = [
        {"policy": row["policy"], "pr": gate_lookup.get(row["policy"].slug, {}).get("pr")}
        for row in rows
        if gate_lookup.get(row["policy"].slug, {}).get("gate") == "drafted"
        and gate_lookup.get(row["policy"].slug, {}).get("pr") is not None
    ]
    return {"rows": rows, "gap_count": gap_count, "pending_review": pending_review}
