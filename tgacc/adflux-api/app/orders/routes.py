import uuid
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional

from app.database import get_db
from app.models import Order, Subscription
from app.auth.dependencies import get_current_user, require_admin
from app.orders.schemas import (
    OrderCreate, OrderUpdate, OrderOut,
    SubscriptionCreate, SubscriptionUpdate, SubscriptionOut,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/orders", tags=["orders"])
sub_router = APIRouter(prefix="/subscriptions", tags=["orders"])


# --------------- Orders ---------------

@router.get("", response_model=list[OrderOut])
async def list_orders(
    status: Optional[str] = Query(None),
    order_type: Optional[str] = Query(None),
    client_id: Optional[uuid.UUID] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    stmt = select(Order)

    if current_user["user_type"] == "client":
        stmt = stmt.where(Order.client_id == current_user["client_id"])
    elif client_id:
        stmt = stmt.where(Order.client_id == client_id)

    if status:
        stmt = stmt.where(Order.status == status)
    if order_type:
        stmt = stmt.where(Order.order_type == order_type)

    stmt = stmt.order_by(Order.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("", response_model=OrderOut, status_code=201)
async def create_order(
    payload: OrderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    if current_user["user_type"] == "client":
        cid = current_user["client_id"]
    else:
        cid = payload.client_id
        if not cid:
            raise HTTPException(400, "client_id is required for admin-created orders")

    order = Order(
        id=uuid.uuid4(),
        client_id=cid,
        order_type=payload.order_type,
        status="pending",
        amount=payload.amount,
        currency=payload.currency,
        account_id=payload.account_id,
        details=payload.details,
        notes=payload.notes,
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)
    logger.info("Order %s created for client %s", order.id, cid)
    return order


@router.get("/stats")
async def order_stats(
    db: AsyncSession = Depends(get_db),
    _admin: dict = Depends(require_admin),
):
    by_status = await db.execute(
        select(Order.status, func.count(Order.id)).group_by(Order.status)
    )
    by_type = await db.execute(
        select(Order.order_type, func.count(Order.id)).group_by(Order.order_type)
    )
    revenue = await db.execute(
        select(func.coalesce(func.sum(Order.amount), 0)).where(
            Order.status == "delivered"
        )
    )

    return {
        "by_status": dict(by_status.all()),
        "by_type": dict(by_type.all()),
        "total_revenue": float(revenue.scalar_one()),
    }


# --------------- Subscriptions ---------------

@sub_router.get("", response_model=list[SubscriptionOut])
async def list_subscriptions(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    stmt = select(Subscription)

    if current_user["user_type"] == "client":
        stmt = stmt.where(Subscription.client_id == current_user["client_id"])

    stmt = stmt.order_by(Subscription.started_at.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@sub_router.post("", response_model=SubscriptionOut, status_code=201)
async def create_subscription(
    payload: SubscriptionCreate,
    db: AsyncSession = Depends(get_db),
    _admin: dict = Depends(require_admin),
):
    sub = Subscription(
        id=uuid.uuid4(),
        client_id=payload.client_id,
        plan=payload.plan,
        price=payload.price,
        interval_type=payload.interval_type,
        status="active",
        started_at=datetime.utcnow(),
    )
    db.add(sub)
    await db.commit()
    await db.refresh(sub)
    logger.info("Subscription %s created – plan=%s", sub.id, sub.plan)
    return sub


@sub_router.get("/{sub_id}", response_model=SubscriptionOut)
async def get_subscription(
    sub_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(select(Subscription).where(Subscription.id == sub_id))
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(404, "Subscription not found")

    if (
        current_user["user_type"] == "client"
        and str(sub.client_id) != str(current_user["client_id"])
    ):
        raise HTTPException(403, "Access denied")

    return sub


@sub_router.put("/{sub_id}", response_model=SubscriptionOut)
async def update_subscription(
    sub_id: uuid.UUID,
    payload: SubscriptionUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: dict = Depends(require_admin),
):
    result = await db.execute(select(Subscription).where(Subscription.id == sub_id))
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(404, "Subscription not found")

    if payload.plan is not None:
        sub.plan = payload.plan
    if payload.price is not None:
        sub.price = payload.price
    if payload.status is not None:
        sub.status = payload.status
        if payload.status == "cancelled":
            sub.cancelled_at = datetime.utcnow()

    await db.commit()
    await db.refresh(sub)
    logger.info("Subscription %s updated – status=%s", sub.id, sub.status)
    return sub


# Include sub_router BEFORE /{order_id} wildcard so /subscriptions matches first
router.include_router(sub_router)


# --------------- Order by ID (must be last — catches all /{order_id}) ---------------


@router.get("/{order_id}", response_model=OrderOut)
async def get_order(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(404, "Order not found")

    if (
        current_user["user_type"] == "client"
        and str(order.client_id) != str(current_user["client_id"])
    ):
        raise HTTPException(403, "Access denied")

    return order


@router.put("/{order_id}", response_model=OrderOut)
async def update_order(
    order_id: uuid.UUID,
    payload: OrderUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(404, "Order not found")

    if current_user["user_type"] == "client":
        if str(order.client_id) != str(current_user["client_id"]):
            raise HTTPException(403, "Access denied")
        if payload.status and payload.status != "cancelled":
            raise HTTPException(403, "Clients can only cancel orders")
        if payload.status == "cancelled" and order.status != "pending":
            raise HTTPException(400, "Only pending orders can be cancelled")

    if payload.status is not None:
        order.status = payload.status
        if payload.status == "delivered":
            order.delivered_at = datetime.utcnow()
    if payload.notes is not None:
        order.notes = payload.notes
    if payload.details is not None:
        order.details = payload.details

    order.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(order)
    logger.info("Order %s updated – status=%s", order.id, order.status)
    return order

