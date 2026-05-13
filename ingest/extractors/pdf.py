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
