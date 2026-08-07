"""Markdown / plain text parser."""

from pathlib import Path
from typing import Any, Dict

from .base import BaseParser


class MarkdownParser(BaseParser):

    @property
    def supported_extensions(self) -> list[str]:
        return [".md", ".markdown", ".txt"]

    async def parse(self, file_path: str) -> Dict[str, Any]:
        path = Path(file_path)
        text = path.read_text(encoding="utf-8")
        return {
            "text": text,
            "metadata": {"filename": path.name},
            "tables": [],
        }
