"""Text chunking strategies."""

from typing import Any, Dict, List


class TextChunker:
    """
    Splits text into chunks suitable for embedding and retrieval.
    Uses recursive character splitting with awareness of document structure.
    """

    def __init__(
        self,
        chunk_size: int = 512,
        overlap: int = 50,
        separators: List[str] | None = None,
    ):
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.separators = separators or [
            "\n\n## ",  # Markdown heading level 2
            "\n\n",     # Paragraph break
            "\n",       # Line break
            "。",       # Chinese period
            ". ",       # English period + space
            "，",       # Chinese comma
            ", ",       # English comma
            " ",        # Space
            "",
        ]

    def chunk(self, text: str, metadata: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
        """Split text into chunks with metadata."""
        if not text or not text.strip():
            return []

        chunks = []
        self._recursive_split(text, self.separators, chunks, metadata or {})
        return chunks

    def _recursive_split(
        self,
        text: str,
        separators: List[str],
        chunks: List[Dict[str, Any]],
        metadata: Dict[str, Any],
    ):
        """Recursively split text trying each separator."""
        if len(text) <= self.chunk_size:
            chunks.append(self._make_chunk(text, metadata))
            return

        # Find the best separator to split on
        for sep in separators:
            if sep not in text:
                continue

            parts = text.split(sep)
            if any(len(p) > self.chunk_size for p in parts):
                continue  # This separator doesn't help, try next

            # Good separator found — split and recurse
            for i, part in enumerate(parts):
                if not part.strip():
                    continue
                if len(part) <= self.chunk_size:
                    chunks.append(self._make_chunk(part.strip(), metadata))
                else:
                    # Still too long — recurse with smaller separators
                    remaining_seps = separators[separators.index(sep) + 1 :]
                    if remaining_seps:
                        self._recursive_split(part.strip(), remaining_seps, chunks, metadata)
                    else:
                        # Last resort: force split at chunk_size
                        for j in range(0, len(part), self.chunk_size - self.overlap):
                            chunk_text = part[j : j + self.chunk_size].strip()
                            if chunk_text:
                                chunks.append(self._make_chunk(chunk_text, metadata))
            return

        # No separator worked — force split
        for j in range(0, len(text), self.chunk_size - self.overlap):
            chunk_text = text[j : j + self.chunk_size].strip()
            if chunk_text:
                chunks.append(self._make_chunk(chunk_text, metadata))

    def _make_chunk(self, text: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Create a chunk dict with metadata."""
        token_estimate = len(text) // 2  # Rough estimate
        return {
            "content": text,
            "token_count": token_estimate,
            "metadata": {
                **metadata,
                "char_length": len(text),
            },
        }
