"""
RAG Node 2: Multi-path Retrieval.

Performs concurrent retrieval using:
1. Vector similarity search (primary)
2. Optional BM25/keyword search (secondary)
Merges results and applies metadata filtering (permissions + tenant).
"""

import asyncio
from typing import Any, Dict, List

from app.graph.state.rag_state import RAGState, ChunkRef
from app.vector.base import get_vector_store


async def _vector_search(query: str, kb_id: str, tenant_id: str, permissions: List[str], top_k: int = 20) -> List[ChunkRef]:
    """Vector similarity search via Qdrant/Chroma."""
    store = get_vector_store()
    results = await store.search(
        collection_name=f"kb_{kb_id}",
        query_text=query,
        tenant_id=tenant_id,
        filter_tags=permissions,
        top_k=top_k,
    )
    return results


async def multi_retrieval_node(state: RAGState) -> Dict[str, Any]:
    """Execute concurrent multi-path retrieval and merge results."""
    queries = state.get("search_queries", [state["question"]])
    kb_id = state["kb_id"]
    tenant_id = state["tenant_id"]
    permissions = state.get("user_permissions", [])
    top_k_per_query = 15  # Per-query top-k (will be merged and reranked later)

    # Run all queries concurrently
    tasks = [_vector_search(q, kb_id, tenant_id, permissions, top_k_per_query) for q in queries]
    results_list = await asyncio.gather(*tasks, return_exceptions=True)

    # Merge all results, deduplicate by (document_id, chunk_index)
    seen: set[tuple[str, int]] = set()
    all_chunks: List[ChunkRef] = []

    for results in results_list:
        if isinstance(results, Exception):
            continue
        for chunk in results:
            key = (chunk["document_id"], chunk["chunk_index"])
            if key not in seen:
                seen.add(key)
                all_chunks.append(chunk)

    # Sort by score descending
    all_chunks.sort(key=lambda c: c.get("score", 0), reverse=True)

    # Keep top candidates for reranking
    top_chunks = all_chunks[:30]

    return {
        "retrieved_chunks": top_chunks,
    }
