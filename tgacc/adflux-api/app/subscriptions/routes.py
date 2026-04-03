from uuid import UUID
from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
import logging

from app.database import get_db
from app.models import SubscriptionPlan, Subscription, Client
from app.auth.dependencies import get_current_user, require_admin
from app.subscriptions.schemas import (
    PlanOut, PlanCreate, PlanUpdate,
    SubscriptionOut, SubscribeRequest, CancelRequest,
    RenewalResult, RenewalSummary,
)

log = logging.getLogger(__name__)
router = APIRouter(tags=["subscriptions"])

INTERVAL_MAP = {
    "monthly": "price_monthly",
    "semiannual": "price_semiannual",
    "annual": "price_annual",
}

INTERVAL_DELTA = {
    "monthly": relativedelta(months=1),
    "semiannual": relativedelta(months=6),
    "annual": relativedelta(years=1),
}


# ── Client-facing ──

@router.get("/subscriptions/plans", response_model=list[PlanOut])
async def list_plans(db: AsyncSession = Depends(get_db)):
    stmt = select(SubscriptionPlan).where(SubscriptionPlan.is_active == True).order_by(SubscriptionPlan.sort_order)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/subscriptions/current", response_model=SubscriptionOut)
async def get_current_subscription(user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    client_id = user.get("client_id")
    if not client_id:
        raise HTTPException(status_code=400, detail="No client linked to this user")
    stmt = (
        select(Subscription)
        .where(Subscription.client_id == UUID(client_id), Subscription.status == "active")
        .order_by(Subscription.started_at.desc())
    )
    result = await db.execute(stmt)
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="No active subscription")
    return sub


