"""File-content extractors for the ingest pipeline.

Public surface:
    extract(path) -> str            top-level dispatcher
    Extractor                       ABC for new format handlers
    UnsupportedFormatError          raised for unknown file extensions
    PdfExtractor, DocxExtractor, TextExtractor

Dispatch is keyed on the file's lowercase suffix. Adding a new format
means writing a new Extractor subclass and registering it in
_EXTRACTORS below.
"""
from __future__ import annotations

from pathlib import Path

from .base import Extractor, UnsupportedFormatError
from .docx import DocxExtractor
from .pdf import PdfExtractor
from .text import TextExtractor

__all__ = [
    "extract",
    "Extractor",
    "UnsupportedFormatError",
    "PdfExtractor",
    "DocxExtractor",
    "TextExtractor",
]


_EXTRACTORS: tuple[Extractor, ...] = (
    PdfExtractor(),
    DocxExtractor(),
    TextExtractor(),
)

_BY_EXTENSION: dict[str, Extractor] = {
    ext: extractor for extractor in _EXTRACTORS for ext in extractor.extensions
}


def extract(path: Path) -> str:
    """Extract plain text from `path`, dispatching by file extension.

    Raises:
        FileNotFoundError: if `path` does not exist (message names the path).
        UnsupportedFormatError: if no extractor handles `path.suffix`.
    """
    path = Path(path)
    suffix = path.suffix.lower()
    extractor = _BY_EXTENSION.get(suffix)
    if extractor is None:
        supported = sorted(_BY_EXTENSION)
        raise UnsupportedFormatError(
            f"No extractor for suffix {suffix!r} (path: {path}). "
            f"Supported: {', '.join(supported)}"
        )
    if not path.exists():
        raise FileNotFoundError(f"File does not exist: {path}")
    return extractor.extract(path)
