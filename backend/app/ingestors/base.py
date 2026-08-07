"""Base parser interface."""

from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseParser(ABC):
    """Abstract base class for document parsers."""

    @abstractmethod
    async def parse(self, file_path: str) -> Dict[str, Any]:
        """
        Parse a document file.

        Returns:
            {
                "text": str,           # Full extracted text
                "metadata": dict,       # Document metadata (title, author, pages, etc.)
                "tables": list[dict],   # Extracted tables (if any)
            }
        """
        ...

    @property
    @abstractmethod
    def supported_extensions(self) -> list[str]:
        """List of file extensions this parser handles."""
        ...
