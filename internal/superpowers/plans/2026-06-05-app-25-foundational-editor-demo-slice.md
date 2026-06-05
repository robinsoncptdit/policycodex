# APP-25: Foundational Typed-Table Editor (Demo Slice) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give a foundational policy (the `document-retention` bundle) an editable typed-table UI: edit the classifications and the retention rows (add / edit / delete), then write the result back to `data.yaml` and open a pull request through the existing Drafted → Reviewed → Published gate flow. This is the "and here's you editing it live" second act of the DISC demo.

**Architecture:** The existing `core.views.policy_edit` flow already proves the gate sequence for flat policies (write file → `branch` → `commit` → `push` → `open_pr`), and it explicitly **403s foundational policies**, pointing them at "the typed-table UI (APP-20)" — which is exactly this editor. We add a sibling view `foundational_edit` at `policies/<slug>/foundational-edit/`. It renders two Django **formsets** (classifications, retention rows) with `can_delete=True` and one blank add-row, validates them, assembles a `{classifications, retention_schedule}` bundle, emits `data.yaml` by **reusing `ai.retention_extract.build_data_yaml`** (from the APP-15 plan), writes it, and runs the same four GitHub operations committing `data.yaml` instead of `policy.md`. The `approve_pr` and `publish_policy` views need **no change** — they operate by slug/PR via `branch_to_slug`, and `_make_branch_name` already produces an `edit-<slug>-<hex>` branch that `branch_to_slug` recognizes.

**Tech Stack:** Django 5+ formsets, pytest-django, PyYAML, the existing `app.git_provider.GitHubProvider` (mocked in tests). Server-rendered — no JS framework, consistent with the current stack.

**Dependency:** Requires the APP-15 plan's Tasks 1–2 merged, which create `ai/retention_extract.py` with `build_data_yaml(bundle) -> str` and `RetentionExtractionError`. This plan reuses both (DRY: one emitter for both bootstrap and edit).

**Scope (demo slice, agreed):**
- IN: edit classification rows; add/edit/delete retention rows; write-back to `data.yaml`; PR through the gate model; reachable from the catalog.
- OUT (post-DISC hardening, separate ticket): reuse inside the APP-23 detail view; pagination/virtualization for very large schedules (this slice renders all rows as inputs on one page — fine for a demo, heavy for 240 rows); soft-delete/`deprecated:` semantics for classifications referenced by other policies; optimistic-concurrency/mtime checks (the existing flat editor documents the same single-admin assumption at `core/views.py:169-175`).

**Test interpreter:** `ai/venv/bin/python -m pytest` (run from repo root).

---

## File Structure

| File | Responsibility | New/Modify |
|------|----------------|------------|
| `core/forms.py` | `ClassificationForm`, `RetentionRowForm`, `ClassificationFormSet`, `RetentionRowFormSet`, `FoundationalEditMetaForm` (summary) | Modify |
| `core/tests/test_foundational_edit_forms.py` | Formset validation unit tests | Create |
| `core/urls.py` | Route `policies/<slug>/foundational-edit/` | Modify |
| `core/views.py` | `foundational_edit` view (GET render, POST write + gate sequence) | Modify |
| `core/templates/foundational_edit.html` | The two editable typed tables + summary + submit | Create |
| `core/templates/catalog.html` | Turn the foundational static text into a link to the editor | Modify |
| `core/tests/test_foundational_edit.py` | View tests: routing, GET, redirect, POST write + provider sequence, delete, invalid, failure | Create |

**Build order:** Task 1 (forms) → Task 2 (view GET + routing + templates + catalog link) → Task 3 (view POST + gate sequence) → Task 4 (full-suite verification). Each ends green and committed.

---

## Task 1: Editor forms + formsets

**Files:**
- Modify: `core/forms.py`
- Test: `core/tests/test_foundational_edit_forms.py`

- [ ] **Step 1: Write the failing form tests**

Create `core/tests/test_foundational_edit_forms.py`:

