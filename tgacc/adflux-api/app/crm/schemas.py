from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from decimal import Decimal


class CRMLeadOut(BaseModel):
    id: UUID
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    position: Optional[str] = None
    source: Optional[str] = None
    status: str
    priority: str
    budget: Optional[str] = None
    authority: Optional[str] = None
    need: Optional[str] = None
    timeline: Optional[str] = None
    bant_score: int
    telegram_username: Optional[str] = None
    whatsapp: Optional[str] = None
    linkedin: Optional[str] = None
    monthly_budget: Optional[Decimal] = None
    company_size: Optional[str] = None
    industry: Optional[str] = None
    interested_platforms: list = []
    assigned_bdm_id: Optional[UUID] = None
    assigned_bdm_name: Optional[str] = None
    converted_client_id: Optional[UUID] = None
    notes: Optional[str] = None
    tags: list = []
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_contacted_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class CRMLeadCreate(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    position: Optional[str] = None
    source: Optional[str] = None
    status: str = "new"
    priority: str = "medium"
    budget: Optional[str] = None
    authority: Optional[str] = None
    need: Optional[str] = None
    timeline: Optional[str] = None
    telegram_username: Optional[str] = None
    whatsapp: Optional[str] = None
    linkedin: Optional[str] = None
    monthly_budget: Optional[Decimal] = None
    company_size: Optional[str] = None
    industry: Optional[str] = None
    interested_platforms: list = []
    assigned_bdm_id: Optional[UUID] = None
    notes: Optional[str] = None
    tags: list = []


class CRMLeadUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    position: Optional[str] = None
    source: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    budget: Optional[str] = None
    authority: Optional[str] = None
    need: Optional[str] = None
    timeline: Optional[str] = None
    telegram_username: Optional[str] = None
    whatsapp: Optional[str] = None
    linkedin: Optional[str] = None
    monthly_budget: Optional[Decimal] = None
    company_size: Optional[str] = None
    industry: Optional[str] = None
    interested_platforms: Optional[list] = None
    assigned_bdm_id: Optional[UUID] = None
    converted_client_id: Optional[UUID] = None
    notes: Optional[str] = None
    tags: Optional[list] = None


class CRMLeadBulkImport(BaseModel):
    leads: List[CRMLeadCreate]


class CRMLeadStats(BaseModel):
    total: int
    by_status: dict
    by_priority: dict
    by_source: dict
    avg_bant_score: float


class TeamTargetOut(BaseModel):
    id: UUID
    admin_id: UUID
    admin_name: Optional[str] = None
    period: str
    target_type: str
    target_value: Decimal
    achieved_value: Decimal
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class TeamTargetCreate(BaseModel):
    admin_id: UUID
    period: str
    target_type: str
    target_value: Decimal
