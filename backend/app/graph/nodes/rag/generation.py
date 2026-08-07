"""
RAG Node 5: Generation — LLM produces the final answer with citation markers.
"""

import time
from typing import Any, Dict

from langchain_core.messages import HumanMessage, SystemMessage

from app.graph.state.rag_state import RAGState
from app.llm.base import get_llm


def _build_rag_prompt(system_prompt: str | None, context: str, question: str) -> tuple[SystemMessage, HumanMessage]:
    """Build the generation prompt with context and citation instructions."""

    default_system = """你是一个专业的智能问答助手。请基于提供的参考文档内容回答用户的问题。

重要规则：
1. 回答必须严格基于给定的参考文档内容，不要编造文档中没有的信息
2. 如果参考文档中没有足够的信息来回答，请明确说明
3. 在回答中引用来源时，使用 [doc_n] 格式标注，其中 n 是文档编号
4. 回答要准确、简洁、有条理
5. 使用与用户相同的语言回答"""

    sys_content = system_prompt or default_system
    if context:
        sys_content += f"\n\n## 参考文档\n\n{context}"

    system_msg = SystemMessage(content=sys_content)

    user_content = f"请回答以下问题：\n\n{question}"
    human_msg = HumanMessage(content=user_content)

    return system_msg, human_msg


async def generate_node(state: RAGState) -> Dict[str, Any]:
    """Generate answer using LLM with streaming support."""
    question = state.get("rewritten_question", state["question"])
    context = state.get("context_text", "")
    kb_custom_prompt = state.get("metadata", {}).get("system_prompt")

    llm = get_llm()
    system_msg, human_msg = _build_rag_prompt(kb_custom_prompt, context, question)

    start_time = time.time()

    response = await llm.ainvoke([system_msg, human_msg])

    latency_ms = (time.time() - start_time) * 1000

    # Estimate token usage
    answer_text = response.content.strip()
    prompt_tokens = len((system_msg.content + human_msg.content).encode()) // 3
    completion_tokens = len(answer_text.encode()) // 3

    metadata = {
        **state.get("metadata", {}),
        "model": getattr(response, "response_metadata", {}).get("model_name", "unknown"),
        "latency_ms": round(latency_ms, 2),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
    }

    return {
        "answer": answer_text,
        "metadata": metadata,
    }
