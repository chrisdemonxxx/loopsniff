"""Pydantic schemas for payment endpoints."""

from __future__ import annotations

from typing import Optional, List
from uuid import UUID
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field


class InvoiceRequest(BaseModel):
    amount: float = Field(..., gt=0, description="Ad spend amount in USD")
    plan: str = Field("starter", description="Plan tier: starter, growth, enterprise")
    niche: str = Field("other", description="Advertiser niche/vertical")
    pay_currency: str = Field("btc", description="Crypto to pay with")
    order_description: Optional[str] = None


class InvoiceResponse(BaseModel):
    invoice_id: str
    invoice_url: str
    order_id: str
    ad_spend: float
    commission: float
    total: float
    rate_pct: float
    pay_currency: str


class PaymentStatusResponse(BaseModel):
    payment_id: str
    payment_status: str
    pay_amount: Optional[float] = None
    pay_currency: Optional[str] = None
    price_amount: Optional[float] = None
    price_currency: Optional[str] = None
    order_id: Optional[str] = None


class CommissionBreakdown(BaseModel):
    base_rate: float
    high_risk: float
    volume_discount: float
    raw_rate: float
    floor_applied: bool
    effective_rate: float
    plan: str
    niche: str
    amount: float
    commission: float
    total: float


class IPNPayload(BaseModel):
    payment_id: int
    payment_status: str
    pay_address: Optional[str] = None
    price_amount: Optional[float] = None
    price_currency: Optional[str] = None
    pay_amount: Optional[float] = None
    pay_currency: Optional[str] = None
    order_id: Optional[str] = None
    order_description: Optional[str] = None

    class Config:
        extra = "allow"


# ── Stripe schemas ──

class StripeCreateIntentRequest(BaseModel):
    amount: Decimal = Field(..., gt=0, description="Amount in USD to top up")
    currency: str = Field("usd", description="Three-letter ISO currency code")
    payment_method_id: Optional[str] = Field(None, description="Stripe payment method ID to use")

class StripeIntentResponse(BaseModel):
    client_secret: str
    payment_intent_id: str
    amount: Decimal
    currency: str
    status: str

class StripePaymentMethodOut(BaseModel):
    id: str
    brand: str
    last4: str
    exp_month: int
    exp_year: int
    is_default: bool = False

class StripeAddMethodRequest(BaseModel):
    payment_method_id: str = Field(..., description="Stripe payment method token from client-side")

class StripeCreateSubscriptionRequest(BaseModel):
    plan_id: UUID = Field(..., description="Internal subscription plan ID")
    payment_method_id: Optional[str] = Field(None, description="Stripe payment method to use")
    interval: str = Field("monthly", description="Billing interval: monthly, semiannual, annual")

class StripeSubscriptionResponse(BaseModel):
    subscription_id: str
    plan_name: str
    status: str
    current_period_end: Optional[datetime] = None
    client_secret: Optional[str] = None

class StripeCancelSubscriptionRequest(BaseModel):
    subscription_id: str
    cancel_at_period_end: bool = True

class StripeInvoiceOut(BaseModel):
    id: str
    amount_due: int
    amount_paid: int
    currency: str
    status: str
    hosted_invoice_url: Optional[str] = None
    created: datetime
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None


# ── Bank transfer schemas ──

class BankTransferDepositRequest(BaseModel):
    amount: Decimal = Field(..., gt=0, description="Deposit amount in USD")
    currency: str = "USD"

class BankTransferDepositResponse(BaseModel):
    request_id: UUID
    amount: Decimal
    currency: str
    reference_code: str
    status: str
    bank_details: dict
    created_at: datetime

class BankTransferRequestOut(BaseModel):
    id: UUID
    client_id: UUID
    amount: Decimal
    currency: str
    reference_code: str
    status: str
    admin_note: Optional[str] = None
    created_at: datetime
    confirmed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}

class BankTransferConfirmRequest(BaseModel):
    admin_note: Optional[str] = None

class BankTransferRejectRequest(BaseModel):
    reason: str = Field(..., description="Reason for rejection")
