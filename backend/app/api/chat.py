"""
Unified Chat API — the primary interface for both RAG and Smart Query engines.

Supports SSE streaming (default) and non-streaming modes.
This is where LangGraph pipelines are invoked.
"""

import json
import uuid
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import Permission
from app.core.tenant import get_current_tenant_id
from app.dependencies import get_db, get_current_active_user
from app.models.conversation import Conversation, Message, ConversationEngine, MessageRole, MessageType
from app.models.user import User
from app.schemas.chat import (
    ChatMessageRequest,
    ConversationResponse,
    ConversationListParams,
    MessageListResponse,
    MessageDoneEvent,
)
from app.graph.rag_graph import run_rag_pipeline
from app.graph.query_graph import run_query_pipeline

router = APIRouter()


async def _get_or_create_conversation(
    db: AsyncSession,
    user: User,
    engine: str,
    kb_id: uuid.UUID | None,
    datasource_id: uuid.UUID | None,
    conversation_id: uuid.UUID | None,
) -> Conversation:
    """Get existing conversation or create new one."""
    if conversation_id:
        result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
        conv = result.scalar_one_or_none()
        if conv:
            return conv

    tenant_id = get_current_tenant_id() or str(user.tenant_id)
    conv = Conversation(
        tenant_id=uuid.UUID(tenant_id) if isinstance(tenant_id, str) else tenant_id,
        user_id=user.id,
        engine=engine,
        kb_id=kb_id,
        datasource_id=datasource_id,
    )
    db.add(conv)
    await db.flush()

    # Auto-generate title from first message (will be updated later)
    return conv


def _sse_format(event_type: str, data: dict) -> str:
    """Format data as Server-Sent Event."""
    payload = json.dumps(data, ensure_ascii=False, default=str)
    return f"event: {event_type}\ndata: {payload}\n\n"


async def _stream_rag(
    request: ChatMessageRequest,
    conversation: Conversation,
    user: User,
    db: AsyncSession,
) -> AsyncGenerator[str, None]:
    """Stream RAG pipeline events as SSE."""
    # Save user message first
    user_msg = Message(
        conversation_id=conversation.id,
        role="user",
        content=request.message,
        message_type="text",
    )
    db.add(user_msg)
    await db.commit()

    # Run RAG pipeline with error handling
    try:
        result = await run_rag_pipeline(
            question=request.message,
            kb_id=str(request.kb_id),
            tenant_id=str(conversation.tenant_id),
            user_permissions=user.permissions,
            conversation_id=str(conversation.id),
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        error_msg = f"RAG查询执行出错: {str(e)}"
        yield _sse_format("thinking", {"content": f"⚠️ {error_msg}"})
        yield _sse_format("message_delta", {"content": f"\n\n抱歉，{error_msg}"})
        done_event = MessageDoneEvent(
            message_id=uuid.uuid4(),
            conversation_id=conversation.id,
            metadata={"error": str(e)},
        )
        yield _sse_format("message_done", done_event.model_dump())
        return

    # Stream events
    yield _sse_format("thinking", {"content": "正在检索相关知识..."})

    citations = result.get("citations", [])
    if citations:
        sources = [
            {
                "doc_title": c["doc_title"],
                "chunk_content": c["chunk_content"][:300],
                "score": c["score"],
                "document_id": c["document_id"],
            }
            for c in citations
        ]
        yield _sse_format("retrieval_result", {"sources": sources})

    answer = result.get("answer", "")
    metadata = result.get("metadata", {})

    # Stream answer in chunks
    chunk_size = 50
    for i in range(0, len(answer), chunk_size):
        chunk = answer[i : i + chunk_size]
        yield _sse_format("message_delta", {"content": chunk})

    # Save assistant message
    msg_uuid = uuid.uuid4()
    assistant_msg = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=answer,
        message_type="mixed" if citations else "text",
        metadata_json={
            "sources": [{"doc_title": c["doc_title"], "document_id": c["document_id"]} for c in citations],
            **metadata,
        },
    )
    db.add(assistant_msg)

    # Update conversation title from first question
    if not conversation.title:
        conversation.title = request.message[:50] + ("..." if len(request.message) > 50 else "")

    await db.commit()

    done_event = MessageDoneEvent(
        message_id=msg_uuid,
        conversation_id=conversation.id,
        metadata={
            "sources": [
                {"doc_title": c["doc_title"], "document_id": c["document_id"], "score": c["score"]}
                for c in citations
            ],
            "tokens_used": metadata.get("prompt_tokens", 0) + metadata.get("completion_tokens", 0),
            "latency_ms": metadata.get("latency_ms", 0),
        },
        usage={
            "prompt_tokens": metadata.get("prompt_tokens", 0),
            "completion_tokens": metadata.get("completion_tokens", 0),
        },
    )
    yield _sse_format("message_done", done_event.model_dump())