@router.post("/subscriptions/subscribe", response_model=SubscriptionOut, status_code=201)
async def subscribe(data: SubscribeRequest, user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    client_id = user.get("client_id")
    if not client_id:
        raise HTTPException(status_code=400, detail="No client linked to this user")

    # Look up plan
    result = await db.execute(select(SubscriptionPlan).where(SubscriptionPlan.slug == data.plan_slug, SubscriptionPlan.is_active == True))
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    if data.interval not in INTERVAL_MAP:
        raise HTTPException(status_code=400, detail="Invalid interval. Use: monthly, semiannual, annual")

    price = getattr(plan, INTERVAL_MAP[data.interval])
    if price is None:
        raise HTTPException(status_code=400, detail=f"Plan does not support {data.interval} billing")

    # Cancel any existing active subscription
    existing = await db.execute(
        select(Subscription).where(Subscription.client_id == UUID(client_id), Subscription.status == "active")
    )
    for old_sub in existing.scalars().all():
        old_sub.status = "cancelled"
        old_sub.cancelled_at = datetime.now(timezone.utc)

    now = datetime.now(timezone.utc)
    sub = Subscription(
        client_id=UUID(client_id),
        plan=plan.slug,
        price=price,
        interval_type=data.interval,
        status="active",
        started_at=now,
        next_bill=now + INTERVAL_DELTA[data.interval],
    )
    db.add(sub)

    # Update client plan field
    client_result = await db.execute(select(Client).where(Client.id == UUID(client_id)))
    client = client_result.scalar_one_or_none()
    if client:
        client.plan = plan.slug

    await db.flush()
    await db.commit()
    await db.refresh(sub)
    log.info("Client %s subscribed to %s (%s)", client_id, plan.slug, data.interval)
    return sub


@router.post("/subscriptions/cancel", response_model=SubscriptionOut)
async def cancel_subscription(data: CancelRequest, user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    client_id = user.get("client_id")
    if not client_id:
        raise HTTPException(status_code=400, detail="No client linked to this user")

    result = await db.execute(
        select(Subscription).where(Subscription.client_id == UUID(client_id), Subscription.status == "active")
    )
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="No active subscription to cancel")

    sub.status = "cancelled"
    sub.cancelled_at = datetime.now(timezone.utc)
    await db.flush()
    await db.commit()
    await db.refresh(sub)
    log.info("Client %s cancelled subscription (reason: %s)", client_id, data.reason)
    return sub


@router.post("/subscriptions/change", response_model=SubscriptionOut, status_code=201)
async def change_plan(data: SubscribeRequest, user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Cancel current subscription and subscribe to a new plan."""
    client_id = user.get("client_id")
    if not client_id:
        raise HTTPException(status_code=400, detail="No client linked to this user")

    # Cancel existing
    existing = await db.execute(
        select(Subscription).where(Subscription.client_id == UUID(client_id), Subscription.status == "active")
    )
    for old_sub in existing.scalars().all():
        old_sub.status = "cancelled"
        old_sub.cancelled_at = datetime.now(timezone.utc)

    # Subscribe to new plan
    result = await db.execute(select(SubscriptionPlan).where(SubscriptionPlan.slug == data.plan_slug, SubscriptionPlan.is_active == True))
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    if data.interval not in INTERVAL_MAP:
        raise HTTPException(status_code=400, detail="Invalid interval. Use: monthly, semiannual, annual")

    price = getattr(plan, INTERVAL_MAP[data.interval])
    if price is None:
        raise HTTPException(status_code=400, detail=f"Plan does not support {data.interval} billing")

    now = datetime.now(timezone.utc)
    sub = Subscription(
        client_id=UUID(client_id),
        plan=plan.slug,
        price=price,
        interval_type=data.interval,
        status="active",
        started_at=now,
        next_bill=now + INTERVAL_DELTA[data.interval],
    )
    db.add(sub)

    client_result = await db.execute(select(Client).where(Client.id == UUID(client_id)))
    client = client_result.scalar_one_or_none()
    if client:
        client.plan = plan.slug

    await db.flush()
    await db.commit()
    await db.refresh(sub)
    log.info("Client %s changed plan to %s (%s)", client_id, plan.slug, data.interval)
    return sub


# ── Admin-facing ──

@router.get("/admin/plans", response_model=list[PlanOut])
async def admin_list_plans(user: dict = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    stmt = select(SubscriptionPlan).order_by(SubscriptionPlan.sort_order)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/admin/plans", response_model=PlanOut, status_code=201)
async def admin_create_plan(data: PlanCreate, user: dict = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    plan = SubscriptionPlan(**data.model_dump())
    db.add(plan)
    await db.flush()
    await db.commit()
    await db.refresh(plan)
    return plan


@router.put("/admin/plans/{plan_id}", response_model=PlanOut)
async def admin_update_plan(
    plan_id: UUID, data: PlanUpdate,
    user: dict = Depends(require_admin), db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(SubscriptionPlan).where(SubscriptionPlan.id == plan_id))
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(plan, k, v)
    await db.flush()
    await db.commit()
    await db.refresh(plan)
    return plan


@router.delete("/admin/plans/{plan_id}")
async def admin_delete_plan(plan_id: UUID, user: dict = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SubscriptionPlan).where(SubscriptionPlan.id == plan_id))
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    plan.is_active = False
    await db.flush()
    await db.commit()
    return {"detail": "Plan deactivated"}


@router.get("/admin/subscriptions", response_model=list[SubscriptionOut])
async def admin_list_subscriptions(
    client_id: Optional[UUID] = Query(None),
    status: Optional[str] = Query(None),
    plan: Optional[str] = Query(None),
    skip: int = 0, limit: int = 50,
    user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Subscription)
    if client_id:
        stmt = stmt.where(Subscription.client_id == client_id)
    if status:
        stmt = stmt.where(Subscription.status == status)
    if plan:
        stmt = stmt.where(Subscription.plan == plan)
    stmt = stmt.order_by(Subscription.started_at.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.put("/admin/subscriptions/{sub_id}", response_model=SubscriptionOut)
async def admin_update_subscription(
    sub_id: UUID,
    status: str = Query(..., description="New status: active, cancelled, paused, expired"),
    user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Subscription).where(Subscription.id == sub_id))
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")
    sub.status = status
    if status == "cancelled":
        sub.cancelled_at = datetime.now(timezone.utc)
    await db.flush()
    await db.commit()
    await db.refresh(sub)
    return sub


# ── Renewal check (cron-friendly) ──

@router.post("/subscriptions/check-renewals", response_model=RenewalSummary)
async def check_renewals(
    user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Check all active subscriptions whose billing date has passed.

    * **Stripe subscriptions** (notes contain ``stripe_sub:``): query Stripe
      for current status and deactivate if the Stripe subscription is no
      longer active.
    * **Other subscriptions**: if ``next_bill`` has passed, mark as
      ``past_due`` and advance the billing date by one interval so a future
      run can retry.

    Designed to be called by a cron job (e.g. daily).
    """
    import stripe as _stripe
    from app.config import get_settings

    settings = get_settings()
    _stripe.api_key = settings.STRIPE_SECRET_KEY

    now = datetime.now(timezone.utc)
    stmt = (
        select(Subscription)
        .where(
            Subscription.status == "active",
            Subscription.next_bill <= now,
        )
    )
    result = await db.execute(stmt)
    subs = result.scalars().all()

    summary = RenewalSummary(checked=len(subs))
    results: list[RenewalResult] = []

    for sub in subs:
        stripe_sub_id = _extract_stripe_sub(sub.notes)

        if stripe_sub_id and settings.STRIPE_SECRET_KEY:
            try:
                stripe_sub = _stripe.Subscription.retrieve(stripe_sub_id)
                if stripe_sub.status in ("active", "trialing"):
                    # Stripe considers it active — advance billing date
                    delta = INTERVAL_DELTA.get(sub.interval_type, relativedelta(months=1))
                    sub.next_bill = now + delta
                    summary.renewed += 1
                    results.append(RenewalResult(
                        subscription_id=sub.id,
                        client_id=sub.client_id,
                        plan=sub.plan,
                        action="renewed",
                        detail=f"Stripe status: {stripe_sub.status}",
                    ))
                else:
                    sub.status = "cancelled" if stripe_sub.status == "canceled" else "past_due"
                    if sub.status == "cancelled":
                        sub.cancelled_at = now
                    summary.deactivated += 1
                    results.append(RenewalResult(
                        subscription_id=sub.id,
                        client_id=sub.client_id,
                        plan=sub.plan,
                        action="deactivated",
                        detail=f"Stripe status: {stripe_sub.status}",
                    ))
            except Exception as exc:
                log.error("Stripe check failed for sub %s: %s", sub.id, exc)
                summary.errors += 1
                results.append(RenewalResult(
                    subscription_id=sub.id,
                    client_id=sub.client_id,
                    plan=sub.plan,
                    action="error",
                    detail=str(exc)[:200],
                ))
        else:
            # Non-Stripe subscription: mark past_due, advance billing date
            sub.status = "past_due"
            delta = INTERVAL_DELTA.get(sub.interval_type, relativedelta(months=1))
            sub.next_bill = now + delta
            summary.deactivated += 1
            results.append(RenewalResult(
                subscription_id=sub.id,
                client_id=sub.client_id,
                plan=sub.plan,
                action="deactivated",
                detail="No Stripe subscription linked; marked past_due",
            ))

    summary.results = results
    await db.commit()
    log.info(
        "Renewal check: %d checked, %d renewed, %d deactivated, %d errors",
        summary.checked, summary.renewed, summary.deactivated, summary.errors,
    )
    return summary


def _extract_stripe_sub(notes: str | None) -> str | None:
    """Pull ``sub_xxx`` from notes like ``stripe_sub:sub_1ABC``."""
    if not notes:
        return None
    for part in notes.split():
        if part.startswith("stripe_sub:"):
            return part.split(":", 1)[1]
    return None
