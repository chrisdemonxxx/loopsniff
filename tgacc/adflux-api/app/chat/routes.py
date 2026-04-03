import uuid
import json
import asyncio
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional

from app.database import get_db, async_session
from app.models import ChatSession, ChatMessage, Client
from app.auth.dependencies import get_current_user, require_admin
from app.auth.jwt import decode_token
from app.chat.schemas import (
    ChatSessionOut, ChatMessageOut, EscalateRequest,
    ConversationCreate, ConversationWithMessages, AssignRequest, UnreadCountOut,
)
from app.chat.ai_manager import get_ai_response
from app.chat.account_manager import get_account_manager_response, maybe_create_ticket, get_client_context
from app.chat.escalation import escalate_all

log = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["Chat"])


async def _enrich_session(s: ChatSession, db: AsyncSession) -> ChatSessionOut:
    """Add last_message, last_message_time, and client_name to a session."""
    last_msg_result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == s.id)
        .order_by(ChatMessage.created_at.desc())
        .limit(1)
    )
    last_msg = last_msg_result.scalar_one_or_none()
    out = ChatSessionOut.model_validate(s)
    if last_msg:
        out.last_message = last_msg.text[:100] if last_msg.text else None
        out.last_message_time = last_msg.created_at
    if s.client_id:
        client_result = await db.execute(select(Client.name).where(Client.id == s.client_id))
        client_name = client_result.scalar_one_or_none()
        out.client_name = client_name
    return out


