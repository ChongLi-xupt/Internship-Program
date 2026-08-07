"""RAG Graph state definition."""

from typing import Any, Dict, List, Optional
from typing_extensions import TypedDict


class Citation(TypedDict):
    """A single citation reference."""
    doc_title: str
    chunk_content: str
    document_id: str
    chunk_index: int
    score: float
    page_numbers: List[int]


class ChunkRef(TypedDict):
    """Reference to a retrieved chunk."""
    content: str
    document_id: str
    kb_id: str
    chunk_index: int
    score: float
    metadata: Dict[str, Any]


class RAGState(TypedDict):
    # ── Input ──
    question: str  # User's original question
    conversation_id: Optional[str]  # Conversation ID for history
    kb_id: str  # Knowledge base ID
    chat_history: List[Dict[str, str]]  # Recent message turns [{role, content}]
    tenant_id: str  # Current tenant
    user_permissions: List[str]  # User's permission tags for filtering

    # ── Intermediate ──
    rewritten_question: str  # Rewritten/expanded question
    search_queries: List[str]  # Expanded queries for multi-path retrieval
    retrieved_chunks: List[ChunkRef]  # Raw retrieved chunks
    reranked_chunks: List[ChunkRef]  # After reranking
    context_text: str  # Assembled context for LLM

    # ── Output ──
    answer: str  # Final generated answer
    citations: List[Citation]  # Source citations
    metadata: Dict[str, Any]  # {tokens, latency, model, sources}
