from pydantic import BaseModel
from uuid import UUID
from typing import Optional
from datetime import datetime
from decimal import Decimal


class ClientCreate(BaseModel):
    name: str
    company: Optional[str] = None
    tg_username: Optional[str] = None
    tg_user_id: Optional[int] = None
    email: Optional[str] = None
    plan: str = "starter"
    niche: Optional[str] = None
    monthly_spend_est: Optional[Decimal] = None
    notes: Optional[str] = None


class ClientUpdate(BaseModel):
    name: Optional[str] = None
    company: Optional[str] = None
    tg_username: Optional[str] = None
    tg_user_id: Optional[int] = None
    email: Optional[str] = None
    plan: Optional[str] = None
    status: Optional[str] = None
    niche: Optional[str] = None
    monthly_spend_est: Optional[Decimal] = None
    notes: Optional[str] = None


class ClientOut(BaseModel):
    id: UUID
    name: str
    company: Optional[str] = None
    tg_username: Optional[str] = None
    tg_user_id: Optional[int] = None
    email: Optional[str] = None
    plan: Optional[str] = None
    status: Optional[str] = None
    niche: Optional[str] = None
    monthly_spend_est: Optional[Decimal] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ClientStats(BaseModel):
    total_clients: int
    active_clients: int
    total_accounts: int
    total_spend: Decimal
