"""
RAG Node 3: Reranking (optional).

Uses cross-encoder model to re-rank retrieved chunks by relevance to the original question.
If reranking is not configured for the knowledge base, this is a no-op pass-through.
"""

from typing import Any, Dict, List

from app.graph.state.rag_state import RAGState


async def rerank_node(state: RAGState) -> Dict[str, Any]:
    """
    Re-rank chunks. Falls back to score-based truncation if no reranker available.
    """
    chunks = state.get("retrieved_chunks", [])
    question = state.get("rewritten_question", state["question"])

    if not chunks:
        return {"reranked_chunks": []}

    # TODO: Integrate cross-encoder reranker (e.g., bge-reranker-v2-m3)
    # For now, use a simple relevance scoring heuristic:
    # - Boost chunks whose content has keyword overlap with the question
    question_words = set(question.lower().split())

    scored_chunks = []
    for chunk in chunks:
        chunk_words = set(chunk.get("content", "").lower().split())
        overlap = len(question_words & chunk_words)
        vector_score = chunk.get("score", 0)
        combined = vector_score * 0.7 + min(overlap / max(len(question_words), 1), 1.0) * 0.3
        scored_chunks.append({**chunk, "_rerank_score": combined})

    scored_chunks.sort(key=lambda c: c["_rerank_score"], reverse=True)

    # Clean up temp field and take top-K
    top_k = 8
    reranked = []
    for c in scored_chunks[:top_k]:
        c.pop("_rerank_score", None)
        reranked.append(c)

    return {"reranked_chunks": reranked}