@router.get("/sessions", response_model=list[ChatSessionOut])
async def list_sessions(
    client_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    skip: int = 0, limit: int = 50,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(ChatSession)
    if client_id:
        stmt = stmt.where(ChatSession.client_id == uuid.UUID(client_id))
    if status:
        stmt = stmt.where(ChatSession.status == status)
    stmt = stmt.order_by(ChatSession.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    sessions = result.scalars().all()
    return [await _enrich_session(s, db) for s in sessions]


# ── Conversation REST endpoints ──────────────────────────────────────────


@router.post("/conversations", response_model=ChatSessionOut, status_code=201)
async def create_conversation(
    body: ConversationCreate,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Start a new support conversation (client-side)."""
    client_id = user.get("client_id")
    session = ChatSession(
        id=uuid.uuid4(),
        client_id=uuid.UUID(client_id) if client_id else None,
        channel="rest",
        status="open",
    )
    db.add(session)
    await db.flush()

    if body.message:
        msg = ChatMessage(
            session_id=session.id,
            sender="user",
            text=body.message,
        )
        db.add(msg)
        await db.flush()

    await db.commit()
    await db.refresh(session)
    return await _enrich_session(session, db)


@router.get("/conversations", response_model=list[ChatSessionOut])
async def list_conversations(
    status: Optional[str] = Query(None, description="Filter: open, closed, escalated, ai"),
    skip: int = 0, limit: int = 50,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List conversations. Clients see only their own; admins see all."""
    stmt = select(ChatSession)
    if user["user_type"] != "admin":
        client_id = user.get("client_id")
        if client_id:
            stmt = stmt.where(ChatSession.client_id == uuid.UUID(client_id))
        else:
            return []
    if status:
        stmt = stmt.where(ChatSession.status == status)
    stmt = stmt.order_by(ChatSession.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    sessions = result.scalars().all()
    return [await _enrich_session(s, db) for s in sessions]


@router.get("/conversations/{conversation_id}", response_model=ConversationWithMessages)
async def get_conversation(
    conversation_id: uuid.UUID,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a conversation with its messages."""
    result = await db.execute(select(ChatSession).where(ChatSession.id == conversation_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if user["user_type"] != "admin":
        client_id = user.get("client_id")
        if not client_id or str(session.client_id) != client_id:
            raise HTTPException(status_code=403, detail="Access denied")

    msgs_result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session.id)
        .order_by(ChatMessage.created_at.asc())
    )
    messages = msgs_result.scalars().all()

    out = await _enrich_session(session, db)
    conv = ConversationWithMessages(**out.model_dump())
    conv.messages = [ChatMessageOut.model_validate(m) for m in messages]
    return conv


@router.post("/conversations/{conversation_id}/messages", response_model=ChatMessageOut, status_code=201)
async def send_message(
    conversation_id: uuid.UUID,
    body: dict,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Send a message in a conversation."""
    result = await db.execute(select(ChatSession).where(ChatSession.id == conversation_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if user["user_type"] != "admin":
        client_id = user.get("client_id")
        if not client_id or str(session.client_id) != client_id:
            raise HTTPException(status_code=403, detail="Access denied")

    sender = "admin" if user["user_type"] == "admin" else "user"
    text = body.get("text", "")
    if not text:
        raise HTTPException(status_code=400, detail="Message text is required")

    msg = ChatMessage(
        session_id=session.id,
        sender=sender,
        text=text,
    )
    db.add(msg)

    if session.status == "closed":
        session.status = "open"
        session.closed_at = None

    await db.commit()
    await db.refresh(msg)
    return msg


@router.put("/conversations/{conversation_id}/close", response_model=ChatSessionOut)
async def close_conversation(
    conversation_id: uuid.UUID,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Close a conversation."""
    result = await db.execute(select(ChatSession).where(ChatSession.id == conversation_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Conversation not found")

    session.status = "closed"
    session.closed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(session)
    return await _enrich_session(session, db)


@router.put("/conversations/{conversation_id}/assign", response_model=ChatSessionOut)
async def assign_conversation(
    conversation_id: uuid.UUID,
    body: AssignRequest,
    user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Admin: assign a conversation to a team member."""
    result = await db.execute(select(ChatSession).where(ChatSession.id == conversation_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Conversation not found")

    session.assigned_admin = body.admin_id
    if session.status == "ai":
        session.status = "open"
    await db.commit()
    await db.refresh(session)
    return await _enrich_session(session, db)


@router.get("/unread-count", response_model=UnreadCountOut)
async def get_unread_count(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get count of conversations with unread messages."""
    if user["user_type"] == "admin":
        # Admin: count open conversations where last message is from a user
        stmt = (
            select(func.count())
            .select_from(ChatSession)
            .where(ChatSession.status.in_(["open", "ai", "escalated"]))
        )
    else:
        client_id = user.get("client_id")
        if not client_id:
            return UnreadCountOut(unread=0)
        # Client: count own conversations where last message is from admin/ai
        stmt = (
            select(func.count())
            .select_from(ChatSession)
            .where(
                ChatSession.client_id == uuid.UUID(client_id),
                ChatSession.status.in_(["open", "ai", "escalated"]),
            )
        )
    result = await db.execute(stmt)
    count = result.scalar() or 0
    return UnreadCountOut(unread=count)


@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessageOut])
async def get_messages(
    session_id: uuid.UUID,
    skip: int = 0, limit: int = 100,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
        .offset(skip).limit(limit)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/escalate")
async def escalate(data: EscalateRequest, user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ChatSession).where(ChatSession.id == data.session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    session.status = "escalated"
    await db.flush()
    await db.commit()
    await escalate_all(
        f"Chat session {session.id} escalated.\nReason: {data.reason}\nClient ID: {session.client_id}",
        title="Chat Escalation",
    )
    return {"detail": "Escalated to human agents"}


@router.websocket("/ws/chat/{session_id}")
async def ws_chat(websocket: WebSocket, session_id: str):
    # S5: Validate JWT token before accepting connection
    token = websocket.query_params.get("token")
    ws_user = None
    if token:
        try:
            ws_user = decode_token(token)
        except Exception:
            await websocket.close(code=4001, reason="Invalid token")
            return
    if not ws_user:
        await websocket.close(code=4001, reason="Authentication required")
        return

    await websocket.accept()
    sid = uuid.UUID(session_id)
    client_info = None

    async with async_session() as db:
        result = await db.execute(select(ChatSession).where(ChatSession.id == sid))
        chat_session = result.scalar_one_or_none()
        if not chat_session:
            # R1: Set client_id from JWT when creating new sessions
            client_id = ws_user.get("client_id")
            chat_session = ChatSession(
                id=sid, channel="websocket", status="ai",
                client_id=uuid.UUID(client_id) if client_id else None,
            )
            db.add(chat_session)
            await db.commit()

        if chat_session.client_id:
            client_info = await get_client_context(str(chat_session.client_id), db)

    try:
        while True:
            data = await asyncio.wait_for(websocket.receive_text(), timeout=300)
            try:
                msg_data = json.loads(data)
                user_text = msg_data.get("text", data)
                mode = msg_data.get("mode", "support")  # "support" or "account_manager"
            except json.JSONDecodeError:
                user_text = data
                mode = "support"

            # Save user message
            async with async_session() as db:
                user_msg = ChatMessage(
                    session_id=sid, sender="user", text=user_text,
                )
                db.add(user_msg)
                await db.commit()

                # Get recent context for AI
                result = await db.execute(
                    select(ChatMessage)
                    .where(ChatMessage.session_id == sid)
                    .order_by(ChatMessage.created_at.desc())
                    .limit(10)
                )
                recent = result.scalars().all()
                context = [
                    {"role": "assistant" if m.sender == "ai" else "user", "content": m.text}
                    for m in reversed(recent)
                ]

            # Get AI response based on mode
            if mode == "account_manager":
                ai_text = await get_account_manager_response(user_text, context, client_info)
            else:
                ai_text = await get_ai_response(user_text, context)

            # Check if AI wants to create a ticket (account manager mode)
            ticket_info = None
            if mode == "account_manager" and "[TICKET_CREATE:" in ai_text:
                async with async_session() as db:
                    conversation_summary = " | ".join(
                        f"{c['role']}: {c['content'][:100]}" for c in context[-6:]
                    )
                    client_id = str(chat_session.client_id) if chat_session.client_id else None
                    if client_id:
                        ticket_info = await maybe_create_ticket(ai_text, client_id, conversation_summary, db)
                        await db.commit()
                # Clean the marker from the response shown to client
                if "[TICKET_CREATE:" in ai_text:
                    marker_start = ai_text.index("[TICKET_CREATE:")
                    marker_end = ai_text.index("]", marker_start) + 1
                    ai_text = ai_text[:marker_start].strip() + ai_text[marker_end:].strip()

            # Save AI message
            async with async_session() as db:
                ai_msg = ChatMessage(
                    session_id=sid, sender="ai", text=ai_text,
                )
                db.add(ai_msg)
                await db.commit()

            response = {
                "sender": "ai",
                "text": ai_text,
                "session_id": session_id,
            }
            if ticket_info:
                response["ticket_created"] = ticket_info

            await websocket.send_text(json.dumps(response))

    except WebSocketDisconnect:
        log.info("WebSocket disconnected: session=%s", session_id)
    except asyncio.TimeoutError:
        log.info("WebSocket timeout: session=%s", session_id)
        try:
            await websocket.close(code=1000, reason="Idle timeout")
        except Exception as e:
            log.debug("WebSocket cleanup error on timeout: %s", e)
    except Exception as e:
        log.exception("WebSocket error: %s", e)
        try:
            await websocket.close()
        except Exception as exc:
            log.debug("WebSocket cleanup error: %s", exc)
