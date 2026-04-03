from uuid import UUID
from decimal import Decimal
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional
import logging

from app.database import get_db
from app.models import Transaction, Client, AdAccount, RevenueLedger
from app.auth.dependencies import get_current_user, require_admin
from app.payments.commission import calculate_topup_cost, get_commission_breakdown
from app.payments.nowpayments import NOWPaymentsClient
from app.payments.schemas import (
    InvoiceRequest, InvoiceResponse, PaymentStatusResponse,
    CommissionBreakdown, IPNPayload,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/payments", tags=["payments"])

_client: NOWPaymentsClient | None = None


def _get_client() -> NOWPaymentsClient:
    global _client
    if _client is None:
        _client = NOWPaymentsClient()
    return _client


# ── Transaction schemas for DB-backed endpoints ──

from pydantic import BaseModel


class TopupRequest(BaseModel):
    client_id: UUID
    account_id: UUID
    ad_amount: float
    pay_currency: str = "btc"


class TopupResponse(BaseModel):
    transaction_id: UUID
    ad_amount: float
    commission: float
    total: float
    commission_rate: float
    invoice: Optional[dict] = None


class TransactionOut(BaseModel):
    id: UUID
    client_id: Optional[UUID] = None
    type: Optional[str] = None
    ad_amount: Optional[Decimal] = None
    commission: Optional[Decimal] = None
    crypto_amount: Optional[Decimal] = None
    crypto_currency: Optional[str] = None
    nowpay_id: Optional[str] = None
    status: Optional[str] = None
    account_id: Optional[UUID] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    confirmed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


@router.post("/topup", response_model=TopupResponse)
async def topup(data: TopupRequest, user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Client).where(Client.id == data.client_id))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # Get cumulative confirmed spend for volume discount
    cum_spend = (await db.execute(
        select(func.coalesce(func.sum(Transaction.ad_amount), 0))
        .where(Transaction.client_id == data.client_id, Transaction.status == "confirmed")
    )).scalar() or 0

    cost = calculate_topup_cost(data.ad_amount, client.plan or "starter", client.niche or "other")
    breakdown = get_commission_breakdown(float(cum_spend), client.plan or "starter", client.niche or "other")
    rate = breakdown["effective_rate"]
    commission = round(data.ad_amount * rate, 2)
    total = round(data.ad_amount + commission, 2)

    txn = Transaction(
        client_id=data.client_id, type="topup",
        ad_amount=Decimal(str(data.ad_amount)), commission=Decimal(str(commission)),
        status="pending", account_id=data.account_id,
    )
    db.add(txn)
    await db.flush()
    await db.commit()

    invoice = None
    try:
        np = _get_client()
        invoice = await np.create_invoice(
            price_amount=total, pay_currency=data.pay_currency,
            order_id=str(txn.id),
            order_description=f"AdFlux topup for {client.name}",
        )
        if invoice.get("id"):
            txn.nowpay_id = str(invoice["id"])
            await db.flush()
            await db.commit()
    except Exception as e:
        log.error("Failed to create NOWPayments invoice: %s", e)

    return TopupResponse(
        transaction_id=txn.id, ad_amount=data.ad_amount,
        commission=commission, total=total, commission_rate=round(rate * 100, 2),
        invoice=invoice,
    )


@router.post("/invoice", response_model=InvoiceResponse)
async def create_invoice(req: InvoiceRequest):
    cost = calculate_topup_cost(req.amount, req.plan, req.niche)
    np = _get_client()
    result = await np.create_invoice(
        price_amount=cost["total"], price_currency="usd",
        pay_currency=req.pay_currency,
        order_description=req.order_description or f"AdFlux {req.plan.title()} — ${req.amount} top-up",
    )
    if "id" not in result:
        raise HTTPException(status_code=502, detail="Payment gateway error")
    return InvoiceResponse(
        invoice_id=str(result["id"]), invoice_url=result.get("invoice_url", ""),
        order_id=result.get("order_id", ""), ad_spend=cost["ad_spend"],
        commission=cost["commission"], total=cost["total"],
        rate_pct=cost["rate_pct"], pay_currency=req.pay_currency,
    )


@router.get("/status/{payment_id}", response_model=PaymentStatusResponse)
async def get_payment_status(payment_id: str):
    np = _get_client()
    result = await np.get_payment_status(payment_id)
    if "payment_status" not in result:
        raise HTTPException(status_code=404, detail="Payment not found")
    return PaymentStatusResponse(
        payment_id=str(result.get("payment_id", payment_id)),
        payment_status=result["payment_status"],
        pay_amount=result.get("pay_amount"), pay_currency=result.get("pay_currency"),
        price_amount=result.get("price_amount"), price_currency=result.get("price_currency"),
        order_id=result.get("order_id"),
    )


@router.post("/commission", response_model=CommissionBreakdown)
async def get_commission(req: InvoiceRequest):
    breakdown = get_commission_breakdown(req.amount, req.plan, req.niche)
    cost = calculate_topup_cost(req.amount, req.plan, req.niche)
    return CommissionBreakdown(**breakdown, commission=cost["commission"], total=cost["total"])


@router.post("/webhooks/nowpayments")
async def nowpayments_webhook(
    request: Request,
    x_nowpayments_sig: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    body = await request.json()
    np = _get_client()

    if x_nowpayments_sig and np.ipn_secret:
        valid = await np.verify_ipn(body, x_nowpayments_sig)
        if not valid:
            raise HTTPException(status_code=401, detail="Invalid IPN signature")

    order_id = body.get("order_id")
    payment_status = body.get("payment_status")
    if not order_id:
        raise HTTPException(status_code=400, detail="Missing order_id")

    try:
        order_uuid = UUID(order_id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="Invalid order_id format")

    result = await db.execute(select(Transaction).where(Transaction.id == order_uuid))
    txn = result.scalar_one_or_none()
    if not txn:
        log.warning("IPN for unknown order_id=%s", order_id)
        return {"status": "ok"}

    if payment_status in ("finished", "confirmed"):
        txn.status = "confirmed"
        txn.confirmed_at = datetime.now(timezone.utc)
        txn.crypto_amount = Decimal(str(body.get("actually_paid", 0)))
        txn.crypto_currency = body.get("pay_currency")

        if txn.account_id:
            result = await db.execute(select(AdAccount).where(AdAccount.id == txn.account_id))
            acct = result.scalar_one_or_none()
            if acct:
                acct.balance = (acct.balance or 0) + txn.ad_amount

        if txn.commission:
            ledger = RevenueLedger(
                transaction_id=txn.id, type="commission",
                amount=txn.commission, currency="USD",
            )
            db.add(ledger)
    elif payment_status in ("failed", "expired"):
        txn.status = payment_status

    await db.flush()
    await db.commit()
    log.info("IPN processed: order=%s status=%s", order_id, payment_status)
    return {"status": "ok"}


@router.get("/transactions", response_model=list[TransactionOut])
async def list_transactions(
    client_id: Optional[UUID] = Query(None),
    status: Optional[str] = Query(None),
    skip: int = 0, limit: int = 50,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Transaction)
    if client_id:
        stmt = stmt.where(Transaction.client_id == client_id)
    if status:
        stmt = stmt.where(Transaction.status == status)
    stmt = stmt.order_by(Transaction.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/currencies")
async def list_currencies():
    np = _get_client()
    currencies = await np.get_available_currencies()
    return {"currencies": currencies}
