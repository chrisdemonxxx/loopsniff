"""Stripe payment endpoints for wallet top-ups, payment methods, subscriptions, and invoices."""

import logging
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.config import get_settings
from app.database import get_db
from app.models import (
    Client,
    Wallet,
    WalletTransaction,
    Subscription,
    SubscriptionPlan,
    RevenueLedger,
    Transaction,
)
from app.payments.schemas import (
    StripeCreateIntentRequest,
    StripeIntentResponse,
    StripePaymentMethodOut,
    StripeAddMethodRequest,
    StripeCreateSubscriptionRequest,
    StripeSubscriptionResponse,
    StripeCancelSubscriptionRequest,
    StripeInvoiceOut,
)

log = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(prefix="/payments/stripe", tags=["payments"])

stripe.api_key = settings.STRIPE_SECRET_KEY


# ── Helpers ──────────────────────────────────────────────────────────────────

def _require_client_id(user: dict) -> UUID:
    cid = user.get("client_id")
    if not cid:
        raise HTTPException(status_code=403, detail="No client account linked")
    return UUID(cid) if isinstance(cid, str) else cid


async def _ensure_stripe_customer(db: AsyncSession, client_id: UUID) -> str:
    """Return or create a Stripe customer for the given client."""
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # Stripe customer ID stored in client.notes as "stripe:cus_xxx" (simple approach)
    stripe_cid = None
    if client.notes:
        for part in client.notes.split(";"):
            if part.strip().startswith("stripe:"):
                stripe_cid = part.strip().split(":", 1)[1]
                break

    if stripe_cid:
        return stripe_cid

    customer = stripe.Customer.create(
        email=client.email or "",
        name=client.name,
        metadata={"adflux_client_id": str(client.id)},
    )
    tag = f"stripe:{customer.id}"
    client.notes = f"{client.notes};{tag}" if client.notes else tag
    await db.flush()
    return customer.id


async def _get_or_create_wallet(db: AsyncSession, client_id: UUID) -> Wallet:
    result = await db.execute(select(Wallet).where(Wallet.client_id == client_id))
    wallet = result.scalar_one_or_none()
    if wallet:
        return wallet
    wallet = Wallet(client_id=client_id, currency="USD", balance=Decimal("0"), frozen_balance=Decimal("0"))
    db.add(wallet)
    await db.flush()
    await db.refresh(wallet)
    return wallet


# ── Payment Intents (wallet top-up) ─────────────────────────────────────────