async def _stream_query(
    request: ChatMessageRequest,
    conversation: Conversation,
    user: User,
    db: AsyncSession,
) -> AsyncGenerator[str, None]:
    """Stream Smart Query pipeline events as SSE (SQLBot-style)."""
    # Save user message
    user_msg = Message(conversation_id=conversation.id, role="user", content=request.message, message_type="text")
    db.add(user_msg)
    await db.commit()

    ds_id = request.datasource_id or (str(conversation.datasource_id) if conversation.datasource_id else None)
    if not ds_id:
        yield _sse_format("message_done", {"error": "请指定数据源"})
        return

    # Step 1: Intent recognition
    yield _sse_format("thinking", {"content": "正在分析查询意图..."})

    # Run full query pipeline with error handling
    try:
        result = await run_query_pipeline(
            question=request.message,
            datasource_id=ds_id,
            tenant_id=str(conversation.tenant_id),
            user_permissions=user.permissions,
            conversation_id=str(conversation.id),
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        error_msg = f"查询执行出错: {str(e)}"
        yield _sse_format("thinking", {"content": f"⚠️ {error_msg}"})
        yield _sse_format("message_delta", {"content": f"\n\n抱歉，{error_msg}"})
        done_event = MessageDoneEvent(
            message_id=uuid.uuid4(),
            conversation_id=conversation.id,
            metadata={"error": str(e)},
        )
        yield _sse_format("message_done", done_event.model_dump())
        return

    # Stream events matching SQLBot workflow
    detected_intent = result.get("detected_intent", {})
    yield _sse_format("query_intent", {"intent": detected_intent})

    structured_intent = result.get("structured_intent", {})
    if structured_intent and not structured_intent.get("error"):
        yield _sse_format("query_intent", {"intent": structured_intent})

    # SQL generation
    generated_sql = result.get("generated_sql", "")
    guarded_sql = result.get("guarded_sql", "")
    guard_warnings = result.get("guard_warnings", [])

    if generated_sql:
        yield _sse_format("sql_generated", {"sql": guarded_sql or generated_sql})
        if guard_warnings:
            yield _sse_format("thinking", {"content": f"SQL安全提示: {'; '.join(guard_warnings)}"})

    # Execution
    execution_result = result.get("execution_result", {})
    error_info = result.get("error_info", {})

    if error_info:
        yield _sse_format("thinking", {"content": f"⚠️ 查询出错: {error_info.get('message', '')}"})
    elif execution_result:
        yield _sse_format("sql_executing", {})

        exec_result_data = {
            "columns": execution_result.get("columns", []),
            "rows": execution_result.get("rows", []),
            "row_count": execution_result.get("row_count", 0),
            "executed_sql": execution_result.get("executed_sql", ""),
            "execution_time_ms": execution_result.get("execution_time_ms"),
        }
        yield _sse_format("result_data", exec_result_data)

        # Chart recommendation
        chart_rec = result.get("chart_recommendation", {})
        if chart_rec and chart_rec.get("type") != "none":
            yield _sse_format("chart_recommendation", chart_rec)

    # Analysis text streaming
    analysis_text = result.get("analysis_text", "")
    natural_response = result.get("natural_response", analysis_text)

    chunk_size = 40
    for i in range(0, len(natural_response), chunk_size):
        yield _sse_format("message_delta", {"content": natural_response[i : i + chunk_size]})

    # Save assistant message
    msg_uuid = uuid.uuid4()
    final_metadata = result.get("metadata", {})
    assistant_msg = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=natural_response,
        message_type="mixed" if execution_result else "text",
        metadata_json={
            "sql": guarded_sql or generated_sql,
            "chart_config": result.get("chart_recommendation", {}),
            "result_row_count": execution_result.get("row_count", 0),
            **final_metadata,
        },
    )
    db.add(assistant_msg)

    if not conversation.title:
        conversation.title = request.message[:50]

    await db.commit()

    done_event = MessageDoneEvent(
        message_id=msg_uuid,
        conversation_id=conversation.id,
        metadata={
            "sql": guarded_sql or generated_sql,
            "chart_config": result.get("chart_recommendation", {}),
            "tokens_used": final_metadata.get("prompt_tokens", 0) + final_metadata.get("completion_tokens", 0),
            "latency_ms": final_metadata.get("latency_ms", 0),
        },
        usage={
            "prompt_tokens": final_metadata.get("prompt_tokens", 0),
            "completion_tokens": final_metadata.get("completion_tokens", 0),
        },
    )
    yield _sse_format("message_done", done_event.model_dump())


