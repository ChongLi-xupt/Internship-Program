"""
Query Node: SQL Compilation — Structured Intent → SQL.

This node does NOT write free-form SQL. Instead, it acts as a "template compiler":
it takes the structured intent and fills in SQL template slots using the
semantic layer mappings. The LLM's job is reduced to mapping, not creative writing.
"""

import json
from typing import Any, Dict, List

from langchain_core.messages import HumanMessage, SystemMessage

from app.graph.state.query_state import QueryState
from app.llm.base import get_llm


def _build_sql_compile_prompt(
    structured_intent: Dict[str, Any],
    examples: List[Dict[str, Any]],
    table_schemas: List[Dict[str, Any]],
) -> tuple[SystemMessage, HumanMessage]:
    """Build SQL compilation prompt with structured input."""

    intent_json = json.dumps(structured_intent, ensure_ascii=False, indent=2)

    example_text = ""
    if examples:
        example_text = "\n## 参考SQL示例\n"
        for i, ex in enumerate(examples):
            example_text += f"### 示例{i+1}\n问题: {ex.get('question','')}\n```sql\n{ex.get('sql','')}\n```\n"
            if ex.get("explanation"):
                example_text += f"说明: {ex['explanation']}\n"
            example_text += "\n"

    schema_text = ""
    if table_schemas:
        schema_text = "\n## 可用数据表\n"
        for ts in table_schemas:
            cols = ", ".join([f"{c['name']} {c['type']}" for c in ts.get("columns", [])])
            schema_text += f"- {ts.get('table_name','')} ({ts.get('schema_name','public')}): {cols}\n"

    system_content = (
        "你是一个SQL编译器。你的任务是根据给定的**结构化查询意图**和**数据表结构**，生成标准的SELECT查询语句。\n\n"
        "规则：\n"
        "1. 只使用上面列出的表和列，不要编造不存在的表或列\n"
        "2. 使用标准SQL语法\n"
        "3. 必须包含WHERE子句进行数据过滤（即使只是时间范围）\n"
        "4. 对于聚合查询必须包含GROUP BY\n"
        "5. 合理使用ORDER BY和LIMIT\n"
        "6. 参考给出的SQL示例的风格和模式\n"
        "7. 输出只有SQL语句，不要解释\n\n"
        f"{schema_text}\n"
        f"{example_text}"
    )

    user_content = (
        f"## 结构化查询意图\n```json\n{intent_json}\n```\n\n"
        "请根据以上信息生成SQL查询语句："
    )

    return SystemMessage(content=system_content), HumanMessage(content=user_content)


async def sql_compile_node(state: QueryState) -> Dict[str, Any]:
    """Compile structured intent into SQL."""
    intent = state.get("structured_intent", {})
    examples = state.get("selected_examples", [])
    datasource_id = state["datasource_id"]

    from sqlalchemy import select
    from app.database import get_async_session
    from app.models.datasource import TableMeta

    async with get_async_session() as db:
        result = await db.execute(select(TableMeta).where(TableMeta.datasource_id == datasource_id).limit(20))
        table_schemas = [ts.__dict__ for ts in result.scalars().all()]

    llm = get_llm()
    system_msg, human_msg = _build_sql_compile_prompt(intent, examples, table_schemas)

    retry_count = state.get("metadata", {}).get("retry_count", 0)

    try:
        response = await llm.ainvoke([system_msg, human_msg])
        sql = response.content.strip()

        if "```sql" in sql:
            sql = sql.split("```sql")[1].split("```")[0].strip()
        elif "```" in sql:
            sql = sql.split("```")[1].split("```")[0].strip()
    except Exception:
        return {
            "generated_sql": "",
            "metadata": {
                **state.get("metadata", {}),
                "retry_count": retry_count,
                "error": "SQL编译失败",
            },
        }

    return {
        "generated_sql": sql,
        "metadata": {
            **state.get("metadata", {}),
            "retry_count": retry_count,
        },
    }