@router.post("/create-intent", response_model=StripeIntentResponse)
async def create_payment_intent(
    data: StripeCreateIntentRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a Stripe PaymentIntent for wallet top-up."""
    client_id = _require_client_id(user)
    stripe_customer_id = await _ensure_stripe_customer(db, client_id)
    wallet = await _get_or_create_wallet(db, client_id)

    amount_cents = int(data.amount * 100)
    try:
        intent_params = {
            "amount": amount_cents,
            "currency": data.currency,
            "customer": stripe_customer_id,
            "metadata": {
                "adflux_client_id": str(client_id),
                "adflux_wallet_id": str(wallet.id),
                "type": "wallet_topup",
            },
        }
        if data.payment_method_id:
            intent_params["payment_method"] = data.payment_method_id
        intent = stripe.PaymentIntent.create(**intent_params)
    except stripe.StripeError as e:
        log.error("Stripe PaymentIntent creation failed: %s", e)
        raise HTTPException(status_code=502, detail=f"Stripe error: {e.user_message or str(e)}")

    return StripeIntentResponse(
        client_secret=intent.client_secret,
        payment_intent_id=intent.id,
        amount=data.amount,
        currency=data.currency,
        status=intent.status,
    )


# ── Webhook ──────────────────────────────────────────────────────────────────

@router.post("/webhook")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Handle Stripe webhook events."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.SignatureVerificationError:
        raise HTTPException(status_code=401, detail="Invalid signature")

    event_type = event["type"]
    data_obj = event["data"]["object"]

    if event_type == "payment_intent.succeeded":
        await _handle_payment_succeeded(data_obj, db)
    elif event_type == "payment_intent.payment_failed":
        await _handle_payment_failed(data_obj, db)
    else:
        log.info("Unhandled Stripe event: %s", event_type)

    return {"status": "ok"}


async def _handle_payment_succeeded(intent: dict, db: AsyncSession):
    metadata = intent.get("metadata", {})
    if metadata.get("type") != "wallet_topup":
        return

    wallet_id = metadata.get("adflux_wallet_id")
    client_id = metadata.get("adflux_client_id")
    if not wallet_id:
        log.warning("Stripe succeeded event missing wallet_id metadata")
        return

    result = await db.execute(select(Wallet).where(Wallet.id == UUID(wallet_id)))
    wallet = result.scalar_one_or_none()
    if not wallet:
        log.warning("Wallet %s not found for Stripe payment", wallet_id)
        return

    amount = Decimal(str(intent["amount"])) / Decimal("100")

    wallet.balance += amount

    txn = WalletTransaction(
        wallet_id=wallet.id,
        type="deposit",
        amount=amount,
        fee=Decimal("0"),
        net_amount=amount,
        currency=intent.get("currency", "usd").upper(),
        payment_method="credit_card",
        payment_reference=intent["id"],
        status="completed",
        completed_at=datetime.now(timezone.utc),
        notes=f"Stripe payment {intent['id']}",
    )
    db.add(txn)
    await db.flush()
    log.info("Stripe wallet top-up completed: wallet=%s amount=%s", wallet_id, amount)


async def _handle_payment_failed(intent: dict, db: AsyncSession):
    metadata = intent.get("metadata", {})
    wallet_id = metadata.get("adflux_wallet_id")
    if not wallet_id:
        return

    txn = WalletTransaction(
        wallet_id=UUID(wallet_id),
        type="deposit",
        amount=Decimal(str(intent["amount"])) / Decimal("100"),
        fee=Decimal("0"),
        net_amount=Decimal("0"),
        currency=intent.get("currency", "usd").upper(),
        payment_method="credit_card",
        payment_reference=intent["id"],
        status="failed",
        notes=f"Stripe payment failed: {intent.get('last_payment_error', {}).get('message', 'unknown')}",
    )
    db.add(txn)
    await db.flush()
    log.warning("Stripe payment failed: intent=%s", intent["id"])


# ── Payment Methods ──────────────────────────────────────────────────────────

@router.get("/methods", response_model=list[StripePaymentMethodOut])
async def list_payment_methods(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List saved payment methods for the current client."""
    client_id = _require_client_id(user)
    stripe_customer_id = await _ensure_stripe_customer(db, client_id)

    try:
        methods = stripe.PaymentMethod.list(customer=stripe_customer_id, type="card")
    except stripe.StripeError as e:
        raise HTTPException(status_code=502, detail=f"Stripe error: {e.user_message or str(e)}")

    # Determine default payment method
    try:
        customer = stripe.Customer.retrieve(stripe_customer_id)
        default_pm = (customer.invoice_settings or {}).get("default_payment_method")
    except stripe.StripeError:
        default_pm = None

    result = []
    for pm in methods.data:
        card = pm.card
        result.append(StripePaymentMethodOut(
            id=pm.id,
            brand=card.brand,
            last4=card.last4,
            exp_month=card.exp_month,
            exp_year=card.exp_year,
            is_default=(pm.id == default_pm),
        ))
    return result


@router.post("/methods", response_model=StripePaymentMethodOut, status_code=201)
async def add_payment_method(
    data: StripeAddMethodRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Attach a new payment method (card) to the client's Stripe customer."""
    client_id = _require_client_id(user)
    stripe_customer_id = await _ensure_stripe_customer(db, client_id)

    try:
        pm = stripe.PaymentMethod.attach(data.payment_method_id, customer=stripe_customer_id)
        # Set as default if it's the first method
        existing = stripe.PaymentMethod.list(customer=stripe_customer_id, type="card")
        if len(existing.data) == 1:
            stripe.Customer.modify(
                stripe_customer_id,
                invoice_settings={"default_payment_method": pm.id},
            )
    except stripe.StripeError as e:
        raise HTTPException(status_code=502, detail=f"Stripe error: {e.user_message or str(e)}")

    card = pm.card
    return StripePaymentMethodOut(
        id=pm.id,
        brand=card.brand,
        last4=card.last4,
        exp_month=card.exp_month,
        exp_year=card.exp_year,
        is_default=(len(existing.data) == 1),
    )


@router.delete("/methods/{method_id}", status_code=204)
async def remove_payment_method(
    method_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Detach a payment method from the client's Stripe customer."""
    client_id = _require_client_id(user)
    stripe_customer_id = await _ensure_stripe_customer(db, client_id)

    try:
        pm = stripe.PaymentMethod.retrieve(method_id)
        if pm.customer != stripe_customer_id:
            raise HTTPException(status_code=403, detail="Payment method does not belong to you")
        stripe.PaymentMethod.detach(method_id)
    except stripe.StripeError as e:
        raise HTTPException(status_code=502, detail=f"Stripe error: {e.user_message or str(e)}")


# ── Subscriptions ────────────────────────────────────────────────────────────

@router.post("/create-subscription", response_model=StripeSubscriptionResponse)
async def create_subscription(
    data: StripeCreateSubscriptionRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a Stripe subscription for a plan."""
    client_id = _require_client_id(user)
    stripe_customer_id = await _ensure_stripe_customer(db, client_id)

    result = await db.execute(select(SubscriptionPlan).where(SubscriptionPlan.id == data.plan_id))
    plan = result.scalar_one_or_none()
    if not plan or not plan.is_active:
        raise HTTPException(status_code=404, detail="Subscription plan not found or inactive")

    price_map = {
        "monthly": plan.price_monthly,
        "semiannual": plan.price_semiannual or plan.price_monthly * 6,
        "annual": plan.price_annual or plan.price_monthly * 12,
    }
    price = price_map.get(data.interval)
    if price is None:
        raise HTTPException(status_code=400, detail="Invalid billing interval")

    interval_map = {"monthly": "month", "semiannual": "month", "annual": "year"}
    interval_count_map = {"monthly": 1, "semiannual": 6, "annual": 1}

    try:
        stripe_price = stripe.Price.create(
            unit_amount=int(price * 100),
            currency="usd",
            recurring={
                "interval": interval_map[data.interval],
                "interval_count": interval_count_map[data.interval],
            },
            product_data={"name": f"AdFlux {plan.name} ({data.interval})"},
        )

        sub_params = {
            "customer": stripe_customer_id,
            "items": [{"price": stripe_price.id}],
            "payment_behavior": "default_incomplete",
            "expand": ["latest_invoice.payment_intent"],
            "metadata": {
                "adflux_client_id": str(client_id),
                "adflux_plan_id": str(plan.id),
                "interval": data.interval,
            },
        }
        if data.payment_method_id:
            sub_params["default_payment_method"] = data.payment_method_id

        subscription = stripe.Subscription.create(**sub_params)
    except stripe.StripeError as e:
        log.error("Stripe subscription creation failed: %s", e)
        raise HTTPException(status_code=502, detail=f"Stripe error: {e.user_message or str(e)}")

    # Track subscription locally
    local_sub = Subscription(
        client_id=client_id,
        plan=plan.slug,
        price=price,
        interval_type=data.interval,
        status="pending",
    )
    local_sub.notes = f"stripe_sub:{subscription.id}"
    db.add(local_sub)
    await db.flush()

    client_secret = None
    latest_invoice = subscription.get("latest_invoice")
    if isinstance(latest_invoice, dict):
        pi = latest_invoice.get("payment_intent")
        if isinstance(pi, dict):
            client_secret = pi.get("client_secret")

    return StripeSubscriptionResponse(
        subscription_id=subscription.id,
        plan_name=plan.name,
        status=subscription.status,
        current_period_end=datetime.fromtimestamp(subscription.current_period_end, tz=timezone.utc),
        client_secret=client_secret,
    )


@router.post("/cancel-subscription")
async def cancel_subscription(
    data: StripeCancelSubscriptionRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cancel a Stripe subscription."""
    client_id = _require_client_id(user)
    await _ensure_stripe_customer(db, client_id)

    try:
        if data.cancel_at_period_end:
            subscription = stripe.Subscription.modify(
                data.subscription_id,
                cancel_at_period_end=True,
            )
        else:
            subscription = stripe.Subscription.cancel(data.subscription_id)
    except stripe.StripeError as e:
        raise HTTPException(status_code=502, detail=f"Stripe error: {e.user_message or str(e)}")

    return {
        "subscription_id": subscription.id,
        "status": subscription.status,
        "cancel_at_period_end": subscription.cancel_at_period_end,
    }


# ── Invoices ─────────────────────────────────────────────────────────────────

@router.get("/invoices", response_model=list[StripeInvoiceOut])
async def list_invoices(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List Stripe invoices for the current client."""
    client_id = _require_client_id(user)
    stripe_customer_id = await _ensure_stripe_customer(db, client_id)

    try:
        invoices = stripe.Invoice.list(customer=stripe_customer_id, limit=50)
    except stripe.StripeError as e:
        raise HTTPException(status_code=502, detail=f"Stripe error: {e.user_message or str(e)}")

    result = []
    for inv in invoices.data:
        result.append(StripeInvoiceOut(
            id=inv.id,
            amount_due=inv.amount_due,
            amount_paid=inv.amount_paid,
            currency=inv.currency,
            status=inv.status or "draft",
            hosted_invoice_url=inv.hosted_invoice_url,
            created=datetime.fromtimestamp(inv.created, tz=timezone.utc),
            period_start=datetime.fromtimestamp(inv.period_start, tz=timezone.utc) if inv.period_start else None,
            period_end=datetime.fromtimestamp(inv.period_end, tz=timezone.utc) if inv.period_end else None,
        ))
    return result
