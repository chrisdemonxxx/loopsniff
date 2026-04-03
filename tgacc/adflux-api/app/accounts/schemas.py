from pydantic import BaseModel
from uuid import UUID
from typing import Optional
from datetime import datetime
from decimal import Decimal


class AccountCreate(BaseModel):
    client_id: UUID
    platform: str
    account_id: Optional[str] = None
    name: Optional[str] = None
    daily_limit: Optional[Decimal] = None


class AccountUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None
    daily_limit: Optional[Decimal] = None
    balance: Optional[Decimal] = None


class AccountOut(BaseModel):
    id: UUID
    client_id: Optional[UUID] = None
    platform: str
    account_id: Optional[str] = None
    name: Optional[str] = None
    status: Optional[str] = None
    balance: Optional[Decimal] = None
    total_spend: Optional[Decimal] = None
    daily_limit: Optional[Decimal] = None
    created_at: Optional[datetime] = None
    banned_at: Optional[datetime] = None
    ban_reason: Optional[str] = None
    replaced_by: Optional[UUID] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class BanRequest(BaseModel):
    reason: str


class FundTransferRequest(BaseModel):
    new_account_id: UUID
    amount: Optional[Decimal] = None  # None = transfer full balance
