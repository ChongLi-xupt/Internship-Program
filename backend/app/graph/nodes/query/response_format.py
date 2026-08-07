"""
Query Node: Response Formatting.

Assembles final response from all pipeline outputs:
- Natural language analysis text
- Data table
- Chart configuration
- SQL display
"""

from typing import Any, Dict

from app.graph.state.query_state import QueryState


async def response_format_node(state: QueryState) -> Dict[str, Any]:
    """Format the final response combining all components."""
    analysis_text = state.get("analysis_text", "")
    execution_result = state.get("execution_result", {})
    chart_rec = state.get("chart_recommendation", {})
    guarded_sql = state.get("guarded_sql", "")
    error_info = state.get("error_info", {})

    metadata = state.get("metadata", {})

    if error_info:
        natural_response = (
            f"⚠️ 查询执行失败: {error_info.get('message', '未知错误')}\n\n"
            "建议：请检查查询条件是否合理，或联系管理员。"
        )
    elif not execution_result:
        natural_response = "未获取到查询结果。"
    else:
        # Build rich response with analysis + data reference
        parts = []

        if analysis_text:
            parts.append(analysis_text)

        row_count = execution_result.get("row_count", 0)
        if row_count > 0:
            parts.append(f"\n📊 共查询到 **{row_count}** 条记录。")

        natural_response = "\n".join(parts)

    # Final metadata
    final_metadata = {
        "sql": guarded_sql,
        "chart_config": chart_rec,
        "result_row_count": execution_result.get("row_count", 0),
        "confidence": detected_intent.get("confidence") if (detected_intent := state.get("detected_intent")) else None,
        **metadata,
    }

    return {
        "natural_response": natural_response,
        "metadata": final_metadata,
    }
