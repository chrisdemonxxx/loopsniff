from pydantic import BaseModel
from uuid import UUID
from typing import Optional
from datetime import datetime


class ChatSessionOut(BaseModel):
    id: UUID
    client_id: Optional[UUID] = None
    channel: Optional[str] = None
    status: Optional[str] = None
    subject: Optional[str] = "Support Chat"
    agent_type: Optional[str] = "ai"
    assigned_admin: Optional[UUID] = None
    created_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    last_message: Optional[str] = None
    last_message_time: Optional[datetime] = None
    client_name: Optional[str] = None

    model_config = {"from_attributes": True}


class ChatMessageOut(BaseModel):
    id: UUID
    session_id: Optional[UUID] = None
    sender: Optional[str] = None
    text: str
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ChatMessageIn(BaseModel):
    text: str
    sender: str = "user"


class EscalateRequest(BaseModel):
    session_id: UUID
    reason: str = "Client requested human agent"


class ConversationCreate(BaseModel):
    subject: str = "Support Chat"
    message: Optional[str] = None


class ConversationWithMessages(ChatSessionOut):
    messages: list[ChatMessageOut] = []


class AssignRequest(BaseModel):
    admin_id: UUID


class UnreadCountOut(BaseModel):
    unread: int
