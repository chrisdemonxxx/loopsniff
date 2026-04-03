from pydantic import BaseModel
from uuid import UUID
from typing import Optional
from datetime import datetime


class OrderCreate(BaseModel):
    client_id: Optional[UUID] = None
    order_type: str
    amount: float
    currency: str = "USD"
    account_id: Optional[UUID] = None
    details: dict = {}
    notes: Optional[str] = None


class OrderUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None
    details: Optional[dict] = None


class OrderOut(BaseModel):
    id: UUID
    client_id: UUID
    order_type: str
    status: str
    amount: float
    currency: str
    account_id: Optional[UUID] = None
    transaction_id: Optional[UUID] = None
    details: dict = {}
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class SubscriptionOut(BaseModel):
    id: UUID
    client_id: Optional[UUID] = None
    plan: str
    price: Optional[float] = None
    interval: str = "monthly"
    status: str
    started_at: Optional[datetime] = None
    next_billing_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class SubscriptionCreate(BaseModel):
    client_id: Optional[UUID] = None
    plan: str
    price: float
    interval: str = "monthly"


class SubscriptionUpdate(BaseModel):
    plan: Optional[str] = None
    price: Optional[float] = None
    status: Optional[str] = None
    interval: Optional[str] = None
