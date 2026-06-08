"""PDF extractor (pypdf-based; lifted from spike/extract.py)."""
from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from .base import Extractor


class PdfExtractor(Extractor):
    """Extract text from a .pdf file using pypdf."""

    extensions: ClassVar[tuple[str, ...]] = (".pdf",)

    def extract(self, path: Path) -> str:
        import pypdf

        reader = pypdf.PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)


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