```python
"""Unit tests for the foundational typed-table editor formsets (APP-25)."""
from core.forms import (
    ClassificationForm,
    ClassificationFormSet,
    RetentionRowForm,
    RetentionRowFormSet,
)


def _mgmt(prefix, total, initial):
    return {
        f"{prefix}-TOTAL_FORMS": str(total),
        f"{prefix}-INITIAL_FORMS": str(initial),
        f"{prefix}-MIN_NUM_FORMS": "0",
        f"{prefix}-MAX_NUM_FORMS": "1000",
    }


def test_classification_form_requires_id_and_name():
    form = ClassificationForm(data={"id": "", "name": ""})
    assert not form.is_valid()
    assert "id" in form.errors
    assert "name" in form.errors


def test_retention_row_requires_group_type_retention():
    form = RetentionRowForm(data={"group": "", "type": "", "retention": ""})
    assert not form.is_valid()
    assert "group" in form.errors
    assert "type" in form.errors
    assert "retention" in form.errors


def test_retention_row_optional_fields_not_required():
    form = RetentionRowForm(data={"group": "G", "type": "T", "retention": "3 years"})
    assert form.is_valid(), form.errors
    assert form.cleaned_data["sub_group"] == ""
    assert form.cleaned_data["medium"] == ""


def test_classification_formset_extra_blank_row_is_ignored():
    data = _mgmt("cls", total=2, initial=1)
    data.update({
        "cls-0-id": "administrative", "cls-0-name": "Administrative",
        "cls-1-id": "", "cls-1-name": "",  # blank extra -> ignored
    })
    fs = ClassificationFormSet(data, prefix="cls")
    assert fs.is_valid(), fs.errors
    # Only the filled form carries data.
    filled = [f.cleaned_data for f in fs if f.cleaned_data and not f.cleaned_data.get("DELETE")]
    assert filled == [{"id": "administrative", "name": "Administrative", "DELETE": False}]


def test_classification_formset_marks_delete():
    data = _mgmt("cls", total=2, initial=2)
    data.update({
        "cls-0-id": "administrative", "cls-0-name": "Administrative",
        "cls-1-id": "legal", "cls-1-name": "Legal", "cls-1-DELETE": "on",
    })
    fs = ClassificationFormSet(data, prefix="cls")
    assert fs.is_valid(), fs.errors
    kept = [f.cleaned_data["id"] for f in fs
            if f.cleaned_data and not f.cleaned_data.get("DELETE")]
    assert kept == ["administrative"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `ai/venv/bin/python -m pytest core/tests/test_foundational_edit_forms.py -q`
Expected: FAIL with `ImportError: cannot import name 'ClassificationForm'`.

- [ ] **Step 3: Implement the forms + formsets**

Append to `core/forms.py`:

```python
class ClassificationForm(forms.Form):
    """One classification row (id + display name) in the typed-table editor (APP-25)."""
    id = forms.SlugField(
        label="id",
        help_text="Stable lowercase slug; other policies reference this.",
        widget=forms.TextInput(attrs={"autocomplete": "off"}),
    )
    name = forms.CharField(
        max_length=200,
        label="name",
        widget=forms.TextInput(attrs={"autocomplete": "off"}),
    )


class RetentionRowForm(forms.Form):
    """One retention-schedule row. group/type/retention required; rest optional."""
    group = forms.CharField(max_length=300, widget=forms.TextInput(attrs={"autocomplete": "off"}))
    sub_group = forms.CharField(max_length=300, required=False, widget=forms.TextInput(attrs={"autocomplete": "off"}))
    type = forms.CharField(max_length=500, widget=forms.TextInput(attrs={"autocomplete": "off"}))
    retention = forms.CharField(max_length=200, widget=forms.TextInput(attrs={"autocomplete": "off"}))
    medium = forms.CharField(max_length=120, required=False, widget=forms.TextInput(attrs={"autocomplete": "off"}))
    retained_at = forms.CharField(max_length=200, required=False, widget=forms.TextInput(attrs={"autocomplete": "off"}))


class FoundationalEditMetaForm(forms.Form):
    """The commit-message summary for a foundational edit."""
    summary = forms.CharField(
        max_length=200,
        required=False,
        help_text="Optional one-line description of your change. Becomes the commit message.",
        widget=forms.TextInput(attrs={"autocomplete": "off"}),
    )


ClassificationFormSet = forms.formset_factory(
    ClassificationForm, can_delete=True, extra=1
)
RetentionRowFormSet = forms.formset_factory(
    RetentionRowForm, can_delete=True, extra=1
)
```

Add `from django import forms` is already at the top of `core/forms.py` (line 2) — no new import needed.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `ai/venv/bin/python -m pytest core/tests/test_foundational_edit_forms.py -q`
Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add core/forms.py core/tests/test_foundational_edit_forms.py
git commit -m "feat(core): typed-table editor formsets for foundational policies (APP-25)"
```

---

