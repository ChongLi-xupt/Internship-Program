"""
Query Node 2: Natural Language Understanding — NL to Structured Intent.

This is THE core node of Smart Query. It converts natural language into a structured
query intent using the semantic layer as intermediary:

  User Question + Terminology + Semantic Layer (Metrics/Dimensions) + Table Schema
    → Structured Intent {metrics[], dimensions[], filters[], time_range[], sort[], limit}
"""

import json
from typing import Any, Dict

from langchain_core.messages import HumanMessage, SystemMessage

from app.graph.state.query_state import QueryState
from app.llm.base import get_llm


def _build_nl_understand_prompt(
    question: str,
    terminology: list[Dict],
    metrics: list[Dict],
    dimensions: list[Dict],
    table_schemas: list[Dict],
    few_shot_examples: list[Dict] | None = None,
) -> tuple[SystemMessage, HumanMessage]:
    """Build prompt with full semantic context."""

    term_section = ""
    if terminology:
        terms = [f"- {t['term']}: 同义词={t.get('synonyms', [])}, 定义={t.get('definition', '')}" for t in terminology[:30]]
        term_section = f"\n## 术语库\n" + "\n".join(terms)

    metric_section = ""
    if metrics:
        m_lines = [f"- {m['name']} ({m['aggregation']}): 表达式={m['column_expr']}, 单位={m.get('unit','')}, 别名={m.get('aliases',[])}" for m in metrics]
        metric_section = f"\n## 可用指标\n" + "\n".join(m_lines)

    dim_section = ""
    if dimensions:
        d_lines = []
        for d in dimensions:
            extra = ""
            if d.get("time_granularity") and d["time_granularity"] != "none":
                extra = f", 时间粒度={d['time_granularity']}"
            if d.get("values"):
                extra += f", 枚举值={[v['label'] for v in d['values'][:10]]}"
            d_lines.append(f"- {d['name']}: 列={d.get('column_name','')}, 别名={d.get('aliases',[])}{extra}")
        dim_section = f"\n## 可用维度\n" + "\n".join(d_lines)

    schema_section = ""
    if table_schemas:
        schema_section = "\n## 数据表结构\n"
        for ts in table_schemas[:10]:
            cols = ", ".join([f"{c['name']}({c['type']}){' '+c.get('comment','') if c.get('comment') else ''}" for c in ts.get("columns", [])])
            schema_section += f"- {ts.get('table_name','')} [{ts.get('schema_name','public')}]: {cols}\n"

    example_section = ""
    if few_shot_examples:
        example_section = "\n## 参考示例(SQL)\n"
        for ex in few_shot_examples[:5]:
            example_section += f"Q: {ex['question']}\nSQL: {ex['sql']}\n\n"

    system_content = (
        "你是一个专业的自然语言到结构化查询意图的解析器。\n"
        "你的任务是将用户的自然语言问题转换为结构化的查询意图。\n\n"
        "你必须且只能使用上面提供的：术语库、可用指标、可用维度、数据表结构来理解问题。\n"
        "不要使用未列出的指标名、维度名或表名。如果用户的问题无法用已有语义元素表达，请将对应字段设为null并标注原因。\n\n"
        f"{term_section}\n"
        f"{metric_section}\n"
        f"{dim_section}\n"
        f"{schema_section}\n"
        f"{example_section}\n\n"
        '输出严格JSON格式（不要markdown代码块）：\n'
        "{\n"
        '  "metrics": [{"name":"显示名", "aggregation":"sum|avg|count|count_distinct|max|min", "expr":"SQL表达式", "unit":"单位"}],\n'
        '  "dimensions": [{"name":"显示名", "column_name":"物理列名"}],\n'
        '  "filters": [{"column":"列名", "operator":"=|!=|>|<|>=|<=|IN|LIKE|BETWEEN", "value":"值"}],\n'
        '  "time_range": {"start":"YYYY-MM-DD", "end":"YYYY-MM-DD", "type":"year|quarter|month|week|day"},\n'
        '  "sort": [{"column":"列名", "order":"asc|desc"}],\n'
        '  "limit": 数字,\n'
        '  "notes": "任何需要注意的点"\n'
        "}"
    )

    user_content = f"请解析以下问题的结构化意图：\n\n{question}"

    return SystemMessage(content=system_content), HumanMessage(content=user_content)


async def nl_understand_node(state: QueryState) -> Dict[str, Any]:
    """
    Convert NL question to structured intent using semantic layer context.
    This is where terminology, metrics, dimensions are injected.
    """
    question = state["question"]
    datasource_id = state["datasource_id"]
    tenant_id = state["tenant_id"]

    llm = get_llm()

    from sqlalchemy import select
    from app.database import get_async_session
    from app.models.semantic import Metric, Dimension, Terminology, SQLExample
    from app.models.datasource import TableMeta

    async with get_async_session() as db:
        layer_result = await db.execute(
            select(Metric).join_from(
                Metric, Dimension, Metric.layer_id == Dimension.layer_id
            ).where(
                True
            ).limit(50)
        )
        metric_result = await db.execute(select(Metric).limit(50))
        metrics = [m.__dict__ for m in metric_result.scalars().all()]

        dim_result = await db.execute(select(Dimension).limit(50))
        dimensions = [d.__dict__ for d in dim_result.scalars().all()]

        term_result = await db.execute(select(Terminology).where(Terminology.tenant_id == tenant_id).limit(100))
        terminology = [t.__dict__ for t in term_result.scalars().all()]

        table_result = await db.execute(select(TableMeta).where(TableMeta.datasource_id == datasource_id).limit(20))
        table_schemas = [ts.__dict__ for ts in table_result.scalars().all()]

    system_msg, human_msg = _build_nl_understand_prompt(
        question=question,
        terminology=terminology,
        metrics=metrics,
        dimensions=dimensions,
        table_schemas=table_schemas,
    )

    try:
        response = await llm.ainvoke([system_msg, human_msg])
        text = response.content.strip()

        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()

        try:
            intent = json.loads(text)
        except json.JSONDecodeError:
            intent = {"metrics": [], "dimensions": [], "filters": [], "error": "Failed to parse LLM output"}
    except Exception:
        intent = {"metrics": [], "dimensions": [], "filters": [], "error": "LLM调用失败"}

    return {
        "structured_intent": intent,
    }