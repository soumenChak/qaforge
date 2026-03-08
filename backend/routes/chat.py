"""
QAForge -- Quinn Chat Routes.

Provides chat session management and SSE-streamed message responses.
Quinn is the AI assistant embedded in the QAForge UI.
"""

import json
import logging
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from db_models import ChatMessage, ChatSession, Project, User
from db_session import get_db
from dependencies import get_current_user
from models import (
    ChatMessageResponse,
    ChatSendMessageRequest,
    ChatSessionCreate,
    ChatSessionDetailResponse,
    ChatSessionResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()

MAX_HISTORY_MESSAGES = 50  # sliding window for LLM context
MAX_TOOL_ITERATIONS = 5


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _get_project_or_404(project_id: uuid.UUID, db: Session) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _get_session_or_404(
    session_id: uuid.UUID, project_id: uuid.UUID, user: User, db: Session
) -> ChatSession:
    session = (
        db.query(ChatSession)
        .filter(
            ChatSession.id == session_id,
            ChatSession.project_id == project_id,
            ChatSession.user_id == user.id,
        )
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return session


# ---------------------------------------------------------------------------
# Session CRUD
# ---------------------------------------------------------------------------
@router.post("/{project_id}/chat/sessions", response_model=ChatSessionResponse)
def create_session(
    project_id: uuid.UUID,
    body: ChatSessionCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new Quinn chat session for a project."""
    project = _get_project_or_404(project_id, db)

    session = ChatSession(
        project_id=project.id,
        user_id=user.id,
        title=body.title,
    )
    db.add(session)
    db.flush()

    resp = ChatSessionResponse.model_validate(session)
    resp.message_count = 0
    db.commit()
    return resp


@router.get("/{project_id}/chat/sessions", response_model=List[ChatSessionResponse])
def list_sessions(
    project_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List chat sessions for the current user in a project."""
    _get_project_or_404(project_id, db)

    sessions = (
        db.query(ChatSession)
        .filter(
            ChatSession.project_id == project_id,
            ChatSession.user_id == user.id,
            ChatSession.status == "active",
        )
        .order_by(ChatSession.updated_at.desc())
        .all()
    )

    result = []
    for s in sessions:
        resp = ChatSessionResponse.model_validate(s)
        resp.message_count = (
            db.query(sa_func.count(ChatMessage.id))
            .filter(ChatMessage.session_id == s.id)
            .scalar()
            or 0
        )
        result.append(resp)
    return result


@router.get(
    "/{project_id}/chat/sessions/{session_id}",
    response_model=ChatSessionDetailResponse,
)
def get_session(
    project_id: uuid.UUID,
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a chat session with all messages."""
    session = _get_session_or_404(session_id, project_id, user, db)
    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session.id)
        .order_by(ChatMessage.created_at)
        .all()
    )
    return ChatSessionDetailResponse(
        id=session.id,
        project_id=session.project_id,
        user_id=session.user_id,
        title=session.title,
        status=session.status,
        created_at=session.created_at,
        updated_at=session.updated_at,
        messages=[ChatMessageResponse.model_validate(m) for m in messages],
    )


@router.delete("/{project_id}/chat/sessions/{session_id}")
def delete_session(
    project_id: uuid.UUID,
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete (archive) a chat session."""
    session = _get_session_or_404(session_id, project_id, user, db)
    session.status = "archived"
    db.commit()
    return {"message": "Session archived"}


# ---------------------------------------------------------------------------
# Send Message → SSE Stream
# ---------------------------------------------------------------------------
@router.post("/{project_id}/chat/sessions/{session_id}/messages")
async def send_message(
    project_id: uuid.UUID,
    session_id: uuid.UUID,
    body: ChatSendMessageRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Send a message and get a streaming SSE response from Quinn."""
    project = _get_project_or_404(project_id, db)
    session = _get_session_or_404(session_id, project_id, user, db)

    # Save user message
    user_msg = ChatMessage(
        session_id=session.id,
        role="user",
        content=body.content,
    )
    db.add(user_msg)
    db.flush()

    # Auto-title session from first user message
    if not session.title:
        session.title = body.content[:100].strip()

    # Build message history for LLM
    history_msgs = (
        db.query(ChatMessage)
        .filter(
            ChatMessage.session_id == session.id,
            ChatMessage.role.in_(["user", "assistant"]),
        )
        .order_by(ChatMessage.created_at.desc())
        .limit(MAX_HISTORY_MESSAGES)
        .all()
    )
    history_msgs.reverse()

    llm_messages = [{"role": m.role, "content": m.content} for m in history_msgs]

    db.commit()

    return StreamingResponse(
        _stream_quinn_response(project, session, llm_messages, user, db),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


def _sse_event(event: str, data: dict) -> str:
    """Format a single SSE event."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def _stream_quinn_response(
    project: Project,
    session: ChatSession,
    llm_messages: list,
    user: User,
    db: Session,
):
    """Generator that yields SSE events for Quinn's response."""
    from core.quinn_prompt import build_quinn_system_prompt
    from core.llm_provider import get_llm_provider
    from dependencies import track_cost

    try:
        system_prompt = build_quinn_system_prompt(project, db)
        llm = get_llm_provider()

        # Phase 2: tool calling loop
        tool_calling_enabled = False
        try:
            from core.quinn_tools import QUINN_TOOLS, execute_tool
            tool_calling_enabled = bool(QUINN_TOOLS)
        except ImportError:
            pass

        if tool_calling_enabled:
            # Tool-calling orchestrator loop
            for iteration in range(MAX_TOOL_ITERATIONS):
                try:
                    result = llm.complete_with_tools(
                        system=system_prompt,
                        messages=llm_messages,
                        tools=QUINN_TOOLS,
                        max_tokens=2048,
                        temperature=0.7,
                        model=llm.smart_model,
                    )
                except AttributeError:
                    # Provider doesn't support tool calling, fall through to streaming
                    tool_calling_enabled = False
                    break

                if not result.tool_calls:
                    # No tool calls -- stream final text response
                    if result.text:
                        # Yield the text in chunks for a streaming feel
                        words = result.text.split(" ")
                        for i, word in enumerate(words):
                            token = word + (" " if i < len(words) - 1 else "")
                            yield _sse_event("token", {"text": token})

                        # Save assistant message
                        assistant_msg = ChatMessage(
                            session_id=session.id,
                            role="assistant",
                            content=result.text,
                            metadata_={
                                "tokens_in": result.tokens_in,
                                "tokens_out": result.tokens_out,
                                "model": result.model,
                                "provider": result.provider,
                            },
                        )
                        db.add(assistant_msg)
                        db.flush()

                        track_cost(
                            db, user.id, project.id, "llm",
                            provider=result.provider, model=result.model,
                            tokens_in=result.tokens_in, tokens_out=result.tokens_out,
                        )

                        yield _sse_event("done", {
                            "message_id": str(assistant_msg.id),
                            "tokens_in": result.tokens_in,
                            "tokens_out": result.tokens_out,
                        })
                        db.commit()
                        return
                    break

                # Execute each tool call
                for tc in result.tool_calls:
                    yield _sse_event("tool_call", {
                        "tool": tc.name,
                        "input": tc.input,
                    })

                    try:
                        tool_result = execute_tool(
                            tc.name, project.id, db, user, **tc.input
                        )
                    except Exception as e:
                        tool_result = {"error": str(e)}

                    yield _sse_event("tool_result", {
                        "tool": tc.name,
                        "result": tool_result,
                    })

                    # Save tool messages
                    db.add(ChatMessage(
                        session_id=session.id,
                        role="tool_call",
                        content=json.dumps({"tool": tc.name, "input": tc.input}),
                        metadata_={"tool_call_id": tc.id},
                    ))
                    db.add(ChatMessage(
                        session_id=session.id,
                        role="tool_result",
                        content=json.dumps(tool_result) if isinstance(tool_result, (dict, list)) else str(tool_result),
                        metadata_={"tool": tc.name, "tool_call_id": tc.id},
                    ))
                    db.flush()

                    # Add to LLM context for next iteration
                    llm_messages.append({
                        "role": "assistant",
                        "content": f"[Tool call: {tc.name}({json.dumps(tc.input)})]",
                    })
                    llm_messages.append({
                        "role": "user",
                        "content": f"[Tool result for {tc.name}]: {json.dumps(tool_result) if isinstance(tool_result, (dict, list)) else str(tool_result)}",
                    })

            # If we exhausted tool iterations or broke out, fall through to streaming

        if not tool_calling_enabled:
            # Pure streaming (Phase 1 path, or fallback when tools not supported)
            full_text = ""
            token_count = 0
            for chunk in llm.stream(
                system=system_prompt,
                messages=llm_messages,
                max_tokens=2048,
                temperature=0.7,
                model=llm.smart_model,
            ):
                full_text += chunk
                token_count += 1
                yield _sse_event("token", {"text": chunk})

            # Save assistant message
            assistant_msg = ChatMessage(
                session_id=session.id,
                role="assistant",
                content=full_text,
                metadata_={
                    "model": getattr(llm, "smart_model", "unknown"),
                    "provider": llm.provider_name,
                    "streamed": True,
                },
            )
            db.add(assistant_msg)
            db.flush()

            yield _sse_event("done", {
                "message_id": str(assistant_msg.id),
                "tokens_in": 0,
                "tokens_out": token_count,
            })
            db.commit()

    except Exception as e:
        logger.error("Quinn streaming error: %s", e, exc_info=True)
        yield _sse_event("error", {"detail": str(e)})
