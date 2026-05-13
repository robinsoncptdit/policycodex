"""DOCX extractor (python-docx-based; lifted from spike/extract.py)."""
from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from .base import Extractor


class DocxExtractor(Extractor):
    """Extract text from a .docx file using python-docx."""

    extensions: ClassVar[tuple[str, ...]] = (".docx",)

    def extract(self, path: Path) -> str:
        import docx

        document = docx.Document(str(path))
        return "\n".join(p.text for p in document.paragraphs)
