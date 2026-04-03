from pydantic import BaseModel
from uuid import UUID
from typing import Optional
from datetime import datetime


class TicketCreate(BaseModel):
    subject: str
    category: str = "general"
    priority: str = "medium"
    message: str  # initial message text


class TicketUpdate(BaseModel):
    status: Optional[str] = None
    priority: Optional[str] = None
    assigned_admin: Optional[UUID] = None
    category: Optional[str] = None


class TicketMessageCreate(BaseModel):
    text: str
    is_internal: bool = False


class TicketMessageOut(BaseModel):
    id: UUID
    ticket_id: UUID
    sender_type: str
    sender_id: Optional[UUID] = None
    text: str
    is_internal: bool = False
    attachments: list = []
    created_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


class TicketOut(BaseModel):
    id: UUID
    client_id: Optional[UUID] = None
    subject: str
    category: str
    priority: str
    status: str
    assigned_admin: Optional[UUID] = None
    created_by_type: str = "client"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    messages: list[TicketMessageOut] = []
    model_config = {"from_attributes": True}


class TicketListOut(BaseModel):
    id: UUID
    client_id: Optional[UUID] = None
    subject: str
    category: str
    priority: str
    status: str
    assigned_admin: Optional[UUID] = None
    created_by_type: str = "client"
    message_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    model_config = {"from_attributes": True}
