"""PDF parser using pdfplumber (excellent table extraction)."""

import pdfplumber
from typing import Any, Dict

from .base import BaseParser


class PDFParser(BaseParser):

    @property
    def supported_extensions(self) -> list[str]:
        return [".pdf"]

    async def parse(self, file_path: str) -> Dict[str, Any]:
        text_parts = []
        tables = []
        metadata = {"page_count": 0}

        with pdfplumber.open(file_path) as pdf:
            metadata["page_count"] = len(pdf.pages)

            for i, page in enumerate(pdf.pages):
                # Extract text
                page_text = page.extract_text() or ""
                if page_text.strip():
                    text_parts.append(f"[Page {i + 1}]\n{page_text}")

                # Extract tables
                page_tables = page.extract_tables()
                for table in page_tables:
                    if table and len(table) > 0:
                        table_text = self._table_to_text(table)
                        text_parts.append(table_text)
                        tables.append({"page": i + 1, "data": table})

        full_text = "\n\n".join(text_parts)
        return {
            "text": full_text,
            "metadata": metadata,
            "tables": tables,
        }

    @staticmethod
    def _table_to_text(table: list[list]) -> str:
        """Convert a table to markdown-like text representation."""
        rows = []
        for row_idx, row in enumerate(table):
            if row is None:
                continue
            cells = [str(cell) if cell is not None else "" for cell in row]
            rows.append(" | ".join(cells))
            if row_idx == 0:
                rows.append("---|" * len(cells))

        return "<table>\n" + "\n".join(rows) + "\n</table>"
