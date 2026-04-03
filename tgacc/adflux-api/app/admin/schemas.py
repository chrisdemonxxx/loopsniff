from pydantic import BaseModel
from uuid import UUID
from typing import Optional
from datetime import datetime


class DashboardStats(BaseModel):
    total_clients: int
    active_clients: int
    total_accounts: int
    active_accounts: int
    banned_accounts: int
    total_revenue: float
    pending_transactions: int
    outreach_leads: int


class AuditLogOut(BaseModel):
    id: UUID
    admin_id: Optional[UUID] = None
    action: str
    entity_type: Optional[str] = None
    entity_id: Optional[UUID] = None
    details: Optional[dict] = None
    ip_address: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class AdminUserOut(BaseModel):
    id: UUID
    email: str
    name: str
    role: Optional[str] = None
    is_active: Optional[bool] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class AdminUserUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
