"""
Query Graph Definition — SQLBot-style NL2SQL pipeline.

DAG (matching SQLBot's 3-step workflow):
  start → intent_recognize → nl_understand → example_retrieve
        → sql_compile → sql_guard ──[fail]──→ sql_compile (retry, max 2x)
                              │
                             [pass]
                              ↓
        sql_execute → result_analyze → chart_recommend → response_format → end

With conditional edges for:
- Intent routing (SQL path vs terminology vs clarification)
- SQL guard failure → retry compilation with error feedback
- Execution failure → retry compilation with DB error info
"""

from typing import Any, Dict, Literal

from langgraph.graph import StateGraph, END

from app.graph.state.query_state import QueryState
from app.graph.nodes.query.intent_recognize import intent_recognize_node
from app.graph.nodes.query.nl_understand import nl_understand_node
from app.graph.nodes.query.example_retrieve import example_retrieve_node
from app.graph.nodes.query.sql_compile import sql_compile_node
from app.graph.nodes.query.sql_guard import sql_guard_node
from app.graph.nodes.query.sql_execute import sql_execute_node
from app.graph.nodes.query.result_analyze import result_analyze_node
from app.graph.nodes.query.chart_recommend import chart_recommend_node
from app.graph.nodes.query.response_format import response_format_node

# Max retries for SQL compilation after guard/execution failure
MAX_SQL_RETRIES = 2


def _route_by_intent(state: QueryState) -> Literal["nl_understand", "terminology_lookup", "clarification"]:
    """Route based on detected intent type."""
    intent_type = (state.get("detected_intent") or {}).get("type", "aggregation")

    if intent_type in ("definition",):
        return "terminology_lookup"
    elif intent_type == "ambiguous":
        return "clarification"
    else:
        return "nl_understand"


def _route_after_guard(state: QueryState) -> Literal["sql_execute", "sql_compile"]:
    """If guard failed, retry compilation."""
    errors = state.get("guard_errors", [])
    retry_count = (state.get("metadata") or {}).get("retry_count", 0)

    if errors and retry_count < MAX_SQL_RETRIES:
        return "sql_compile"  # Retry with error feedback
    return "sql_execute"


def _route_after_execution(state: QueryState) -> Literal["result_analyze", "sql_compile"]:
    """If execution failed, retry compilation with DB error."""
    error_info = state.get("error_info", {})
    retry_count = (state.get("metadata") or {}).get("retry_count", 0)

    if error_info and retry_count < MAX_SQL_RETRIES:
        return "sql_compile"
    return "result_analyze"


def build_query_graph() -> StateGraph:
    """Build and return the compiled Smart Query StateGraph."""
    graph = StateGraph(QueryState)

    # Add all nodes
    graph.add_node("intent_recognize", intent_recognize_node)
    graph.add_node("nl_understand", nl_understand_node)
    graph.add_node("terminology_lookup", _terminology_lookup_node)
    graph.add_node("clarification", _clarification_node)
    graph.add_node("example_retrieve", example_retrieve_node)
    graph.add_node("sql_compile", sql_compile_node)
    graph.add_node("sql_guard", sql_guard_node)
    graph.add_node("sql_execute", sql_execute_node)
    graph.add_node("result_analyze", result_analyze_node)
    graph.add_node("chart_recommend", chart_recommend_node)
    graph.add_node("response_format", response_format_node)

    # Entry point
    graph.set_entry_point("intent_recognize")

    # Step 1: Intent recognition → route by type
    graph.add_conditional_edges(
        "intent_recognize",
        _route_by_intent,
        {
            "nl_understand": "nl_understand",
            "terminology_lookup": "terminology_lookup",
            "clarification": "clarification",
        },
    )

    # Terminology & clarification go directly to response format
    graph.add_edge("terminology_lookup", "response_format")
    graph.add_edge("clarification", "response_format")

    # Main SQL path
    graph.add_edge("nl_understand", "example_retrieve")
    graph.add_edge("example_retrieve", "sql_compile")
    graph.add_edge("sql_compile", "sql_guard")

    # Guard → execute or retry
    graph.add_conditional_edges(
        "sql_guard",
        _route_after_guard,
        {"sql_execute": "sql_execute", "sql_compile": "sql_compile"},
    )

    # Execute → analyze or retry
    graph.add_conditional_edges(
        "sql_execute",
        _route_after_execution,
        {"result_analyze": "result_analyze", "sql_compile": "sql_compile"},
    )

    # Final pipeline
    graph.add_edge("result_analyze", "chart_recommend")
    graph.add_edge("chart_recommend", "response_format")
    graph.add_edge("response_format", END)

    return graph.compile()