## Task 2: View GET, routing, templates, catalog link

**Files:**
- Modify: `core/urls.py`
- Modify: `core/views.py`
- Create: `core/templates/foundational_edit.html`
- Modify: `core/templates/catalog.html`
- Test: `core/tests/test_foundational_edit.py`

- [ ] **Step 1: Write the failing routing + GET tests**

Create `core/tests/test_foundational_edit.py`:

```python
"""Tests for the foundational typed-table editor view (APP-25)."""
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse

from ingest.policy_reader import LogicalPolicy

User = get_user_model()

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
    "- group: Financial Records\n"
    "  type: Audited statements\n"
    "  retention: Permanent\n"
)


@pytest.fixture
def user(db):
    return User.objects.create_user(
        username="editor", password="hunter2hunter2",
        email="editor@example.com", first_name="Pat", last_name="Editor",
    )


def _bundle_on_disk(tmp_path):
    """Write a real document-retention bundle; return (policies_dir, LogicalPolicy)."""
    policies_dir = tmp_path / "policies"
    bundle = policies_dir / "document-retention"
    bundle.mkdir(parents=True)
    (bundle / "policy.md").write_text(
        "---\ntitle: Document Retention Policy\nowner: CFO\n"
        "foundational: true\nprovides:\n- classifications\n- retention-schedule\n---\n\n# DRP\n",
        encoding="utf-8",
    )
    (bundle / "data.yaml").write_text(DATA_YAML, encoding="utf-8")
    policy = LogicalPolicy(
        slug="document-retention", kind="bundle",
        policy_path=bundle / "policy.md", data_path=bundle / "data.yaml",
        frontmatter={"title": "Document Retention Policy", "owner": "CFO",
                     "foundational": True, "provides": ["classifications", "retention-schedule"]},
        body="# DRP\n", foundational=True,
        provides=("classifications", "retention-schedule"),
    )
    return policies_dir, policy


def test_url_resolves():
    assert reverse("foundational_edit", kwargs={"slug": "document-retention"}) == \
        "/policies/document-retention/foundational-edit/"


def test_requires_login(client):
    resp = client.get("/policies/document-retention/foundational-edit/")
    assert resp.status_code == 302
    assert resp.url.startswith("/login/")


def test_404_when_slug_missing(client, user, tmp_path):
    client.force_login(user)
    policies_dir, policy = _bundle_on_disk(tmp_path)
    with override_settings(POLICYCODEX_POLICY_REPO_URL="https://example.com/x.git",
                           POLICYCODEX_WORKING_COPY_ROOT=str(tmp_path)):
        with patch("core.views.Path.exists", return_value=True):
            with patch("core.views.BundleAwarePolicyReader") as MockReader:
                MockReader.return_value.read.return_value = iter([policy])
                resp = client.get("/policies/not-here/foundational-edit/")
    assert resp.status_code == 404


def test_non_foundational_redirects_to_flat_editor(client, user, tmp_path):
    client.force_login(user)
    flat = LogicalPolicy(
        slug="whistleblower", kind="flat", policy_path=Path("/tmp/p/whistleblower.md"),
        data_path=None, frontmatter={"title": "Whistleblower"}, body="b",
        foundational=False, provides=(),
    )
    with override_settings(POLICYCODEX_POLICY_REPO_URL="https://example.com/x.git",
                           POLICYCODEX_WORKING_COPY_ROOT=str(tmp_path)):
        with patch("core.views.Path.exists", return_value=True):
            with patch("core.views.BundleAwarePolicyReader") as MockReader:
                MockReader.return_value.read.return_value = iter([flat])
                resp = client.get("/policies/whistleblower/foundational-edit/")
    assert resp.status_code == 302
    assert resp.url == "/policies/whistleblower/edit/"


def test_get_renders_editable_tables_prepopulated(client, user, tmp_path):
    client.force_login(user)
    policies_dir, policy = _bundle_on_disk(tmp_path)
    with override_settings(POLICYCODEX_POLICY_REPO_URL="https://example.com/x.git",
                           POLICYCODEX_WORKING_COPY_ROOT=str(tmp_path)):
        with patch("core.views.Path.exists", return_value=True):
            with patch("core.views.BundleAwarePolicyReader") as MockReader:
                MockReader.return_value.read.return_value = iter([policy])
                resp = client.get("/policies/document-retention/foundational-edit/")
    assert resp.status_code == 200
    body = resp.content.decode()
    # Existing classification + retention values are present as input values.
    assert 'value="administrative"' in body
    assert 'value="Administrative"' in body
    assert 'value="Audited statements"' in body
    assert 'value="Permanent"' in body
    # Editable form scaffolding + the management forms for both formsets.
    assert "csrfmiddlewaretoken" in body
    assert 'name="cls-TOTAL_FORMS"' in body
    assert 'name="ret-TOTAL_FORMS"' in body
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `ai/venv/bin/python -m pytest core/tests/test_foundational_edit.py -q`
Expected: FAIL — `NoReverseMatch: 'foundational_edit'` (URL not registered yet).

- [ ] **Step 3: Register the URL**

In `core/urls.py`, add inside `urlpatterns` (after the `policy_edit` line):

```python
    path(
        "policies/<slug:slug>/foundational-edit/",
        views.foundational_edit,
        name="foundational_edit",
    ),
