# APP-30 Screen-7 Image-Only-PDF Guard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Onboarding screen 7 detects a scanned / image-only retention PDF (empty text extraction) and blocks with a clear warning, instead of silently running the AI on empty text and committing empty classifications.

**Architecture:** Promote the image-only detection logic that currently lives as a test-only helper (`_empty_extraction_is_explained` in `ingest/tests/test_corpus_integration.py`) into a reusable production function `pdf_has_embedded_images` in `ingest/extractors/pdf.py`. The screen-7 handler (`app/onboarding/retention_policy.py`) calls it in the `action == "extract"` branch: if the extracted text is empty, it picks a scan-specific or generic "no readable text" message, removes the staged upload, and re-renders the upload form. The expensive AI call (`extract_retention_bundle`) is never reached for an empty document. Detect-and-warn only; OCR stays out of scope (INGEST-08 covers the ingest path).

**Tech Stack:** Python 3.14, Django, pypdf, pytest / pytest-django. Test interpreter: `ai/venv/bin/python` (no root venv exists; system Python lacks pytest).

---

## File Structure

- `ingest/extractors/pdf.py` — gains a module-level `pdf_has_embedded_images(path)` function alongside the existing `PdfExtractor` class. PDF inspection lives next to PDF extraction.
- `ingest/extractors/__init__.py` — re-exports `pdf_has_embedded_images` so callers import it from the package surface (`from ingest.extractors import pdf_has_embedded_images`).
- `ingest/tests/test_extractors.py` — new unit tests for `pdf_has_embedded_images` (reuses the existing `tiny_pdf` fixture and pypdf-synthesis pattern; no binary fixtures).
- `ingest/tests/test_corpus_integration.py` — refactored to import and use `pdf_has_embedded_images`, deleting its local `_empty_extraction_is_explained` helper (single source of truth, DRY).
- `app/onboarding/retention_policy.py` — the `action == "extract"` branch gains the empty-extraction guard before the AI call.
- `app/onboarding/tests/test_onboarding_views.py` — new tests for the guard (scanned-PDF block, empty-text block, AI-not-called).

No new dependencies. No new files.

---

### Task 1: Promote the image-only detection helper to production

**Files:**
- Modify: `ingest/extractors/pdf.py`
- Modify: `ingest/extractors/__init__.py`
- Test: `ingest/tests/test_extractors.py`

- [ ] **Step 1: Write the failing tests**

Append to `ingest/tests/test_extractors.py` (the `tiny_pdf` fixture already exists in this file and builds a text-only one-page PDF):