async def _terminology_lookup_node(state: QueryState) -> Dict[str, Any]:
    """Handle definition/explanation queries via terminology lookup."""
    question = state["question"]
    tenant_id = state["tenant_id"]

    from sqlalchemy import select
    from app.database import get_async_session
    from app.models.semantic import Terminology

    async with get_async_session() as db:
        # Fuzzy search terminology
        result = await db.execute(
            select(Terminology).where(
                Terminology.tenant_id == tenant_id,
            ).limit(5)
        )
        terms = result.scalars().all()

    # Find best match (simple keyword overlap)
    q_words = set(question.lower().split())
    best_match = None
    best_score = 0

    for term in terms:
        score = len(q_words & set(term.term.lower().split()))
        score += len(q_words & set(s.lower() for s in term.synonyms))
        if score > best_score:
            best_score = score
            best_match = term

    if best_match:
        analysis_text = f"**{best_match.term}**: {best_match.definition or '暂无定义'}"
        if best_match.synonyms:
            analysis_text += f"\n\n同义词：{', '.join(best_match.synonyms)}"
    else:
        analysis_text = f"未在术语库中找到与「{question}」相关的术语定义。"

    return {
        "analysis_text": analysis_text,
        "natural_response": analysis_text,
        "chart_recommendation": {"type": "none", "config": {}},
        "metadata": {**state.get("metadata", {}), "resolved_via": "terminology"},
    }


async def _clarification_node(state: QueryState) -> Dict[str, Any]:
    """Generate clarification question for ambiguous queries."""
    question = state["question"]

    clarification = (
        f"您的问题「{question}」不够明确。为了给您更准确的答案，请补充以下信息：\n\n"
        "- 您想查询哪个时间范围的数据？\n"
        "- 需要哪些维度（如地区、产品、部门等）？\n"
        "- 希望看到什么指标（如销售额、数量、占比等）？"
    )

    return {
        "analysis_text": clarification,
        "natural_response": clarification,
        "chart_recommendation": {"type": "none", "config": {}},
        "metadata": {**state.get("metadata", {}), "resolved_via": "clarification"},
    }


# Compiled graph singleton
_query_graph = None


def get_query_graph():
    """Get or create the compiled Query graph."""
    global _query_graph
    if _query_graph is None:
        _query_graph = build_query_graph()
    return _query_graph


def reset_query_graph():
    """Force rebuild the query graph (for error recovery)."""
    global _query_graph
    _query_graph = None


async def run_query_pipeline(
    question: str,
    datasource_id: str,
    tenant_id: str,
    user_permissions: list[str],
    conversation_id: str | None = None,
    chat_history: list[dict] | None = None,
) -> dict[str, Any]:
    """
    Run the full Smart Query pipeline (SQLBot-style).

    Returns final state with analysis, chart config, SQL, etc.
    """
    graph = get_query_graph()

    initial_state: QueryState = {
        "question": question,
        "datasource_id": datasource_id,
        "conversation_id": conversation_id,
        "chat_history": chat_history or [],
        "tenant_id": tenant_id,
        "user_permissions": user_permissions,
        "detected_intent": {},
        "structured_intent": {},
        "selected_examples": [],
        "generated_sql": "",
        "guarded_sql": "",
        "guard_warnings": [],
        "guard_errors": [],
        "execution_result": {},
        "error_info": {},
        "analysis_text": "",
        "chart_recommendation": {},
        "natural_response": "",
        "metadata": {},
    }

    result = await graph.ainvoke(initial_state)

    return result
