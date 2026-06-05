# APP-15: Retention-Bundle Bootstrap (Wizard Screen 7) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wizard screen 7 lets the admin upload the diocese's retention-policy PDF, runs a new AI extraction that produces the `data.yaml` shape (classifications + retention schedule), shows a read-only review, and on Accept scaffolds `policies/document-retention/` as the diocese's first foundational-policy bundle in the local working copy.

**Architecture:** Four self-contained units behind the existing wizard. (1) A new AI extraction module (`ai/retention_extract.py`) turns PDF text into a `{classifications, retention_schedule}` dict and emits `data.yaml` text — pure, unit-tested with a fake provider, no network. (2) A bundle scaffolder (`app/onboarding/scaffold.py`) writes `policy.md` + `data.yaml` + `source.pdf` into the working copy, verified by round-tripping through the existing `BundleAwarePolicyReader`. (3) A file-upload form. (4) A screen-7 request handler (`app/onboarding/retention_policy.py`) wired into the generic `onboarding_step` view, using on-disk staging between the extract POST and the accept POST. Extraction runs **synchronously** in-request (no task queue in the v0.1 stack). The bundle is scaffolded to the working copy only; committing it to the policy repo is APP-16's job.

**Tech Stack:** Django 5+, pytest-django, PyYAML, the Anthropic SDK (behind `ai.provider.LLMProvider`), `pypdf` (behind `ingest.extractors.extract`).

**Known limitations to record, not solve here (v0.1):**
- A real retention schedule is ~150–240 rows. A single completion may not emit all of them within its output-token budget. Mitigation: request a high `max_tokens` (8192) and surface the extracted **row count** in the review screen so a truncated extraction is visible to the admin. Chunked extraction is a post-DISC enhancement.
- The draft is staged **on disk** under the working copy (not the Django session), so a large schedule never bloats the session.
- The review is **read-only** (Accept / Re-upload). Inline CRUD editing of classifications and retention rows is the separate post-DISC editor ticket (see the companion plan).

**Test interpreter:** `ai/venv/bin/python -m pytest` (run from repo root; `pytest.ini` wires `DJANGO_SETTINGS_MODULE`).

---

## File Structure

| File | Responsibility | New/Modify |
|------|----------------|------------|
| `ai/retention_extract.py` | Prompt, response parsing, `extract_retention_bundle`, `build_data_yaml` | Create |
| `ai/tests/test_retention_extract.py` | Unit tests for parsing + extraction + YAML emit | Create |
| `app/onboarding/scaffold.py` | `scaffold_retention_bundle` — write bundle files to the working copy | Create |
| `app/onboarding/tests/test_scaffold.py` | Round-trip scaffolder through `BundleAwarePolicyReader` | Create |
| `app/onboarding/forms.py` | Add `RetentionPolicyUploadForm` (NOT auto-registered in `_FORMS`) | Modify |
| `app/onboarding/tests/test_onboarding_forms.py` | Form validation tests | Modify (add) |
| `app/onboarding/retention_policy.py` | Screen-7 handler: upload → extract → review → accept/reupload | Create |
| `app/onboarding/views.py` | Delegate the `retention-policy` step to the handler | Modify |
| `app/onboarding/templates/onboarding/base_wizard.html` | Optional `enctype` for multipart steps | Modify |
| `app/onboarding/templates/onboarding/retention_policy_upload.html` | Upload form screen | Create |
| `app/onboarding/templates/onboarding/retention_policy_review.html` | Read-only review screen | Create |
| `app/onboarding/tests/test_onboarding_views.py` | Screen-7 flow tests; fix the last-step test | Modify |

**Build order:** Task 1 → 2 (AI module, no Django) are independent of Task 3 (scaffolder). Tasks 4–7 (form, handler, templates, view) integrate them. Do them in numeric order; each ends green and committed.

---

## Task 1: Retention-bundle AI extraction (prompt + parse + run)

**Files:**
- Create: `ai/retention_extract.py`
- Test: `ai/tests/test_retention_extract.py`

This is distinct from `spike/extract.py:extract_metadata`, which extracts *single-policy* metadata. Here we extract the *bundle data* (the 8 classifications + the retention schedule) *out of* the retention PDF.

- [ ] **Step 1: Write the failing tests for parsing + extraction**

Create `ai/tests/test_retention_extract.py`:

```python
"""Unit tests for the retention-bundle extraction (APP-15 / AI-13 work)."""
import json

import pytest

from ai.retention_extract import (
    RetentionExtractionError,
    build_data_yaml,
    extract_retention_bundle,
    parse_bundle_response,
)

VALID_BUNDLE = {
    "classifications": [
        {"id": "administrative", "name": "Administrative"},
        {"id": "financial", "name": "Financial"},
    ],
    "classifications_confidence": "high",
    "retention_schedule": [
        {"group": "Administrative Records", "type": "General correspondence",
         "retention": "3 years", "medium": "Paper/Elec", "retained_at": "On-site"},
        {"group": "Financial Records", "type": "Audited statements",
         "retention": "Permanent"},
    ],
    "retention_schedule_confidence": "medium",
}


class FakeProvider:
    """Stands in for ai.provider.LLMProvider. Returns canned text."""
    def __init__(self, text):
        self._text = text
        self.last_prompt = None
        self.last_max_tokens = None

    def complete(self, prompt, max_tokens):
        self.last_prompt = prompt
        self.last_max_tokens = max_tokens
        return self._text


def test_parse_plain_json():
    raw = json.dumps(VALID_BUNDLE)
    assert parse_bundle_response(raw) == VALID_BUNDLE


def test_parse_strips_code_fences():
    raw = "```json\n" + json.dumps(VALID_BUNDLE) + "\n```"
    assert parse_bundle_response(raw) == VALID_BUNDLE


def test_parse_rejects_non_json():
    with pytest.raises(RetentionExtractionError, match="JSON"):
        parse_bundle_response("this is not json")


def test_parse_rejects_missing_keys():
    with pytest.raises(RetentionExtractionError, match="classifications"):
        parse_bundle_response(json.dumps({"retention_schedule": []}))


def test_extract_calls_provider_and_parses():
    provider = FakeProvider(json.dumps(VALID_BUNDLE))
    result = extract_retention_bundle(provider, "PDF TEXT HERE")
    assert result == VALID_BUNDLE
    # The document text is injected into the prompt and budget is generous.
    assert "PDF TEXT HERE" in provider.last_prompt
    assert provider.last_max_tokens >= 8192
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `ai/venv/bin/python -m pytest ai/tests/test_retention_extract.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'ai.retention_extract'`.

- [ ] **Step 3: Implement the prompt + parser + runner**

Create `ai/retention_extract.py`:

```python
"""Extract a foundational retention bundle (classifications + retention
schedule) from a diocese's retention-policy document.

Distinct from spike/extract.py's single-policy metadata extraction: this
reads ONE source-of-truth document and returns the structured data that
becomes policies/document-retention/data.yaml (APP-15). Provider-agnostic
via ai.provider.LLMProvider, so it is unit-testable without a network call.
"""
from __future__ import annotations

import json
from typing import Any

import yaml

from ai.provider import LLMProvider

# Generous output budget: a real schedule can run to a few hundred rows.
# See the plan's "Known limitations": a single completion may still truncate.
EXTRACTION_MAX_TOKENS = 8192

RETENTION_BUNDLE_PROMPT = """\
You are a records-management archivist for a Catholic diocese. You are given
the full text of the diocese's Document Retention Policy. Extract two
independent structures:

1. classifications: the top-level data classifications the policy defines
   (often a "Section 3.0" or similar). Each has a stable lowercase slug `id`
   (ascii, words joined by hyphens) and a human `name`.
2. retention_schedule: every row of the record-retention schedule (often an
   "Appendix A"). Each row has a `group`, a record `type`, and a `retention`
   value. `retention` is free text, copied verbatim (e.g. "Permanent",
   "7 years", "Termination + 4 years"). Optional per row: `sub_group`,
   `medium`, `retained_at`.

Be faithful to the document. Do not invent rows or classifications. Copy
retention values verbatim. Output STRICTLY one JSON object, no prose:

{
  "classifications": [{"id": "<slug>", "name": "<name>"}],
  "classifications_confidence": "<low | medium | high>",
  "retention_schedule": [
    {"group": "<group>", "sub_group": "<or omit>", "type": "<record type>",
     "retention": "<verbatim>", "medium": "<or omit>", "retained_at": "<or omit>"}
  ],
  "retention_schedule_confidence": "<low | medium | high>"
}

Document text follows. Output only the JSON object.
---
"""

_REQUIRED_KEYS = ("classifications", "retention_schedule")


class RetentionExtractionError(ValueError):
    """The model output could not be read as a retention bundle."""


