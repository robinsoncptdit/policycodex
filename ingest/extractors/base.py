"""Extractor abstract base class and shared error types."""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar


class UnsupportedFormatError(ValueError):
    """Raised when no registered Extractor handles a file's suffix."""


class Extractor(ABC):
    """Pull plain text out of a single file on disk.

    Subclasses declare the extensions they handle via the `extensions`
    class attribute (lowercase, including the leading dot). The
    dispatcher in `ingest.extractors.__init__` uses that attribute to
    route a path to the right extractor.
    """

    extensions: ClassVar[tuple[str, ...]]

    @abstractmethod
    def extract(self, path: Path) -> str:
        """Return the file's text content.

        Implementations may raise FileNotFoundError if the path is
        missing, or a format-specific error if parsing fails.
        """
