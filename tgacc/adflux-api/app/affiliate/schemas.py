from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from decimal import Decimal


class AffiliateCodeOut(BaseModel):
    id: UUID
    client_id: UUID
    code: str
    commission_percent: Decimal
    is_active: bool
    total_referrals: int
    total_earnings: Decimal
    created_at: datetime

    class Config:
        from_attributes = True


class AffiliateCodeCreate(BaseModel):
    code: Optional[str] = None  # auto-generate if not provided
    commission_percent: Decimal = Decimal("40")


class AffiliateCodeUpdate(BaseModel):
    commission_percent: Optional[Decimal] = None
    is_active: Optional[bool] = None


class ReferralOut(BaseModel):
    id: UUID
    affiliate_code_id: UUID
    referred_client_id: UUID
    status: str
    total_commission: Decimal
    created_at: datetime
    referred_client_name: Optional[str] = None

    class Config:
        from_attributes = True


class CommissionOut(BaseModel):
    id: UUID
    amount: Decimal
    status: str
    created_at: datetime
    paid_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CommissionStatusUpdate(BaseModel):
    status: str  # approved, paid


class AffiliateStats(BaseModel):
    total_referrals: int
    active_referrals: int
    total_earnings: Decimal
    pending_earnings: Decimal
    commission_rate: Decimal