def parse_bundle_response(raw: str) -> dict[str, Any]:
    """Parse the model's text into a bundle dict, or raise RetentionExtractionError."""
    text = raw.strip()
    if text.startswith("```"):
        # Strip a ```json ... ``` fence the same way the spike does.
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip().rstrip("`").strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RetentionExtractionError(f"model did not return JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise RetentionExtractionError("model JSON was not an object")
    for key in _REQUIRED_KEYS:
        if key not in parsed:
            raise RetentionExtractionError(f"model JSON missing required key: {key}")
    return parsed


def extract_retention_bundle(provider: LLMProvider, document_text: str) -> dict[str, Any]:
    """Run the extraction prompt against the retention document text."""
    prompt = RETENTION_BUNDLE_PROMPT + document_text[:50000]
    raw = provider.complete(prompt, EXTRACTION_MAX_TOKENS)
    return parse_bundle_response(raw)
```

(`build_data_yaml` lands in Task 2; its test is already importing it, so Task 1's suite will still error on that import until Task 2 — run only the Task-1 tests in Step 4.)

- [ ] **Step 4: Run the parsing/extraction tests to verify they pass**

Run: `ai/venv/bin/python -m pytest ai/tests/test_retention_extract.py -q -k "parse or extract_calls"`
Expected: the 6 parse/extract tests PASS. (`build_data_yaml` tests come in Task 2.)

- [ ] **Step 5: Commit**

```bash
git add ai/retention_extract.py ai/tests/test_retention_extract.py
git commit -m "feat(ai): retention-bundle extraction prompt + response parser (APP-15)"
```

---

## Task 2: Emit `data.yaml` text from an extracted bundle

**Files:**
- Modify: `ai/retention_extract.py`
- Test: `ai/tests/test_retention_extract.py:test_build_data_yaml_*`

- [ ] **Step 1: Write the failing tests**

Append to `ai/tests/test_retention_extract.py`:

```python
def test_build_data_yaml_round_trips():
    text = build_data_yaml(VALID_BUNDLE)
    loaded = yaml.safe_load(text)
    assert [c["id"] for c in loaded["classifications"]] == ["administrative", "financial"]
    assert loaded["retention_schedule"][0]["group"] == "Administrative Records"
    assert loaded["retention_schedule"][1]["retention"] == "Permanent"


def test_build_data_yaml_omits_blank_optional_keys():
    text = build_data_yaml(VALID_BUNDLE)
    loaded = yaml.safe_load(text)
    # Row 2 had no medium/retained_at/sub_group -> those keys are absent.
    assert set(loaded["retention_schedule"][1]) == {"group", "type", "retention"}


def test_build_data_yaml_rejects_row_missing_required_field():
    bad = {"classifications": [{"id": "x", "name": "X"}],
           "retention_schedule": [{"group": "G", "type": "T"}]}  # no retention
    with pytest.raises(RetentionExtractionError, match="retention"):
        build_data_yaml(bad)


def test_build_data_yaml_rejects_classification_missing_id():
    bad = {"classifications": [{"name": "X"}], "retention_schedule": []}
    with pytest.raises(RetentionExtractionError, match="id"):
        build_data_yaml(bad)
```

Need `import yaml` at the top of the test file:

```python
import yaml
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `ai/venv/bin/python -m pytest ai/tests/test_retention_extract.py -q -k build_data_yaml`
Expected: FAIL with `ImportError: cannot import name 'build_data_yaml'` (already imported at top) — or AttributeError. Either way, red.

- [ ] **Step 3: Implement `build_data_yaml`**

Append to `ai/retention_extract.py`:

```python
_CLASSIFICATION_KEYS = ("id", "name")
_RETENTION_REQUIRED = ("group", "type", "retention")
_RETENTION_OPTIONAL = ("sub_group", "medium", "retained_at")


def _clean_classification(entry: dict[str, Any]) -> dict[str, Any]:
    for key in _CLASSIFICATION_KEYS:
        if not entry.get(key):
            raise RetentionExtractionError(f"classification missing '{key}': {entry!r}")
    return {"id": str(entry["id"]), "name": str(entry["name"])}


def _clean_retention_row(row: dict[str, Any]) -> dict[str, Any]:
    for key in _RETENTION_REQUIRED:
        if not row.get(key):
            raise RetentionExtractionError(f"retention row missing '{key}': {row!r}")
    # group, then optional sub_group, then type/retention, then remaining optionals.
    cleaned: dict[str, Any] = {"group": str(row["group"])}
    if row.get("sub_group"):
        cleaned["sub_group"] = str(row["sub_group"])
    cleaned["type"] = str(row["type"])
    cleaned["retention"] = str(row["retention"])
    for key in ("medium", "retained_at"):
        if row.get(key):
            cleaned[key] = str(row[key])
    return cleaned


def build_data_yaml(bundle: dict[str, Any]) -> str:
    """Render an extracted bundle into the canonical data.yaml text.

    Validates that every classification has id+name and every retention row
    has group+type+retention; blank optional keys are omitted. Raises
    RetentionExtractionError on a malformed row so the caller can re-prompt.
    """
    classifications = [_clean_classification(c) for c in bundle.get("classifications", [])]
    schedule = [_clean_retention_row(r) for r in bundle.get("retention_schedule", [])]
    doc = {"classifications": classifications, "retention_schedule": schedule}
    return yaml.safe_dump(doc, sort_keys=False, default_flow_style=False, allow_unicode=True)
```

- [ ] **Step 4: Run the whole module's tests to verify they pass**

Run: `ai/venv/bin/python -m pytest ai/tests/test_retention_extract.py -q`
Expected: all tests PASS (10 total).

- [ ] **Step 5: Commit**

```bash
git add ai/retention_extract.py ai/tests/test_retention_extract.py
git commit -m "feat(ai): emit data.yaml text from an extracted retention bundle (APP-15)"
```

---

## Task 3: Bundle scaffolder

**Files:**
- Create: `app/onboarding/scaffold.py`
- Test: `app/onboarding/tests/test_scaffold.py`

The scaffolder writes bytes; it does not validate the data (Task 2 already did). Correctness is proven by reading the result back through the production `BundleAwarePolicyReader`.

- [ ] **Step 1: Write the failing round-trip test**

Create `app/onboarding/tests/test_scaffold.py`:

```python
"""Scaffolder writes a valid foundational bundle (APP-15)."""
import yaml

from app.onboarding.scaffold import scaffold_retention_bundle
from ingest.policy_reader import BundleAwarePolicyReader

DATA_YAML = (
    "classifications:\n"
    "- id: administrative\n"
    "  name: Administrative\n"
    "- id: financial\n"
    "  name: Financial\n"
    "retention_schedule:\n"
    "- group: Administrative Records\n"
    "  type: General correspondence\n"
    "  retention: 3 years\n"
)


def test_scaffold_writes_readable_foundational_bundle(tmp_path):
    policies_dir = tmp_path / "policies"
    policies_dir.mkdir()
    source_pdf = tmp_path / "src.pdf"
    source_pdf.write_bytes(b"%PDF-1.4 fake")

    bundle_dir = scaffold_retention_bundle(
        policies_dir,
        title="Document Retention Policy",
        owner="CFO",
        narrative="# Document Retention Policy\n\nBootstrapped.\n",
        data_yaml_text=DATA_YAML,
        source_pdf=source_pdf,
    )

    assert bundle_dir == policies_dir / "document-retention"
    assert (bundle_dir / "policy.md").is_file()
    assert (bundle_dir / "data.yaml").is_file()
    assert (bundle_dir / "source.pdf").read_bytes() == b"%PDF-1.4 fake"

    # The production reader must accept it as a foundational bundle.
    policies = list(BundleAwarePolicyReader(policies_dir).read())
    assert len(policies) == 1
    policy = policies[0]
    assert policy.slug == "document-retention"
    assert policy.kind == "bundle"
    assert policy.foundational is True
    assert policy.provides == ("classifications", "retention-schedule")
    assert policy.frontmatter["title"] == "Document Retention Policy"

    data = yaml.safe_load((bundle_dir / "data.yaml").read_text())
    assert [c["id"] for c in data["classifications"]] == ["administrative", "financial"]


def test_scaffold_without_source_pdf_omits_it(tmp_path):
    policies_dir = tmp_path / "policies"
    policies_dir.mkdir()
    bundle_dir = scaffold_retention_bundle(
        policies_dir, title="T", owner="CFO",
        narrative="# T\n", data_yaml_text=DATA_YAML, source_pdf=None,
    )
    assert not (bundle_dir / "source.pdf").exists()
    # Still a valid bundle.
    assert list(BundleAwarePolicyReader(policies_dir).read())[0].foundational is True
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `ai/venv/bin/python -m pytest app/onboarding/tests/test_scaffold.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.onboarding.scaffold'`.

- [ ] **Step 3: Implement the scaffolder**

Create `app/onboarding/scaffold.py`:

```python
"""Scaffold the diocese's first foundational-policy bundle (APP-15).

Writes policies/document-retention/{policy.md, data.yaml, source.pdf} into
the local working copy. Committing the bundle to the policy repo is APP-16.
The on-disk shape is the contract enforced by ingest.policy_reader.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import yaml

BUNDLE_SLUG = "document-retention"
PROVIDES = ["classifications", "retention-schedule"]


def scaffold_retention_bundle(
    policies_dir: Path,
    *,
    title: str,
    owner: str,
    narrative: str,
    data_yaml_text: str,
    source_pdf: Path | None,
) -> Path:
    """Create the document-retention bundle under `policies_dir`. Returns its dir."""
    bundle_dir = Path(policies_dir) / BUNDLE_SLUG
    bundle_dir.mkdir(parents=True, exist_ok=True)

    frontmatter = yaml.safe_dump(
        {"title": title, "owner": owner, "foundational": True, "provides": PROVIDES},
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
    )
    body = narrative if narrative.endswith("\n") else narrative + "\n"
    (bundle_dir / "policy.md").write_text(f"---\n{frontmatter}---\n\n{body}", encoding="utf-8")

    text = data_yaml_text if data_yaml_text.endswith("\n") else data_yaml_text + "\n"
    (bundle_dir / "data.yaml").write_text(text, encoding="utf-8")

    if source_pdf is not None:
        shutil.copyfile(source_pdf, bundle_dir / "source.pdf")

    return bundle_dir
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `ai/venv/bin/python -m pytest app/onboarding/tests/test_scaffold.py -q`
Expected: both tests PASS.

- [ ] **Step 5: Commit**

```bash
git add app/onboarding/scaffold.py app/onboarding/tests/test_scaffold.py
git commit -m "feat(app): foundational-bundle scaffolder for onboarding (APP-15)"
```

---

## Task 4: Upload form

**Files:**
- Modify: `app/onboarding/forms.py`
- Test: `app/onboarding/tests/test_onboarding_forms.py`

The form is intentionally NOT added to the `_FORMS` registry: screen 7 has a custom multi-action handler (Task 5), not the generic single-form flow.

- [ ] **Step 1: Write the failing form tests**

Append to `app/onboarding/tests/test_onboarding_forms.py` (add the import at the top of the file if absent):

```python
from django.core.files.uploadedfile import SimpleUploadedFile

from app.onboarding.forms import RetentionPolicyUploadForm


def test_retention_upload_requires_a_file():
    form = RetentionPolicyUploadForm(data={}, files={})
    assert not form.is_valid()
    assert "pdf_file" in form.errors


def test_retention_upload_rejects_non_pdf():
    upload = SimpleUploadedFile("policy.txt", b"hello", content_type="text/plain")
    form = RetentionPolicyUploadForm(data={}, files={"pdf_file": upload})
    assert not form.is_valid()
    assert "pdf_file" in form.errors


def test_retention_upload_accepts_pdf():
    upload = SimpleUploadedFile("policy.pdf", b"%PDF-1.4 ...", content_type="application/pdf")
    form = RetentionPolicyUploadForm(data={}, files={"pdf_file": upload})
    assert form.is_valid(), form.errors
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `ai/venv/bin/python -m pytest app/onboarding/tests/test_onboarding_forms.py -q -k retention_upload`
Expected: FAIL with `ImportError: cannot import name 'RetentionPolicyUploadForm'`.

- [ ] **Step 3: Implement the form**

In `app/onboarding/forms.py`, add after the `GitHubRepoForm` class (and before `_FORMS`):

```python
class RetentionPolicyUploadForm(forms.Form):
    pdf_file = forms.FileField(
        label="Retention policy PDF",
        help_text="Upload your diocese's Document Retention Policy as a PDF.",
    )

    def clean_pdf_file(self):
        upload = self.cleaned_data["pdf_file"]
        if not upload.name.lower().endswith(".pdf"):
            raise forms.ValidationError("Upload a PDF file (.pdf).")
        return upload
```

Leave `_FORMS` unchanged (no `"retention-policy"` entry).

- [ ] **Step 4: Run the tests to verify they pass**

Run: `ai/venv/bin/python -m pytest app/onboarding/tests/test_onboarding_forms.py -q -k retention_upload`
Expected: 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add app/onboarding/forms.py app/onboarding/tests/test_onboarding_forms.py
git commit -m "feat(app): retention-policy PDF upload form (APP-15)"
```

---

## Task 5: Screen-7 handler + view delegation + templates

**Files:**
- Create: `app/onboarding/retention_policy.py`
- Modify: `app/onboarding/views.py`
- Modify: `app/onboarding/templates/onboarding/base_wizard.html`
- Create: `app/onboarding/templates/onboarding/retention_policy_upload.html`
- Create: `app/onboarding/templates/onboarding/retention_policy_review.html`
- Test: `app/onboarding/tests/test_onboarding_views.py`

- [ ] **Step 1: Write the failing flow tests**

Append to `app/onboarding/tests/test_onboarding_views.py`:

```python
from django.core.files.uploadedfile import SimpleUploadedFile

# Steps 1-6 payloads to reach screen 7. Only github-repo has a real form.
def _advance_to_retention_policy(client):
    client.post("/onboarding/github-repo/", GITHUB_REPO_CONTINUE)
    for slug in ["address-scheme", "versioning", "reviewer-roles", "retention", "llm-provider"]:
        client.post(f"/onboarding/{slug}/", {"action": "continue"})


FAKE_BUNDLE = {
    "classifications": [
        {"id": "administrative", "name": "Administrative"},
        {"id": "financial", "name": "Financial"},
    ],
    "classifications_confidence": "high",
    "retention_schedule": [
        {"group": "Administrative Records", "type": "Correspondence", "retention": "3 years"},
    ],
    "retention_schedule_confidence": "medium",
}


@pytest.fixture
def working_copy(settings, tmp_path):
    settings.POLICYCODEX_POLICY_REPO_URL = "https://github.com/acme/policies.git"
    settings.POLICYCODEX_WORKING_COPY_ROOT = str(tmp_path)
    # working_dir = tmp_path / "policies"
    (tmp_path / "policies").mkdir()
    return tmp_path / "policies"


@pytest.fixture
def stub_extraction(monkeypatch):
    """Avoid network + Anthropic() init; return a canned bundle and PDF text."""
    from app.onboarding import retention_policy as rp
    monkeypatch.setattr(rp, "extract_text", lambda path: "FAKE PDF TEXT")
    monkeypatch.setattr(rp, "extract_retention_bundle", lambda provider, text: FAKE_BUNDLE)
    monkeypatch.setattr(rp, "ClaudeProvider", lambda *a, **k: object())


def test_screen7_get_shows_upload_form(client, user, working_copy):
    client.force_login(user)
    _advance_to_retention_policy(client)
    resp = client.get("/onboarding/retention-policy/")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert 'enctype="multipart/form-data"' in body
    assert 'name="pdf_file"' in body
    assert "Step 7 of 7" in body


def test_screen7_extract_shows_readonly_review(client, user, working_copy, stub_extraction):
    client.force_login(user)
    _advance_to_retention_policy(client)
    upload = SimpleUploadedFile("retention.pdf", b"%PDF-1.4", content_type="application/pdf")
    resp = client.post("/onboarding/retention-policy/", {"action": "extract", "pdf_file": upload})
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "Administrative" in body
    assert "2 classifications" in body       # count surfaced (truncation visibility)
    assert "1 retention" in body
    assert 'value="accept"' in body
    assert 'value="reupload"' in body


def test_screen7_accept_scaffolds_bundle_and_finishes(client, user, working_copy, stub_extraction):
    client.force_login(user)
    _advance_to_retention_policy(client)
    upload = SimpleUploadedFile("retention.pdf", b"%PDF-1.4", content_type="application/pdf")
    client.post("/onboarding/retention-policy/", {"action": "extract", "pdf_file": upload})
    resp = client.post("/onboarding/retention-policy/", {"action": "accept"})
    assert resp.status_code == 302
    assert resp.url == "/catalog/"
    # Bundle now exists in the working copy and reads back as foundational.
    from ingest.policy_reader import BundleAwarePolicyReader
    policies = list(BundleAwarePolicyReader(working_copy).read())
    assert [p.slug for p in policies] == ["document-retention"]
    assert policies[0].foundational is True
    assert (working_copy / "document-retention" / "source.pdf").is_file()


def test_screen7_reupload_clears_draft(client, user, working_copy, stub_extraction):
    client.force_login(user)
    _advance_to_retention_policy(client)
    upload = SimpleUploadedFile("retention.pdf", b"%PDF-1.4", content_type="application/pdf")
    client.post("/onboarding/retention-policy/", {"action": "extract", "pdf_file": upload})
    resp = client.post("/onboarding/retention-policy/", {"action": "reupload"})
    assert resp.status_code == 200
    assert 'name="pdf_file"' in resp.content.decode()  # back to upload form
```

Also REPLACE the existing `test_last_step_continue_completes_and_redirects_to_catalog` (its bare-`continue` finish is the skeleton behavior APP-15 removes). Change its body to drive the new accept path:

```python
def test_last_step_continue_completes_and_redirects_to_catalog(client, user, working_copy, stub_extraction):
    client.force_login(user)
    _advance_to_retention_policy(client)
    upload = SimpleUploadedFile("retention.pdf", b"%PDF-1.4", content_type="application/pdf")
    client.post("/onboarding/retention-policy/", {"action": "extract", "pdf_file": upload})
    resp = client.post("/onboarding/retention-policy/", {"action": "accept"})
    assert resp.status_code == 302
    assert resp.url == "/catalog/"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `ai/venv/bin/python -m pytest app/onboarding/tests/test_onboarding_views.py -q -k screen7`
Expected: FAIL — `retention_policy` module / handler does not exist yet, so screen 7 still runs the generic no-op handler (no upload form, no `enctype`).

- [ ] **Step 3: Add the optional multipart enctype to the base template**

In `app/onboarding/templates/onboarding/base_wizard.html`, change the form tag (line 9) from:

```html
  <form method="post">
```
to:
```html
  <form method="post"{% if multipart %} enctype="multipart/form-data"{% endif %}>
```

- [ ] **Step 4: Create the two screen-7 templates**

Create `app/onboarding/templates/onboarding/retention_policy_upload.html`:

```html
{% extends "onboarding/base_wizard.html" %}

{% block step_content %}
  <p>Upload your diocese's Document Retention Policy. We extract its
     classifications and retention schedule for you to review.</p>
  {{ form.as_p }}
  {% if error %}<p class="wizard-error">{{ error }}</p>{% endif %}
  <div class="wizard-nav">
    <button type="submit" name="action" value="back">Back</button>
    <button type="submit" name="action" value="extract">Upload and extract</button>
    <button type="submit" name="action" value="save_exit">Save and exit</button>
  </div>
{% endblock %}
```

Create `app/onboarding/templates/onboarding/retention_policy_review.html`:

```html
{% extends "onboarding/base_wizard.html" %}

{% block step_content %}
  <p>Review the extracted data. Accept to scaffold your foundational
     Document Retention Policy, or re-upload a corrected PDF.</p>

  <h3>{{ classifications|length }} classifications</h3>
  <table class="review-table">
    <thead><tr><th>id</th><th>name</th></tr></thead>
    <tbody>
      {% for c in classifications %}
        <tr><td>{{ c.id }}</td><td>{{ c.name }}</td></tr>
      {% endfor %}
    </tbody>
  </table>

  <h3>{{ retention_schedule|length }} retention rows</h3>
  <table class="review-table">
    <thead><tr><th>group</th><th>type</th><th>retention</th></tr></thead>
    <tbody>
      {% for r in retention_schedule %}
        <tr><td>{{ r.group }}</td><td>{{ r.type }}</td><td>{{ r.retention }}</td></tr>
      {% endfor %}
    </tbody>
  </table>

  <div class="wizard-nav">
    <button type="submit" name="action" value="reupload">Re-upload a different PDF</button>
    <button type="submit" name="action" value="accept">Accept and scaffold</button>
  </div>
{% endblock %}
```

Note: the review template overrides the default nav buttons inside `step_content`; the base still wraps a single `<form>` with the CSRF token, so these buttons post back to the same step. The literal text `"{{ count }} classifications"` the tests assert is produced by `{{ classifications|length }} classifications` (Django renders `2 classifications`). Likewise `1 retention` is the prefix of `1 retention rows`.

- [ ] **Step 5: Implement the handler**

Create `app/onboarding/retention_policy.py`:

```python
"""Screen 7 (retention-policy) handler for the onboarding wizard (APP-15).

Custom flow, separate from the generic single-form step:
  GET                      -> upload form, or the review screen if a draft is staged
  POST action=extract      -> save PDF, extract text, run AI, stage draft, show review
  POST action=accept       -> scaffold the bundle from the staged draft, finish
  POST action=reupload     -> discard the staged draft, back to the upload form
  POST action=back/save_exit -> standard wizard navigation

The draft is staged on disk under the working copy (never the session) so a
large schedule cannot bloat the session.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import yaml
from django.contrib import messages
from django.shortcuts import redirect, render

from ai.claude_provider import ClaudeProvider
from ai.retention_extract import (
    RetentionExtractionError,
    build_data_yaml,
    extract_retention_bundle,
)
from app.onboarding import wizard
from app.onboarding.forms import RetentionPolicyUploadForm
from app.onboarding.scaffold import scaffold_retention_bundle
from app.working_copy.config import load_working_copy_config
from ingest.extractors import extract as extract_text

STEP_SLUG = "retention-policy"
DEFAULT_TITLE = "Document Retention Policy"
DEFAULT_OWNER = "CFO"
_NARRATIVE_STUB = (
    "# Document Retention Policy\n\n"
    "This foundational policy was bootstrapped from the uploaded source "
    "document during onboarding. Edit the narrative here; manage the "
    "classifications and retention schedule through the typed-table editor.\n"
)


def _paths():
    config = load_working_copy_config()
    policies_dir = config.working_dir / "policies"
    staging = config.working_dir / ".policycodex-staging" / STEP_SLUG
    return policies_dir, staging


def _base_ctx(target, state):
    return {
        "step": target,
        "index": wizard.index_of(target.slug) + 1,
        "total": len(wizard.STEPS),
        "prev_step": wizard.prev_step(target.slug),
        "is_last": wizard.is_last(target.slug),
        "is_complete": state.is_complete(target.slug),
        "multipart": True,
    }


def _render_upload(request, target, state, form=None, error=None):
    ctx = _base_ctx(target, state)
    ctx["form"] = form or RetentionPolicyUploadForm()
    ctx["error"] = error
    return render(request, "onboarding/retention_policy_upload.html", ctx)


def _render_review(request, target, state, draft):
    ctx = _base_ctx(target, state)
    ctx["classifications"] = draft.get("classifications", [])
    ctx["retention_schedule"] = draft.get("retention_schedule", [])
    return render(request, "onboarding/retention_policy_review.html", ctx)


def _load_draft(staging: Path):
    draft_file = staging / "draft.yaml"
    if not draft_file.is_file():
        return None
    return yaml.safe_load(draft_file.read_text(encoding="utf-8"))


def handle(request, target, state):
    policies_dir, staging = _paths()

    if request.method == "GET":
        # Same ahead-jump gating as the generic view.
        furthest = state.furthest_step()
        if wizard.index_of(STEP_SLUG) > wizard.index_of(furthest):
            return redirect("onboarding_step", step=furthest)
        draft = _load_draft(staging)
        if draft is not None:
            return _render_review(request, target, state, draft)
        return _render_upload(request, target, state)

    action = request.POST.get("action")
    if action == "back":
        prev = wizard.prev_step(STEP_SLUG)
        return redirect("onboarding_step", step=prev.slug if prev else STEP_SLUG)
    if action == "save_exit":
        messages.info(request, "Your progress is saved. Resume onboarding any time.")
        return redirect("catalog")

    if action == "extract":
        form = RetentionPolicyUploadForm(request.POST, request.FILES)
        if not form.is_valid():
            return _render_upload(request, target, state, form=form)
        staging.mkdir(parents=True, exist_ok=True)
        source_pdf = staging / "source.pdf"
        with source_pdf.open("wb") as fh:
            for chunk in form.cleaned_data["pdf_file"].chunks():
                fh.write(chunk)
        try:
            text = extract_text(source_pdf)
            bundle = extract_retention_bundle(ClaudeProvider(), text)
            data_yaml_text = build_data_yaml(bundle)
        except RetentionExtractionError as exc:
            return _render_upload(
                request, target, state,
                error=f"Could not read that document automatically: {exc}. "
                      "Try a different PDF.",
            )
        draft = {
            "title": DEFAULT_TITLE,
            "owner": DEFAULT_OWNER,
            "classifications": bundle.get("classifications", []),
            "retention_schedule": bundle.get("retention_schedule", []),
            "data_yaml": data_yaml_text,
        }
        (staging / "draft.yaml").write_text(
            yaml.safe_dump(draft, sort_keys=False, allow_unicode=True), encoding="utf-8"
        )
        return _render_review(request, target, state, draft)

    if action == "reupload":
        if staging.exists():
            shutil.rmtree(staging)
        return _render_upload(request, target, state)

    if action == "accept":
        draft = _load_draft(staging)
        if draft is None:
            return _render_upload(request, target, state)
        scaffold_retention_bundle(
            policies_dir,
            title=draft["title"],
            owner=draft["owner"],
            narrative=_NARRATIVE_STUB,
            data_yaml_text=draft["data_yaml"],
            source_pdf=staging / "source.pdf" if (staging / "source.pdf").is_file() else None,
        )
        shutil.rmtree(staging, ignore_errors=True)
        state.mark_complete(STEP_SLUG)
        messages.success(request, "Onboarding complete. Your retention policy is scaffolded.")
        return redirect("catalog")

    # Unknown action: re-render current state defensively.
    draft = _load_draft(staging)
    if draft is not None:
        return _render_review(request, target, state, draft)
    return _render_upload(request, target, state)
```

- [ ] **Step 6: Wire the delegation into the generic view**

In `app/onboarding/views.py`, add the import near the top (with the other `app.onboarding` imports):

```python
from app.onboarding import retention_policy
```

Then, inside `onboarding_step`, immediately after `state = WizardState(request.session)` (currently line 44), add:

```python
    if step == retention_policy.STEP_SLUG:
        return retention_policy.handle(request, target, state)
```

This runs for both GET and POST; the handler does its own gating and rendering.

- [ ] **Step 7: Run the screen-7 tests to verify they pass**

Run: `ai/venv/bin/python -m pytest app/onboarding/tests/test_onboarding_views.py -q -k "screen7 or last_step"`
Expected: all screen-7 tests + the rewritten last-step test PASS.

- [ ] **Step 8: Run the full onboarding + ai + ingest suites for regressions**

Run: `ai/venv/bin/python -m pytest app/onboarding ai/tests/test_retention_extract.py ingest -q`
Expected: all PASS (no regressions in the existing wizard tests).

- [ ] **Step 9: Commit**

```bash
git add app/onboarding/retention_policy.py app/onboarding/views.py \
        app/onboarding/templates/onboarding/base_wizard.html \
        app/onboarding/templates/onboarding/retention_policy_upload.html \
        app/onboarding/templates/onboarding/retention_policy_review.html \
        app/onboarding/tests/test_onboarding_views.py
git commit -m "feat(app): wizard screen 7 - upload, extract, review, scaffold retention bundle (APP-15)"
```

---

## Task 6: Full-suite verification

- [ ] **Step 1: Run the entire suite**

Run: `ai/venv/bin/python -m pytest -q`
Expected: the whole suite green (was 379 before this work; expect 379 + the new tests, minus none — the one rewritten test is modified in place).

- [ ] **Step 2: Confirm the count moved as expected and stop on any unexpected failure.**

If anything outside the files in this plan fails, do NOT paper over it — investigate before claiming completion (per superpowers:verification-before-completion).

---

## Self-Review (completed during planning)

- **Spec coverage:** APP-15 ticket clauses — upload retention PDF (Task 4 form + Task 5 handler), run AI extraction to a draft data.yaml (Tasks 1–2), admin reviews (Task 5 review template, read-only per the agreed scope), scaffold `policies/document-retention/` with `policy.md` `foundational: true` + `provides: [classifications, retention-schedule]`, `data.yaml`, archived `source.pdf` (Task 3 scaffolder, exercised in Task 5 accept). Commit-to-repo is explicitly deferred to APP-16 (not in this plan) per the scope decision.
- **Placeholder scan:** every code step contains complete code; no TODO/"handle errors"/"similar to" placeholders.
- **Type consistency:** `extract_retention_bundle(provider, text)`, `build_data_yaml(bundle) -> str`, `scaffold_retention_bundle(policies_dir, *, title, owner, narrative, data_yaml_text, source_pdf) -> Path`, `RetentionExtractionError`, and the handler's `STEP_SLUG`/`extract_text`/`ClaudeProvider` seams (the exact names the view tests monkeypatch) are used identically across tasks.
- **Open follow-ups (not blockers):** the handbook `<title>` placeholder and per-row CRUD editing are tracked separately (CRUD = the companion edit-slice plan). Large-schedule truncation is surfaced via the review row counts, with chunked extraction noted as post-DISC.
```
