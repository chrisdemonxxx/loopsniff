from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from decimal import Decimal


class PlanOut(BaseModel):
    id: UUID
    name: str
    slug: str
    description: Optional[str]
    price_monthly: Decimal
    price_semiannual: Optional[Decimal]
    price_annual: Optional[Decimal]
    platforms: list
    max_accounts: Optional[int]
    cashback_percent: Decimal
    features: list
    is_active: bool
    sort_order: int

    model_config = {"from_attributes": True}


class PlanCreate(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None
    price_monthly: Decimal
    price_semiannual: Optional[Decimal] = None
    price_annual: Optional[Decimal] = None
    platforms: list = []
    max_accounts: Optional[int] = None
    cashback_percent: Decimal = Decimal("0")
    features: list = []
    is_active: bool = True
    sort_order: int = 0


class PlanUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price_monthly: Optional[Decimal] = None
    price_semiannual: Optional[Decimal] = None
    price_annual: Optional[Decimal] = None
    platforms: Optional[list] = None
    max_accounts: Optional[int] = None
    cashback_percent: Optional[Decimal] = None
    features: Optional[list] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None


class SubscriptionOut(BaseModel):
    id: UUID
    client_id: UUID
    plan: str
    price: Optional[Decimal]
    interval_type: str
    status: str
    started_at: datetime
    next_bill: Optional[datetime]
    cancelled_at: Optional[datetime]

    model_config = {"from_attributes": True}


class SubscribeRequest(BaseModel):
    plan_slug: str
    interval: str = "monthly"  # monthly, semiannual, annual


class CancelRequest(BaseModel):
    reason: Optional[str] = None
