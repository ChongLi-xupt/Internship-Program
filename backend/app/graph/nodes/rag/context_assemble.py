"""
RAG Node 4: Context Assembly.

Formats retrieved chunks into a structured context string for LLM generation.
Applies token budget management to avoid exceeding context window.
"""

from typing import Any, Dict

from app.graph.state.rag_state import RAGState

# Approximate characters per token (for Chinese + English mixed text)
CHARS_PER_TOKEN_ESTIMATE = 2.5
# Reserve 40% of context window for answer generation
CONTEXT_BUDGET_RATIO = 0.6
# Default context window size (will be overridden by actual model config)
DEFAULT_CONTEXT_WINDOW = 128_000


def _estimate_tokens(text: str) -> int:
    """Rough token count estimation."""
    return int(len(text) / CHARS_PER_TOKEN_ESTIMATE)


async def context_assemble_node(state: RAGState) -> Dict[str, Any]:
    """Assemble retrieved chunks into formatted context text."""
    chunks = state.get("reranked_chunks") or state.get("retrieved_chunks", [])

    if not chunks:
        return {"context_text": ""}

    # Calculate token budget
    context_budget = int(DEFAULT_CONTEXT_WINDOW * CONTEXT_BUDGET_RATIO)

    # Format chunks as <doc> blocks with source references
    doc_parts: list[str] = []
    total_tokens = 0

    for i, chunk in enumerate(chunks):
        doc_title = chunk.get("metadata", {}).get("title", f"文档_{chunk.get('document_id', '?')[:8]}")
        page_info = chunk.get("metadata", {}).get("page_number", "")
        page_str = f" (第{page_info}页)" if page_info else ""

        part = (
            f"<doc id=\"{i + 1}\">\n"
            f"<source>{doc_title}{page_str}</source>\n"
            f"<content>{chunk['content']}</content>\n"
            f"</doc>"
        )

        part_tokens = _estimate_tokens(part)
        if total_tokens + part_tokens > context_budget:
            break  # Token budget exhausted

        doc_parts.append(part)
        total_tokens += part_tokens

    context_text = "\n\n".join(doc_parts)

    return {
        "context_text": context_text,
        "metadata": {
            **state.get("metadata", {}),
            "chunks_used": len(doc_parts),
            "context_tokens": total_tokens,
        },
    }
