"""
RAG Node 1: Query Rewrite / Question Decomposition.

Takes the user's question and:
- Rewrites for clarity using conversation history
- Decomposes compound questions into sub-queries
- Expands with terminology synonyms
"""

import json
from typing import Any, Dict

from langchain_core.messages import HumanMessage, SystemMessage

from app.graph.state.rag_state import RAGState
from app.llm.base import get_llm


REWRITE_SYSTEM_PROMPT = """你是一个专业的问题改写助手。你的任务是对用户问题进行优化处理，以便后续检索更准确。

规则：
1. 如果问题模糊或有歧义，改写为更明确、完整的表述
2. 结合对话历史，将指代词（"它"、"那个"、"上面说的"）替换为具体内容
3. 如果问题是复合问题（包含多个子问题），拆分为多个独立的检索查询
4. 不要改变问题的原意，只优化表达方式
5. 输出JSON格式：
{
  "rewritten_question": "改写后的主问题",
  "search_queries": ["查询1", "查询2", ...]
}

如果问题不需要改写，rewritten_question保持原样，search_queries包含原问题即可。"""


async def query_rewrite_node(state: RAGState) -> Dict[str, Any]:
    """Rewrite user question and optionally decompose into sub-queries."""
    question = state["question"]
    history = state.get("chat_history", [])

    llm = get_llm()

    # Build context from history
    history_text = ""
    if history:
        history_lines = [f"{msg['role']}: {msg['content']}" for msg in history[-6:]]  # Last 3 turns
        history_text = "\n".join(history_lines)

    user_message = f"请改写以下问题：\n\n{question}"
    if history_text:
        user_message += f"\n\n对话历史（供参考）：\n{history_text}"

    messages = [
        SystemMessage(content=REWRITE_SYSTEM_PROMPT),
        HumanMessage(content=user_message),
    ]

    response = await llm.ainvoke(messages)
    response_text = response.content.strip()

    # Parse JSON from response (handle markdown code blocks)
    if "```json" in response_text:
        response_text = response_text.split("```json")[1].split("```")[0].strip()
    elif "```" in response_text:
        response_text = response_text.split("```")[1].split("```")[0].strip()

    try:
        result = json.loads(response_text)
        rewritten = result.get("rewritten_question", question)
        queries = result.get("search_queries", [question])
    except json.JSONDecodeError:
        rewritten = question
        queries = [question]

    return {
        "rewritten_question": rewritten,
        "search_queries": queries,
    }