```

- [ ] **Step 4: Add the view imports**

In `core/views.py`, extend the AI import (currently `from ai.taxonomy_loader import load_foundational_taxonomy`) with the emitter, and add the forms import. Add near the existing imports:

```python
from ai.retention_extract import RetentionExtractionError, build_data_yaml
from core.forms import (
    ClassificationFormSet,
    FoundationalEditMetaForm,
    RetentionRowFormSet,
)
```

(`PolicyEditForm` is already imported on line 17; keep it.)

- [ ] **Step 5: Implement the GET half of the view**

In `core/views.py`, add this view (place it after `policy_edit`, before `approve_pr`):

```python
def _classification_initial(data: dict) -> list[dict]:
    return [
        {"id": c.get("id", ""), "name": c.get("name", "")}
        for c in (data.get("classifications") or [])
    ]


def _retention_initial(data: dict) -> list[dict]:
    rows = []
    for r in (data.get("retention_schedule") or []):
        rows.append({
            "group": r.get("group", ""),
            "sub_group": r.get("sub_group", ""),
            "type": r.get("type", ""),
            "retention": r.get("retention", ""),
            "medium": r.get("medium", ""),
            "retained_at": r.get("retained_at", ""),
        })
    return rows


@login_required
def foundational_edit(request, slug):
    """Typed-table editor for a foundational bundle's data.yaml (APP-25).

    GET renders editable classification + retention-row tables prefilled
    from data.yaml. POST writes an edited data.yaml and opens a PR through
    the same gate flow as policy_edit. Non-foundational policies are sent to
    the flat editor; this view edits only foundational bundles.
    """
    policy = _find_policy(slug)
    if policy is None:
        raise Http404(f"Policy not found: {slug}")
    if not policy.foundational:
        # Wrong editor for a flat policy; send them to the standard form.
        return redirect("policy_edit", slug=slug)

    data = yaml.safe_load(policy.data_path.read_text(encoding="utf-8")) or {}

    if request.method == "POST":
        return _foundational_edit_post(request, slug, policy)

    cforms = ClassificationFormSet(
        initial=_classification_initial(data), prefix="cls"
    )
    rforms = RetentionRowFormSet(
        initial=_retention_initial(data), prefix="ret"
    )
    meta = FoundationalEditMetaForm()
    return render(request, "foundational_edit.html", {
        "policy": policy, "cforms": cforms, "rforms": rforms, "meta": meta,
    })
```

Add `import yaml` to the top of `core/views.py` if it is not already imported (it is not in the current file — add it with the stdlib/third-party imports).

`_foundational_edit_post` lands in Task 3. For Task 2's tests (GET/routing/redirect/404) it is not exercised, but the name must exist so the module imports. Add a temporary stub right below the view that Task 3 replaces:

```python
def _foundational_edit_post(request, slug, policy):
    raise NotImplementedError  # implemented in APP-25 Task 3
```

- [ ] **Step 6: Create the editor template**

Create `core/templates/foundational_edit.html`:

```html
{% extends "base.html" %}

{% block title %}Edit {{ policy.frontmatter.title|default:policy.slug }} | PolicyCodex{% endblock %}

