from pydantic import BaseModel
from uuid import UUID
from typing import Optional
from datetime import datetime


class OutreachLeadOut(BaseModel):
    id: UUID
    tg_username: Optional[str] = None
    tg_user_id: Optional[int] = None
    source: Optional[str] = None
    bant_score: Optional[int] = None
    stage: Optional[str] = None
    assigned_account: Optional[str] = None
    last_message_at: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class OutreachLeadUpdate(BaseModel):
    stage: Optional[str] = None
    bant_score: Optional[int] = None
    notes: Optional[str] = None
    assigned_account: Optional[str] = None


class OutreachLeadCreate(BaseModel):
    tg_username: Optional[str] = None
    tg_user_id: Optional[int] = None
    source: Optional[str] = None
    bant_score: int = 0
    stage: str = "new"
    assigned_account: Optional[str] = None
    notes: Optional[str] = None


class FunnelStats(BaseModel):
    total: int
    new: int
    contacted: int
    qualified: int
    proposal: int
    converted: int
    lost: int
