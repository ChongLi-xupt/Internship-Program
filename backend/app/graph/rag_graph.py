"""
RAG Graph Definition — assembles RAG nodes into a LangGraph StateGraph.

DAG:
  start → query_rewrite → multi_retrieval → rerank → context_assemble
        → generate → citation_build → end

With conditional edges for:
- Skip rerank if not configured
- Retry on low confidence generation
"""

from typing import Any, Dict, Literal

from langgraph.graph import StateGraph, END

from app.graph.state.rag_state import RAGState
from app.graph.nodes.rag.query_rewrite import query_rewrite_node
from app.graph.nodes.rag.retrieval import multi_retrieval_node
from app.graph.nodes.rag.rerank import rerank_node
from app.graph.nodes.rag.context_assemble import context_assemble_node
from app.graph.nodes.rag.generation import generate_node
from app.graph.nodes.rag.citation import citation_build_node


def _should_rerank(state: RAGState) -> Literal["rerank", "generate"]:
    """Decide whether to rerank or skip to generate."""
    # In production, check knowledge base config: state["kb_config"].get("rerank_enabled")
    # For now, always rerank (it's a lightweight operation)
    return "rerank"


def _should_retry(state: RAGState) -> Literal["multi_retrieval", "citation_build"]:
    """Check if generation confidence is low and retry is warranted."""
    metadata = state.get("metadata", {})
    confidence = metadata.get("confidence", 1.0)
    retry_count = metadata.get("retry_count", 0)

    if confidence < 0.5 and retry_count < 1:
        return "multi_retrieval"  # Go back for more context
    return "citation_build"


def build_rag_graph() -> StateGraph:
    """Build and return the compiled RAG StateGraph."""
    graph = StateGraph(RAGState)

    # Add nodes
    graph.add_node("query_rewrite", query_rewrite_node)
    graph.add_node("multi_retrieval", multi_retrieval_node)
    graph.add_node("rerank", rerank_node)
    graph.add_node("context_assemble", context_assemble_node)
    graph.add_node("generate", generate_node)
    graph.add_node("citation_build", citation_build_node)

    # Define edges
    graph.set_entry_point("query_rewrite")
    graph.add_edge("query_rewrite", "multi_retrieval")

    # Conditional: rerank or skip
    graph.add_conditional_edges(
        "multi_retrieval",
        _should_rerank,
        {"rerank": "rerank", "generate": "context_assemble"},
    )

    graph.add_edge("rerank", "context_assemble")
    graph.add_edge("context_assemble", "generate")

    # Conditional: retry on low confidence or proceed
    graph.add_conditional_edges(
        "generate",
        _should_retry,
        {"multi_retrieval": "multi_retrieval", "citation_build": "citation_build"},
    )

    graph.add_edge("citation_build", END)

    return graph.compile()


# Compiled graph singleton
_rag_graph = None


def get_rag_graph():
    """Get or create the compiled RAG graph."""
    global _rag_graph
    if _rag_graph is None:
        _rag_graph = build_rag_graph()
    return _rag_graph


async def run_rag_pipeline(
    question: str,
    kb_id: str,
    tenant_id: str,
    user_permissions: list[str],
    conversation_id: str | None = None,
    chat_history: list[dict] | None = None,
) -> dict[str, Any]:
    """
    Run the full RAG pipeline.

    Returns final state with answer, citations, and metadata.
    """
    graph = get_rag_graph()

    initial_state: RAGState = {
        "question": question,
        "conversation_id": conversation_id,
        "kb_id": kb_id,
        "chat_history": chat_history or [],
        "tenant_id": tenant_id,
        "user_permissions": user_permissions,
        "rewritten_question": "",
        "search_queries": [],
        "retrieved_chunks": [],
        "reranked_chunks": [],
        "context_text": "",
        "answer": "",
        "citations": [],
        "metadata": {},
    }

    result = await graph.ainvoke(initial_state)

    return result