```python
# ---------- pdf_has_embedded_images (APP-30) ----------------------------------


def test_pdf_has_embedded_images_false_for_non_pdf(tmp_path: Path):
    p = tmp_path / "notes.txt"
    p.write_text("plain text", encoding="utf-8")
    from ingest.extractors import pdf_has_embedded_images

    assert pdf_has_embedded_images(p) is False


def test_pdf_has_embedded_images_false_for_unreadable_bytes(tmp_path: Path):
    """Garbage that pypdf cannot parse is not a scan; the helper returns False
    rather than raising, so the caller can fall through to its generic error."""
    p = tmp_path / "garbage.pdf"
    p.write_bytes(b"this is not a pdf at all")
    from ingest.extractors import pdf_has_embedded_images

    assert pdf_has_embedded_images(p) is False


def test_pdf_has_embedded_images_false_for_text_only_pdf(tiny_pdf: Path):
    """A real, parseable, text-only PDF has pages but no embedded images."""
    from ingest.extractors import pdf_has_embedded_images

    assert pdf_has_embedded_images(tiny_pdf) is False


def test_pdf_has_embedded_images_true_when_a_page_has_images(tmp_path: Path, monkeypatch):
    """A scan presents as one-or-more pages each carrying image XObjects.
    Faking the reader keeps this deterministic without a binary image fixture;
    the real image-only PDF path is exercised by the corpus integration test."""
    import pypdf
    from ingest.extractors import pdf_has_embedded_images

    p = tmp_path / "scan.pdf"
    p.write_bytes(b"%PDF-1.4 placeholder")

    class _FakePage:
        images = [object()]

    class _FakeReader:
        pages = [_FakePage()]

    monkeypatch.setattr(pypdf, "PdfReader", lambda *a, **k: _FakeReader())
    assert pdf_has_embedded_images(p) is True


def test_pdf_has_embedded_images_false_when_pages_have_no_images(tmp_path: Path, monkeypatch):
    import pypdf
    from ingest.extractors import pdf_has_embedded_images

    p = tmp_path / "scan.pdf"
    p.write_bytes(b"%PDF-1.4 placeholder")

    class _FakePage:
        images = []

    class _FakeReader:
        pages = [_FakePage()]

    monkeypatch.setattr(pypdf, "PdfReader", lambda *a, **k: _FakeReader())
    assert pdf_has_embedded_images(p) is False


def test_pdf_has_embedded_images_false_for_pdf_with_no_pages(tmp_path: Path, monkeypatch):
    import pypdf
    from ingest.extractors import pdf_has_embedded_images

    p = tmp_path / "empty.pdf"
    p.write_bytes(b"%PDF-1.4 placeholder")

    class _FakeReader:
        pages = []

    monkeypatch.setattr(pypdf, "PdfReader", lambda *a, **k: _FakeReader())
    assert pdf_has_embedded_images(p) is False
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `ai/venv/bin/python -m pytest ingest/tests/test_extractors.py -k pdf_has_embedded_images -v`
Expected: FAIL with `ImportError: cannot import name 'pdf_has_embedded_images' from 'ingest.extractors'`

- [ ] **Step 3: Implement the function in `ingest/extractors/pdf.py`**

Append to `ingest/extractors/pdf.py` (after the `PdfExtractor` class):

```python
def pdf_has_embedded_images(path: Path) -> bool:
    """Return True if `path` is a PDF that pypdf can open and at least one of
    its pages carries an embedded image.

    Callers use this to explain an empty text extraction: a scan (image with no
    text layer) extracts to empty text but reports embedded images here. The
    function never raises. A non-PDF suffix, an unparseable file, or a PDF with
    no pages all return False so the caller can fall through to a generic
    "no readable text" message. The text-layer extractor cannot read a scan;
    OCR is out of scope for v0.1.
    """
    if Path(path).suffix.lower() != ".pdf":
        return False
    import pypdf

    try:
        reader = pypdf.PdfReader(str(path))
    except Exception:  # noqa: BLE001 - any parse failure means "not a scan we can flag"
        return False
    if not reader.pages:
        return False
    return any(len(getattr(page, "images", [])) for page in reader.pages)
```

- [ ] **Step 4: Export it from `ingest/extractors/__init__.py`**

In `ingest/extractors/__init__.py`, change the pdf import line:

```python
from .pdf import PdfExtractor
```

to:

```python
from .pdf import PdfExtractor, pdf_has_embedded_images
```

and add `"pdf_has_embedded_images"` to the `__all__` list:

```python
__all__ = [
    "extract",
    "Extractor",
    "UnsupportedFormatError",
    "PdfExtractor",
    "DocxExtractor",
    "TextExtractor",
    "pdf_has_embedded_images",
]
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `ai/venv/bin/python -m pytest ingest/tests/test_extractors.py -k pdf_has_embedded_images -v`
Expected: PASS (6 tests)

- [ ] **Step 6: Commit**

```bash
git add ingest/extractors/pdf.py ingest/extractors/__init__.py ingest/tests/test_extractors.py
git commit -m "feat(app-30): promote pdf_has_embedded_images to ingest.extractors"
```

---

### Task 2: Point the corpus integration test at the promoted helper (DRY)

**Files:**
- Modify: `ingest/tests/test_corpus_integration.py`

This removes the duplicated detection logic so there is a single source of truth. The test's behavior is unchanged; it must stay green (and still skip without `POLICYCODEX_CORPUS_DIR`).

- [ ] **Step 1: Add the import**

In `ingest/tests/test_corpus_integration.py`, change:

```python
from ingest.extractors import extract
```

to:

```python
from ingest.extractors import extract, pdf_has_embedded_images
```

- [ ] **Step 2: Delete the local helper**

Remove the entire `_empty_extraction_is_explained` function (the `def _empty_extraction_is_explained(path: Path) -> bool:` block and its docstring/body, including its inner `import pypdf`).

- [ ] **Step 3: Update the call site**

In `test_every_corpus_file_extracts_text_or_is_image_only`, change:

```python
        if not _empty_extraction_is_explained(p):
            unexplained_empties.append(str(p))
```

to:

```python
        if not pdf_has_embedded_images(p):
            unexplained_empties.append(str(p))
```

- [ ] **Step 4: Verify the module imports and the suite is green**