{% block content %}
  <h2>Edit {{ policy.frontmatter.title|default:policy.slug }}</h2>
  <p>This is a foundational policy. Editing here opens a pull request that
     flows through Drafted &rarr; Reviewed &rarr; Published, just like every
     other policy change.</p>

  <form method="post">
    {% csrf_token %}

    <h3>Classifications</h3>
    {{ cforms.management_form }}
    <table class="typed-table classifications">
      <thead><tr><th>id</th><th>name</th><th>delete</th></tr></thead>
      <tbody>
        {% for f in cforms %}
          <tr>
            <td>{{ f.id }}{{ f.id.errors }}</td>
            <td>{{ f.name }}{{ f.name.errors }}</td>
            <td>{% if f.DELETE %}{{ f.DELETE }}{% endif %}</td>
          </tr>
        {% endfor %}
      </tbody>
    </table>

    <h3>Retention schedule</h3>
    {{ rforms.management_form }}
    <table class="typed-table retention">
      <thead><tr>
        <th>group</th><th>sub_group</th><th>type</th>
        <th>retention</th><th>medium</th><th>retained_at</th><th>delete</th>
      </tr></thead>
      <tbody>
        {% for f in rforms %}
          <tr>
            <td>{{ f.group }}{{ f.group.errors }}</td>
            <td>{{ f.sub_group }}</td>
            <td>{{ f.type }}{{ f.type.errors }}</td>
            <td>{{ f.retention }}{{ f.retention.errors }}</td>
            <td>{{ f.medium }}</td>
            <td>{{ f.retained_at }}</td>
            <td>{% if f.DELETE %}{{ f.DELETE }}{% endif %}</td>
          </tr>
        {% endfor %}
      </tbody>
    </table>

    <p>{{ meta.summary.label_tag }} {{ meta.summary }}</p>
    {% if error %}<p class="form-error">{{ error }}</p>{% endif %}

    <button type="submit">Open PR</button>
    <a href="{% url 'catalog' %}">Cancel</a>
  </form>
{% endblock %}
```

- [ ] **Step 7: Link the catalog's foundational row to the editor**

In `core/templates/catalog.html`, replace the static foundational message (lines 63-64) so the foundational branch links to the editor:

Change:
```html
          {% if row.policy.foundational %}
            <span class="foundational-gate">Foundational policy. Edit through the typed-table editor.</span>
          {% else %}
```
to:
```html
          {% if row.policy.foundational %}
            <a class="action-edit-foundational" href="{% url 'foundational_edit' slug=row.policy.slug %}">Edit (typed table)</a>
          {% else %}
```

- [ ] **Step 8: Run the Task-2 tests to verify they pass**

Run: `ai/venv/bin/python -m pytest core/tests/test_foundational_edit.py -q`
Expected: routing, login, 404, redirect, and GET-render tests PASS.

- [ ] **Step 9: Run the catalog tests for regressions**

Run: `ai/venv/bin/python -m pytest core/tests/test_catalog.py -q`
Expected: PASS. If a catalog test asserted the old static "Edit through the typed-table editor" string, update that assertion to the new link text "Edit (typed table)" — record the change here.

- [ ] **Step 10: Commit**

```bash
git add core/urls.py core/views.py core/templates/foundational_edit.html \
        core/templates/catalog.html core/tests/test_foundational_edit.py
git commit -m "feat(core): foundational typed-table editor view + catalog link, GET (APP-25)"
```

---

## Task 3: POST write-back + gate sequence

**Files:**
- Modify: `core/views.py`
- Test: `core/tests/test_foundational_edit.py`

- [ ] **Step 1: Write the failing POST tests**

Append to `core/tests/test_foundational_edit.py`:

```python
def _formset_post(prefix, rows, extra=None):
    """Build management-form + per-row POST data for a formset.

    rows: list of dicts (existing/edited rows, in order). A row dict may
    include "DELETE": "on". `extra`: an optional dict for the trailing
    add-row (omit to leave it blank).
    """
    total = len(rows) + 1  # one extra add-row form
    data = {
        f"{prefix}-TOTAL_FORMS": str(total),
        f"{prefix}-INITIAL_FORMS": str(len(rows)),
        f"{prefix}-MIN_NUM_FORMS": "0",
        f"{prefix}-MAX_NUM_FORMS": "1000",
    }
    for i, row in enumerate(rows):
        for k, v in row.items():
            data[f"{prefix}-{i}-{k}"] = v
    extra = extra or {}
    for k, v in extra.items():
        data[f"{prefix}-{len(rows)}-{k}"] = v
    return data


def _post_payload(*, classifications, retention, add_classification=None, summary="msg"):
    data = {}
    data.update(_formset_post("cls", classifications, extra=add_classification))
    data.update(_formset_post("ret", retention))
    data["summary"] = summary
    return data


