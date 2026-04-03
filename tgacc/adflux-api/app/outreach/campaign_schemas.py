from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ── Sequence Step ──

class SequenceStepCreate(BaseModel):
    step_order: int
    delay_hours: int = 0
    template_a: str
    template_b: Optional[str] = None
    step_type: str = "message"


class SequenceStepOut(BaseModel):
    id: uuid.UUID
    sequence_id: uuid.UUID
    step_order: int
    delay_hours: int
    template_a: str
    template_b: Optional[str] = None
    step_type: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Sequence ──

class SequenceCreate(BaseModel):
    name: str
    description: Optional[str] = None
    steps: list[SequenceStepCreate] = Field(default_factory=list)


class SequenceUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class SequenceOut(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    steps: list[SequenceStepOut] = Field(default_factory=list)

    model_config = {"from_attributes": True}


# ── Campaign ──

class CampaignCreate(BaseModel):
    name: str
    description: Optional[str] = None
    status: str = "draft"
    target_niche: Optional[str] = None
    platform: str = "telegram"
    sequence_id: Optional[uuid.UUID] = None
    daily_send_cap: int = 20
    send_window_start: int = 9
    send_window_end: int = 21
    steps: Optional[list[SequenceStepCreate]] = None


class CampaignUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    target_niche: Optional[str] = None
    platform: Optional[str] = None
    sequence_id: Optional[uuid.UUID] = None
    daily_send_cap: Optional[int] = None
    send_window_start: Optional[int] = None
    send_window_end: Optional[int] = None


class CampaignOut(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str] = None
    status: str
    target_niche: Optional[str] = None
    platform: str
    sequence_id: Optional[uuid.UUID] = None
    daily_send_cap: int
    send_window_start: int
    send_window_end: int
    total_enrolled: int
    total_sent: int
    total_replied: int
    total_converted: int
    created_at: datetime
    updated_at: datetime
    sequence: Optional[SequenceOut] = None
    lead_count: Optional[int] = None

    model_config = {"from_attributes": True}


# ── Campaign Lead ──

class CampaignLeadEnroll(BaseModel):
    tg_username: str
    tg_user_id: Optional[int] = None


class CampaignLeadOut(BaseModel):
    id: uuid.UUID
    campaign_id: uuid.UUID
    tg_username: Optional[str] = None
    tg_user_id: Optional[int] = None
    status: str
    current_step: int
    ab_variant: Optional[str] = None
    next_touch_at: Optional[datetime] = None
    assigned_account: Optional[str] = None
    enrolled_at: Optional[datetime] = None
    last_sent_at: Optional[datetime] = None
    replied_at: Optional[datetime] = None
    converted_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class LeadUploadResult(BaseModel):
    total: int
    imported: int
    duplicates: int
    errors: int


class BulkLeadItem(BaseModel):
    tg_username: str
    tg_user_id: Optional[int] = None


class BulkLeadUpload(BaseModel):
    leads: list[BulkLeadItem]


# ── AB Test ──

class ABTestOut(BaseModel):
    id: uuid.UUID
    campaign_id: uuid.UUID
    step_id: uuid.UUID
    variant_a_sent: int
    variant_a_replied: int
    variant_b_sent: int
    variant_b_replied: int
    winner: Optional[str] = None
    significance: Optional[float] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
