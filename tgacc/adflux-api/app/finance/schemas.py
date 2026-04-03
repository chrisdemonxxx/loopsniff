from pydantic import BaseModel
from typing import Optional
from decimal import Decimal
from datetime import datetime


class RevenueOverview(BaseModel):
    total_revenue: Decimal
    total_commission: Decimal
    total_ad_spend: Decimal
    transaction_count: int


class LTVData(BaseModel):
    client_id: str
    client_name: str
    total_spend: Decimal
    total_commission: Decimal
    transaction_count: int
    avg_transaction: Decimal


class CommissionBreakdownItem(BaseModel):
    plan: str
    total_commission: Decimal
    transaction_count: int
    avg_rate: Optional[Decimal] = None


# ── Deposits ──

class DepositOut(BaseModel):
    id: str
    wallet_id: str
    client_id: str
    client_name: str
    type: str
    amount: Decimal
    fee: Decimal
    net_amount: Decimal
    currency: str
    payment_method: Optional[str] = None
    payment_reference: Optional[str] = None
    status: str
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class DepositRejectBody(BaseModel):
    reason: str


# ── Adjustments ──

class AdjustmentCreate(BaseModel):
    client_id: str
    type: str  # credit or debit
    amount: Decimal
    reason: str


class AdjustmentOut(BaseModel):
    id: str
    client_id: str
    client_name: str
    type: str
    amount: Decimal
    reason: str
    created_by: str
    created_at: Optional[datetime] = None


# ── Revenue Breakdown ──

class RevenueBreakdownItem(BaseModel):
    source: str
    amount: Decimal
    count: int


# ── Alerts ──

class LowBalanceAlert(BaseModel):
    client_id: str
    client_name: str
    wallet_balance: Decimal
    currency: str


# ── Summary ──

class FinanceSummary(BaseModel):
    total_deposits: Decimal
    completed_deposits: int
    pending_deposits: int
    failed_deposits: int
    total_revenue: Decimal
    active_subscriptions: int
    subscription_mrr: Decimal
    total_adjustments: int