def test_post_valid_writes_data_yaml_and_opens_pr(client, user, tmp_path):
    client.force_login(user)
    policies_dir, policy = _bundle_on_disk(tmp_path)
    fake_pr = {"pr_number": 31, "url": "https://github.com/x/y/pull/31", "state": "open"}
    payload = _post_payload(
        classifications=[
            {"id": "administrative", "name": "Administrative Records"},  # renamed
            {"id": "financial", "name": "Financial"},
        ],
        add_classification={"id": "legal", "name": "Legal"},  # added
        retention=[
            {"group": "Administrative Records", "type": "General correspondence",
             "retention": "5 years"},  # retention edited 3->5 years
            {"group": "Financial Records", "type": "Audited statements",
             "retention": "Permanent"},
        ],
    )
    with override_settings(
        POLICYCODEX_POLICY_REPO_URL="https://github.com/example/diocese-policies.git",
        POLICYCODEX_POLICY_BRANCH="main",
        POLICYCODEX_WORKING_COPY_ROOT=str(tmp_path),
    ):
        with patch("core.views.Path.exists", return_value=True):
            with patch("core.views.BundleAwarePolicyReader") as MockReader:
                MockReader.return_value.read.return_value = iter([policy])
                with patch("core.views.GitHubProvider") as MockProvider:
                    instance = MockProvider.return_value
                    instance.open_pr.return_value = fake_pr
                    resp = client.post(
                        "/policies/document-retention/foundational-edit/",
                        data=payload, follow=True,
                    )
    assert resp.status_code == 200
    # data.yaml on disk reflects the edits.
    written = yaml.safe_load(policy.data_path.read_text())
    assert [c["id"] for c in written["classifications"]] == ["administrative", "financial", "legal"]
    assert written["classifications"][0]["name"] == "Administrative Records"
    assert written["retention_schedule"][0]["retention"] == "5 years"
    # The four GitHub operations ran, committing data.yaml.
    instance.branch.assert_called_once()
    assert instance.branch.call_args[0][0].startswith("policycodex/edit-document-retention-")
    commit_call = instance.commit.call_args
    files = commit_call.kwargs.get("files", commit_call.args[1] if len(commit_call.args) > 1 else None)
    assert files == [policy.data_path]
    instance.push.assert_called_once()
    instance.open_pr.assert_called_once()
    # Success page shows the PR url.
    assert "https://github.com/x/y/pull/31" in resp.content.decode()
    # Call order matches the proven sequence.
    method_names = [c[0] for c in MockProvider.return_value.mock_calls]
    assert method_names.index("branch") < method_names.index("commit") \
        < method_names.index("push") < method_names.index("open_pr")


def test_post_delete_row_drops_it_from_data_yaml(client, user, tmp_path):
    client.force_login(user)
    policies_dir, policy = _bundle_on_disk(tmp_path)
    payload = _post_payload(
        classifications=[
            {"id": "administrative", "name": "Administrative"},
            {"id": "financial", "name": "Financial"},
        ],
        retention=[
            {"group": "Administrative Records", "type": "General correspondence",
             "retention": "3 years"},
            {"group": "Financial Records", "type": "Audited statements",
             "retention": "Permanent", "DELETE": "on"},  # delete this row
        ],
    )
    with override_settings(
        POLICYCODEX_POLICY_REPO_URL="https://github.com/example/diocese-policies.git",
        POLICYCODEX_WORKING_COPY_ROOT=str(tmp_path),
    ):
        with patch("core.views.Path.exists", return_value=True):
            with patch("core.views.BundleAwarePolicyReader") as MockReader:
                MockReader.return_value.read.return_value = iter([policy])
                with patch("core.views.GitHubProvider") as MockProvider:
                    MockProvider.return_value.open_pr.return_value = {
                        "pr_number": 1, "url": "u", "state": "open"}
                    client.post(
                        "/policies/document-retention/foundational-edit/",
                        data=payload,
                    )
    written = yaml.safe_load(policy.data_path.read_text())
    types = [r["type"] for r in written["retention_schedule"]]
    assert types == ["General correspondence"]  # the deleted row is gone


