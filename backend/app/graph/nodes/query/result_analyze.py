"""
Query Node: Result Analysis.

Uses LLM to analyze query results and generate natural language insights:
- Trend analysis (up/down/flat)
- Anomaly detection (unusual values)
- Key findings summary
- Comparison conclusions
"""

import json
from typing import Any, Dict

from langchain_core.messages import HumanMessage, SystemMessage

from app.graph.state.query_state import QueryState
from app.llm.base import get_llm


ANALYSIS_SYSTEM_PROMPT = """你是一个数据分析专家。根据用户的查询问题和数据库查询结果，提供专业、简洁的数据分析结论。

分析要求：
1. 用自然语言描述数据中的关键发现
2. 指出趋势（上升/下降/稳定）、极值、异常点
3. 对比数据时说明差异和原因（如果可推断）
4. 给出有价值的业务洞察
5. 使用数字支撑你的结论，不要泛泛而谈
6. 回答要简洁有力，不超过300字
7. 使用与用户相同的语言回答"""


async def result_analyze_node(state: QueryState) -> Dict[str, Any]:
    """Analyze query results using LLM."""
    question = state["question"]
    execution_result = state.get("execution_result", {})
    structured_intent = state.get("structured_intent", {})
    generated_sql = state.get("generated_sql", "")

    if not execution_result:
        return {"analysis_text": "未能获取查询结果。"}

    columns = execution_result.get("columns", [])
    rows = execution_result.get("rows", [])
    row_count = execution_result.get("row_count", 0)

    if row_count == 0:
        return {"analysis_text": "未找到符合条件的数据。可能的原因：时间范围内无记录、筛选条件过严、或该维度下确实没有数据。建议尝试调整查询条件。"}

    # Prepare data summary for LLM (don't send all rows if too many)
    max_display_rows = 20
    display_rows = rows[:max_display_rows]

    data_summary = {
        "columns": columns,
        "row_count": row_count,
        "sample_rows": display_rows,
        "truncated": row_count > max_display_rows,
    }

    llm = get_llm()

    messages = [
        SystemMessage(content=ANALYSIS_SYSTEM_PROMPT),
        HumanMessage(content=(
            f"## 用户问题\n{question}\n\n"
            f"## 查询意图\n```json\n{json.dumps(structured_intent, ensure_ascii=False)}\n```\n\n"
            f"## 查询结果\n```json\n{json.dumps(data_summary, ensure_ascii=False)}\n```\n\n"
            f"## 执行的SQL\n```sql\n{generated_sql}\n```\n\n"
            "请基于以上数据进行专业分析："
        )),
    ]

    response = await llm.ainvoke(messages)
    analysis_text = response.content.strip()

    return {"analysis_text": analysis_text}
