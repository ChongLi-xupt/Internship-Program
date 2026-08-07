"""
Query Node: Chart Type Recommendation.

Recommends optimal chart type based on query intent and result structure.
Uses rule-based logic (fast & deterministic) with optional LLM fallback.
"""

from typing import Any, Dict, List

from app.graph.state.query_state import QueryState


# Intent type → preferred chart types mapping
_INTENT_CHART_MAP = {
    "aggregation": ["bar", "table"],
    "trend": ["line", "area"],
    "comparison": ["bar_grouped", "radar"],
    "ranking": ["bar_horizontal", "table"],
    "detail": ["table"],
}


def _detect_chart_from_data(columns: List[str], rows: List[List[Any]], intent_type: str) -> Dict[str, Any]:
    """Rule-based chart type detection from data shape."""

    col_count = len(columns)
    row_count = len(rows)

    # Single value → number card
    if col_count == 1 and row_count == 1:
        return {"type": "number", "config": {"field": columns[0], "value": rows[0][0]}}

    # Time series → line chart
    time_keywords = ["date", "time", "month", "year", "quarter", "week", "日期", "时间", "月", "年", "季度"]
    has_time_col = any(any(kw in c.lower() for kw in time_keywords) for c in columns)

    if has_time_col and col_count >= 2 and row_count > 1:
        x_col = next((c for c in columns if any(kw in c.lower() for kw in time_keywords)), columns[0])
        y_col = columns[1] if len(columns) > 1 else columns[0]
        return {
            "type": "line",
            "config": {
                "x": x_col,
                "y": y_col,
                "title": "",
            },
        }

    # Category + Value → bar/pie
    if col_count == 2 and row_count <= 12:
        cat_col = columns[0]
        val_col = columns[1]
        # If ranking intent → horizontal bar
        if intent_type == "ranking":
            return {
                "type": "bar_horizontal",
                "config": {"x": val_col, "y": cat_col, "title": ""},
            }
        return {
            "type": "bar",
            "config": {"x": cat_col, "y": val_col, "title": ""},
        }

    # Many categories → horizontal bar
    if col_count == 2 and row_count > 12:
        return {
            "type": "bar_horizontal",
            "config": {"x": columns[1], "y": columns[0], "title": ""},
        }

    # Multi-dimension → grouped bar or just table
    if col_count >= 3:
        return {
            "type": "table",
            "config": {"columns": columns, "sortable": True, "exportable": True},
        }

    # Default: table
    return {
        "type": "table",
        "config": {"columns": columns, "sortable": True, "exportable": True},
    }


async def chart_recommend_node(state: QueryState) -> Dict[str, Any]:
    """Recommend chart type based on intent and data."""
    detected_intent = state.get("detected_intent", {})
    execution_result = state.get("execution_result", {})

    intent_type = detected_intent.get("type", "aggregation")
    columns = execution_result.get("columns", [])
    rows = execution_result.get("rows", [])

    if not columns or not rows:
        return {"chart_recommendation": {"type": "none", "config": {}}}

    # Primary recommendation from rules
    chart = _detect_chart_from_data(columns, rows, intent_type)

    # Override with intent-based preference if applicable
    preferred = _INTENT_CHART_MAP.get(intent_type, [])
    if preferred and chart["type"] not in preferred:
        chart["type"] = preferred[0]  # Use first preference

    return {"chart_recommendation": chart}
