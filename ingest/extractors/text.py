"""Plain-text extractor for .md and .txt files."""
from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from .base import Extractor


class TextExtractor(Extractor):
    """Extract text from .md and .txt files via UTF-8 read_text.

    Uses `errors="replace"` so a stray non-UTF-8 byte does not crash
    ingest; the substitution character is harmless for the LLM
    extraction pass downstream.
    """

    extensions: ClassVar[tuple[str, ...]] = (".md", ".txt")

    def extract(self, path: Path) -> str:
        return path.read_text(encoding="utf-8", errors="replace")