Run: `ai/venv/bin/python -m pytest ingest/tests/test_corpus_integration.py -v`
Expected: 4 tests SKIPPED (no `POLICYCODEX_CORPUS_DIR` in CI), 0 errors. The collection must succeed (no import error, no reference to the deleted helper).

Run: `ai/venv/bin/python -m pytest ingest/ -q`
Expected: PASS, no failures.

- [ ] **Step 5: Commit**

```bash
git add ingest/tests/test_corpus_integration.py
git commit -m "refactor(app-30): use ingest.extractors.pdf_has_embedded_images in corpus test"
```

---

### Task 3: Add the empty-extraction guard to screen 7

**Files:**
- Modify: `app/onboarding/retention_policy.py`
- Test: `app/onboarding/tests/test_onboarding_views.py`

- [ ] **Step 1: Write the failing tests**

Append to `app/onboarding/tests/test_onboarding_views.py` (the `working_copy` fixture, `FAKE_BUNDLE`, `_advance_to_retention_policy`, and `SimpleUploadedFile` import already exist in this file):

```python
def test_screen7_extract_blocks_scanned_image_only_pdf(client, user, working_copy, monkeypatch):
    """A scanned/image-only PDF extracts to empty text. The wizard must warn and
    stay on the upload form, and must NOT call the AI (which would otherwise
    produce empty classifications and let onboarding proceed)."""
    from app.onboarding import retention_policy as rp

    monkeypatch.setattr(rp, "ClaudeProvider", lambda *a, **k: object())
    monkeypatch.setattr(rp, "extract_text", lambda path: "")
    monkeypatch.setattr(rp, "pdf_has_embedded_images", lambda path: True)
    ai_calls = []
    monkeypatch.setattr(
        rp, "extract_retention_bundle",
        lambda provider, text: ai_calls.append(text) or FAKE_BUNDLE,
    )

    client.force_login(user)
    _advance_to_retention_policy(client)
    upload = SimpleUploadedFile("scan.pdf", b"%PDF-1.4", content_type="application/pdf")
    resp = client.post("/onboarding/retention-policy/", {"action": "extract", "pdf_file": upload})

    assert resp.status_code == 200
    body = resp.content.decode()
    assert 'name="pdf_file"' in body          # back on the upload form, not review
    assert "Administrative" not in body        # no draft classifications rendered
    assert "scanned pdf" in body.lower()       # scan-specific guidance
    assert ai_calls == []                       # the AI extraction was never called


def test_screen7_extract_blocks_empty_text_pdf(client, user, working_copy, monkeypatch):
    """An empty/blank PDF that is not image-only also blocks, with a generic
    'no readable text' message rather than the scan-specific one."""
    from app.onboarding import retention_policy as rp

    monkeypatch.setattr(rp, "ClaudeProvider", lambda *a, **k: object())
    monkeypatch.setattr(rp, "extract_text", lambda path: "   \n  ")
    monkeypatch.setattr(rp, "pdf_has_embedded_images", lambda path: False)
    ai_calls = []
    monkeypatch.setattr(
        rp, "extract_retention_bundle",
        lambda provider, text: ai_calls.append(text) or FAKE_BUNDLE,
    )

    client.force_login(user)
    _advance_to_retention_policy(client)
    upload = SimpleUploadedFile("blank.pdf", b"%PDF-1.4", content_type="application/pdf")
    resp = client.post("/onboarding/retention-policy/", {"action": "extract", "pdf_file": upload})

    assert resp.status_code == 200
    body = resp.content.decode()
    assert 'name="pdf_file"' in body
    assert "readable text" in body.lower()
    assert ai_calls == []
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `ai/venv/bin/python -m pytest app/onboarding/tests/test_onboarding_views.py -k "blocks_scanned or blocks_empty" -v`
Expected: FAIL. The first fails on `AttributeError: ... has no attribute 'pdf_has_embedded_images'` (the name is not imported into the handler module yet) or, if that line is reached differently, on the review screen rendering "Administrative" and `ai_calls` being non-empty.

- [ ] **Step 3: Add the import to the handler**

In `app/onboarding/retention_policy.py`, the existing line 33 is:

```python
from ingest.extractors import extract as extract_text
```

Add a line directly after it:

```python
from ingest.extractors import extract as extract_text
from ingest.extractors import pdf_has_embedded_images
```

- [ ] **Step 4: Insert the guard in the `action == "extract"` branch**

In `app/onboarding/retention_policy.py`, replace this block:

```python
        try:
            text = extract_text(source_pdf)
            bundle = extract_retention_bundle(ClaudeProvider(), text)
            data_yaml_text = build_data_yaml(bundle)
        except RetentionExtractionError as exc:
```

with:

```python
        try:
            text = extract_text(source_pdf)
            if not text.strip():
                if pdf_has_embedded_images(source_pdf):
                    guard_error = (
                        "This looks like a scanned PDF (an image with no text "
                        "layer), so there is nothing to extract automatically. "
                        "Upload a text-based PDF of the policy and try again."
                    )
                else:
                    guard_error = (
                        "We could not find any readable text in that document. "
                        "Check that it is a text-based PDF and try again."
                    )
                shutil.rmtree(staging, ignore_errors=True)
                return _render_upload(request, target, state, error=guard_error)
            bundle = extract_retention_bundle(ClaudeProvider(), text)
            data_yaml_text = build_data_yaml(bundle)
        except RetentionExtractionError as exc:
```

Note: returning before `extract_retention_bundle` is what keeps the AI from being called on empty text. `shutil` is already imported at the top of the file. The messages avoid em dashes and contractions (apostrophe-free) per project style and to keep them matchable after HTML escaping.

- [ ] **Step 5: Run the new tests to verify they pass**

Run: `ai/venv/bin/python -m pytest app/onboarding/tests/test_onboarding_views.py -k "blocks_scanned or blocks_empty" -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Run the full onboarding suite to check for regressions**

Run: `ai/venv/bin/python -m pytest app/onboarding/ -q`
Expected: PASS. The existing happy-path tests (`test_screen7_extract_shows_readonly_review`, `test_screen7_accept_*`) still pass because `stub_extraction` makes `extract_text` return `"FAKE PDF TEXT"` (non-empty), so the guard is skipped.

- [ ] **Step 7: Commit**

```bash
git add app/onboarding/retention_policy.py app/onboarding/tests/test_onboarding_views.py
git commit -m "feat(app-30): block scanned/image-only PDFs on onboarding screen 7"
```

---

### Task 4: Full-suite verification and docs close-out (controller)

**Files:**
- Modify: `PolicyWonk-v0.1-Tickets.md`
- Modify: `internal/PolicyWonk-Daily-Log.md`

This task is run by the controller after the implementation tasks pass review. It is not TDD; it verifies the whole suite and records the result.

- [ ] **Step 1: Run the whole suite**

Run: `ai/venv/bin/python -m pytest -q`
Expected: PASS, no failures (the 4 corpus-gated tests skip without `POLICYCODEX_CORPUS_DIR`). Note the new total (Task 1 adds 6, Task 3 adds 2; Task 2 changes none).

- [ ] **Step 2: Mark APP-30 resolved in `PolicyWonk-v0.1-Tickets.md`**

Prepend a bold `**Resolved 2026-06-08 (<commit-shas>): ...**` note to the APP-30 row body, summarizing: promoted `pdf_has_embedded_images` to `ingest/extractors`, refactored the corpus test onto it, added the screen-7 empty-extraction guard (scan-specific + generic message, AI never called on empty text), suite delta.

- [ ] **Step 3: Append a Daily Log entry**

Append a dated entry to `internal/PolicyWonk-Daily-Log.md` recording the ticket, the design (promote-then-consume, guard-before-AI), the two message branches, and the final suite count.

- [ ] **Step 4: Commit the docs**

```bash
git add PolicyWonk-v0.1-Tickets.md internal/PolicyWonk-Daily-Log.md
git commit -m "docs(app-30): mark APP-30 done, log screen-7 image-only guard"
```

---

## Notes for the implementer

- **Run tests with `ai/venv/bin/python -m pytest`** from the repo root. There is no root virtualenv; the system Python lacks pytest.
- **Ship generic.** No diocese-specific strings in any shipping file (`app/`, `core/`, `ai/`, `ingest/`). Say "the policy" / "your", never "PT" or a diocese name. The `tests/test_generic_ship.py` guard will fail the build otherwise.
- **Scope is detect-and-warn only.** Do not add OCR, do not try to extract text from images, do not add a new dependency. INGEST-08 owns the ingest-path equivalent post-freeze.
- **Why block before the AI call:** running `extract_retention_bundle` on empty text wastes an LLM call and yields empty classifications that would scaffold a broken foundational bundle and let onboarding proceed silently. The early `return` is the entire point of the ticket.