def test_post_invalid_formset_rerenders_without_calling_provider(client, user, tmp_path):
    client.force_login(user)
    policies_dir, policy = _bundle_on_disk(tmp_path)
    # Blank required `retention` on an existing row -> invalid.
    payload = _post_payload(
        classifications=[{"id": "administrative", "name": "Administrative"}],
        retention=[{"group": "G", "type": "T", "retention": ""}],
    )
    with override_settings(
        POLICYCODEX_POLICY_REPO_URL="https://github.com/example/diocese-policies.git",
        POLICYCODEX_WORKING_COPY_ROOT=str(tmp_path),
    ):
        with patch("core.views.Path.exists", return_value=True):
            with patch("core.views.BundleAwarePolicyReader") as MockReader:
                MockReader.return_value.read.return_value = iter([policy])
                with patch("core.views.GitHubProvider") as MockProvider:
                    resp = client.post(
                        "/policies/document-retention/foundational-edit/",
                        data=payload,
                    )
                    MockProvider.return_value.branch.assert_not_called()
    assert resp.status_code == 200
    assert "Open PR" in resp.content.decode()  # re-rendered editor


def test_post_provider_failure_rerenders_with_error(client, user, tmp_path):
    client.force_login(user)
    policies_dir, policy = _bundle_on_disk(tmp_path)
    payload = _post_payload(
        classifications=[{"id": "administrative", "name": "Administrative"}],
        retention=[{"group": "G", "type": "T", "retention": "3 years"}],
    )
    with override_settings(
        POLICYCODEX_POLICY_REPO_URL="https://github.com/example/diocese-policies.git",
        POLICYCODEX_WORKING_COPY_ROOT=str(tmp_path),
    ):
        with patch("core.views.Path.exists", return_value=True):
            with patch("core.views.BundleAwarePolicyReader") as MockReader:
                MockReader.return_value.read.return_value = iter([policy])
                with patch("core.views.GitHubProvider") as MockProvider:
                    instance = MockProvider.return_value
                    instance.branch.side_effect = RuntimeError("git branch failed")
                    resp = client.post(
                        "/policies/document-retention/foundational-edit/",
                        data=payload,
                    )
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "Open PR" in body  # editor re-rendered, not a 500
    assert "couldn't" in body.lower() or "failed" in body.lower() or "error" in body.lower()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `ai/venv/bin/python -m pytest core/tests/test_foundational_edit.py -q -k post`
Expected: FAIL — the POST handler currently raises `NotImplementedError`.

- [ ] **Step 3: Implement the POST handler**

In `core/views.py`, replace the `_foundational_edit_post` stub from Task 2 with:

```python
def _foundational_edit_post(request, slug, policy):
    cforms = ClassificationFormSet(request.POST, prefix="cls")
    rforms = RetentionRowFormSet(request.POST, prefix="ret")
    meta = FoundationalEditMetaForm(request.POST)

    def _render(error=None):
        return render(request, "foundational_edit.html", {
            "policy": policy, "cforms": cforms, "rforms": rforms,
            "meta": meta, "error": error,
        })

    if not (cforms.is_valid() and rforms.is_valid() and meta.is_valid()):
        return _render()

    classifications = [
        {"id": f.cleaned_data["id"], "name": f.cleaned_data["name"]}
        for f in cforms
        if f.cleaned_data and not f.cleaned_data.get("DELETE")
    ]
    retention_schedule = [
        {
            "group": f.cleaned_data["group"],
            "sub_group": f.cleaned_data.get("sub_group", ""),
            "type": f.cleaned_data["type"],
            "retention": f.cleaned_data["retention"],
            "medium": f.cleaned_data.get("medium", ""),
            "retained_at": f.cleaned_data.get("retained_at", ""),
        }
        for f in rforms
        if f.cleaned_data and not f.cleaned_data.get("DELETE")
    ]
    bundle = {"classifications": classifications, "retention_schedule": retention_schedule}

    # build_data_yaml validates required fields + drops blank optionals (DRY
    # with the APP-15 bootstrap emitter). A malformed bundle re-renders.
    try:
        data_yaml_text = build_data_yaml(bundle)
    except RetentionExtractionError as exc:
        return _render(error=f"Could not save: {exc}")

    # Write the edited data.yaml in the working copy.
    policy.data_path.write_text(data_yaml_text, encoding="utf-8")

    # Same four-operation gate sequence as policy_edit, committing data.yaml.
    config = load_working_copy_config()
    working_dir = config.working_dir
    provider = GitHubProvider()
    author_name, author_email = get_git_author(request.user)
    branch_name = _make_branch_name(slug)
    summary = (meta.cleaned_data.get("summary") or "").strip()
    commit_message = summary or f"Update {slug} classifications and retention schedule"

    try:
        provider.branch(branch_name, working_dir)
        provider.commit(
            message=commit_message,
            files=[policy.data_path],
            author_name=author_name,
            author_email=author_email,
            working_dir=working_dir,
        )
        provider.push(branch_name, working_dir)
        pr_title = f"Edit policies/{slug}: {commit_message}"
        pr_body = (
            f"Opened by PolicyCodex on behalf of {request.user.username}.\n"
            f"\n"
            f"Foundational policy: policies/{slug} (data.yaml)\n"
            f"Author: {author_name} <{author_email}>\n"
        )
        if summary:
            pr_body += f"\n{summary}\n"
        pr = provider.open_pr(
            title=pr_title,
            body=pr_body,
            head_branch=branch_name,
            base_branch=config.branch,
            working_dir=working_dir,
        )
    except (RuntimeError, ValueError) as exc:
        logger.error("APP-25 provider failure on slug=%s: %s", slug, exc)
        messages.error(
            request,
            "Couldn't open the pull request. The change is saved locally; "
            "ask your administrator to retry from the server logs.",
        )
        return _render()

    return render(request, "policy_edit_success.html", {"policy": policy, "pr": pr})
```

