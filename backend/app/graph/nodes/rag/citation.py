"""
RAG Node 6: Citation Building.

Extracts [doc_n] markers from generated answer and builds structured citations.
"""

import re
from typing import Any, Dict, List

from app.graph.state.rag_state import RAGState, Citation, ChunkRef

# Pattern to find citation markers like [doc_1], [doc_2], [1], etc.
CITATION_PATTERN = re.compile(r"\[doc_(\d+)\]|\[(\d+)\]")


def _build_citation(marker_num: int, chunks: List[ChunkRef]) -> Citation | None:
    """Build a citation object from marker number and retrieved chunks."""
    idx = marker_num - 1  # 1-based to 0-based
    if idx < 0 or idx >= len(chunks):
        return None

    chunk = chunks[idx]
    meta = chunk.get("metadata", {})

    return Citation(
        doc_title=meta.get("title", f"文档_{chunk.get('document_id', '?')[:8]}"),
        chunk_content=chunk.get("content", "")[:500],
        document_id=chunk.get("document_id", ""),
        chunk_index=chunk.get("chunk_index", 0),
        score=chunk.get("score", 0),
        page_numbers=meta.get("page_numbers", [meta.get("page_number")] if meta.get("page_number") else []),
    )


async def citation_build_node(state: RAGState) -> Dict[str, Any]:
    """Extract citation markers and build citation objects."""
    answer = state.get("answer", "")
    chunks = state.get("reranked_chunks") or state.get("retrieved_chunks", [])

    if not answer or not chunks:
        return {"citations": []}

    # Find all citation markers in order of appearance
    citations: List[Citation] = []
    seen_indices: set[int] = set()

    for match in CITATION_PATTERN.finditer(answer):
        num = int(match.group(1) or match.group(2))
        if num not in seen_indices:
            citation = _build_citation(num, chunks)
            if citation:
                citations.append(citation)
                seen_indices.add(num)

    # If no explicit markers found but we have chunks, cite top sources
    if not citations and chunks:
        for i in range(min(3, len(chunks))):
            citation = _build_citation(i + 1, chunks)
            if citation:
                citations.append(citation)

    return {"citations": citations}