@router.post("/messages")
async def chat_messages(
    body: ChatMessageRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Unified chat endpoint. Streams SSE events for real-time response.

    Engine routing:
    - engine="rag" → RAG pipeline (requires kb_id)
    - engine="query" → Smart Query / SQLBot pipeline (requires datasource_id)
    """
    # Validate engine-specific requirements
    if body.engine == "rag" and not body.kb_id:
        raise HTTPException(status_code=400, detail="RAG模式需要指定知识库(kb_id)")

    # Get or create conversation
    conversation = await _get_or_create_conversation(
        db=db,
        user=current_user,
        engine=body.engine,
        kb_id=body.kb_id,
        datasource_id=body.datasource_id,
        conversation_id=body.conversation_id,
    )

    if body.stream:
        if body.engine == "rag":
            generator = _stream_rag(body, conversation, current_user, db)
        else:
            generator = _stream_query(body, conversation, current_user, db)

        return StreamingResponse(
            generator,
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    else:
        # Non-streaming mode: collect all events and return final response
        if body.engine == "rag":
            result = await run_rag_pipeline(
                question=body.message,
                kb_id=str(body.kb_id),
                tenant_id=str(conversation.tenant_id),
                user_permissions=current_user.permissions,
            )
            content = result.get("answer", "")
        else:
            ds_id = body.datasource_id or str(conversation.datasource_id)
            result = await run_query_pipeline(
                question=body.message,
                datasource_id=ds_id,
                tenant_id=str(conversation.tenant_id),
                user_permissions=current_user.permissions,
            )
            content = result.get("natural_response", "")

        # Save messages
        user_msg = Message(conversation_id=conversation.id, role="user", content=body.message)
        asst_msg = Message(conversation_id=conversation.id, role="assistant", content=content)
        db.add_all([user_msg, asst_msg])
        await db.commit()

        from app.schemas.chat import ChatResponse
        return ChatResponse(
            message_id=uuid.uuid4(),
            conversation_id=conversation.id,
            content=content,
        )


# ── Conversation management ──

@router.get("/conversations", response_model=list[ConversationResponse])
async def list_conversations(
    params: ConversationListParams = Depends(),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import func

    query = select(Conversation).where(Conversation.user_id == current_user.id)
    if params.engine:
        query = query.where(Conversation.engine == params.engine)

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar()

    result = await db.execute(
        query.order_by(Conversation.updated_at.desc())
        .offset((params.page - 1) * params.page_size)
        .limit(params.page_size)
    )
    conversations = result.scalars().all()

    responses = []
    for conv in conversations:
        r = ConversationResponse.model_validate(conv)
        # Count messages
        msg_count = (await db.execute(select(func.count()).select_from(select(Message).where(Message.conversation_id == conv.id).subquery()))).scalar()
        r.message_count = msg_count
        responses.append(r)

    return responses


@router.delete("/conversations/{conv_id}")
async def delete_conversation(
    conv_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Conversation).where(Conversation.id == conv_id, Conversation.user_id == current_user.id))
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="会话不存在")

    await db.delete(conv)
    await db.commit()
    return {"message": "会话已删除"}