This reuses `load_working_copy_config`, `GitHubProvider`, `get_git_author`, `_make_branch_name`, and `messages` — all already imported in `core/views.py`.

- [ ] **Step 4: Run the POST tests to verify they pass**

Run: `ai/venv/bin/python -m pytest core/tests/test_foundational_edit.py -q -k post`
Expected: the 4 POST tests PASS.

- [ ] **Step 5: Run the whole foundational-editor test module**

Run: `ai/venv/bin/python -m pytest core/tests/test_foundational_edit.py core/tests/test_foundational_edit_forms.py -q`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add core/views.py core/tests/test_foundational_edit.py
git commit -m "feat(core): foundational editor POST writes data.yaml + opens PR through the gate (APP-25)"
```

---

## Task 4: Full-suite verification

- [ ] **Step 1: Run the gate-flow neighbors to confirm no regression**

Run: `ai/venv/bin/python -m pytest core -q`
Expected: PASS, including `test_catalog.py`, `test_approve_pr.py`, `test_publish_policy.py` (the approve/publish views are unchanged and must still pass against the new foundational-edit branch convention).

- [ ] **Step 2: Run the entire suite**

Run: `ai/venv/bin/python -m pytest -q`
Expected: green. Any failure outside this plan's files must be investigated, not papered over (superpowers:verification-before-completion).

- [ ] **Step 3: Manual demo dry-run (record result, do not claim success without it)**

Because this is the DISC demo's centerpiece, exercise it in a browser against a test repo before calling it done: open the catalog, click "Edit (typed table)" on the document-retention row, rename a classification, change one retention row's value, submit, confirm a PR opens, approve it (Approve a PR box), then Publish. Confirm the gate badge moves Drafted → Reviewed → Published and the handbook rebuild fires. If you cannot run the full GitHub round-trip locally, say so explicitly rather than implying it passed.

---

## Self-Review (completed during planning)

- **Spec coverage:** demo-slice scope — edit classifications (Task 1 formset + Task 2/3 view), add/edit/delete retention rows (Task 1 `can_delete` + Task 3 add/delete tests), write-back to `data.yaml` (Task 3, via reused `build_data_yaml`), PR through Drafted/Reviewed/Published (Task 3 reuses the proven 4-op sequence; `approve_pr`/`publish_policy` unchanged and covered by Task 4), reachable from the catalog (Task 2 link). Post-DISC hardening (APP-23 reuse, large-schedule pagination, soft-delete semantics, concurrency) is explicitly OUT and listed in the header.
- **Placeholder scan:** every code step is complete. The one intentional interim stub (`_foundational_edit_post` raising `NotImplementedError` in Task 2) is replaced wholesale in Task 3 Step 3 and is called out as interim.
- **Type consistency:** `build_data_yaml(bundle)` / `RetentionExtractionError` match the APP-15 plan's signatures; `_find_policy`, `_make_branch_name`, `get_git_author`, `GitHubProvider`, `load_working_copy_config`, and the `policy_edit_success.html` context (`policy`, `pr`) match `core/views.py` exactly; formset prefixes `cls` / `ret` are identical across the template, view, and tests.
- **Cross-plan dependency:** flagged in the header — this plan must land after APP-15 Tasks 1–2 (which create `ai/retention_extract.py`).
```
