"""Locate and load a diocese's foundational taxonomy bundle.

Django-free so both the standalone spike (`spike/extract.py`) and the
app's extraction path can use it. The app passes the working_dir from
`app.working_copy.config.load_working_copy_config()`; the spike resolves
the policies dir from an env var. Both then call into here.

The foundational bundle is found by CAPABILITY (its `provides:` list),
never by a hardcoded slug, so any diocese's retention bundle works.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from ingest.policy_reader import BundleAwarePolicyReader


def load_foundational_taxonomy(policies_dir, required):
    """Stub - implemented in Task 3."""
    raise NotImplementedError


def resolve_taxonomy(policies_dir, required, seed_path):
    """Stub - implemented in Task 3."""
    raise NotImplementedError


def find_foundational_bundle(policies_dir, required):
    """Return the data.yaml Path of the foundational policy whose `provides`
    covers every capability in `required`, or None.

    Returns None when `policies_dir` is missing or not a directory, or when
    no foundational bundle provides all required capabilities. A malformed
    bundle (invalid policy.md or data.yaml) raises BundleError from the
    reader; that surfaces deliberately rather than silently falling back.
    """
    policies_dir = Path(policies_dir)
    if not policies_dir.is_dir():
        return None
    required_set = set(required)
    for policy in BundleAwarePolicyReader(policies_dir).read():
        if policy.foundational and required_set.issubset(set(policy.provides)):
            return policy.data_path
    return None
