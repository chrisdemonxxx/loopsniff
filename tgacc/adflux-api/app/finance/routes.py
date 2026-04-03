import uuid as _uuid
import logging
from decimal import Decimal
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case
from typing import Optional

from app.database import get_db
from app.models import (
    Transaction, RevenueLedger, Client, Wallet, WalletTransaction,
    Subscription, BalanceAdjustment,
)
from app.auth.dependencies import require_admin
from app.finance.schemas import (
    RevenueOverview, LTVData, CommissionBreakdownItem,
    DepositOut, DepositRejectBody,
    AdjustmentCreate, AdjustmentOut,
    RevenueBreakdownItem, LowBalanceAlert, FinanceSummary,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/finance", tags=["finance"])


# ────────────────────────── Existing Endpoints ──────────────────────────

@router.get("/revenue", response_model=RevenueOverview)
async def revenue_overview(user: dict = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    total_rev = (await db.execute(
        select(func.coalesce(func.sum(RevenueLedger.amount), 0))
    )).scalar()
    total_comm = (await db.execute(
        select(func.coalesce(func.sum(Transaction.commission), 0))
        .where(Transaction.status == "confirmed")
    )).scalar()
    total_spend = (await db.execute(
        select(func.coalesce(func.sum(Transaction.ad_amount), 0))
        .where(Transaction.status == "confirmed")
    )).scalar()
    txn_count = (await db.execute(
        select(func.count(Transaction.id)).where(Transaction.status == "confirmed")
    )).scalar() or 0

    return RevenueOverview(
        total_revenue=total_rev, total_commission=total_comm,
        total_ad_spend=total_spend, transaction_count=txn_count,
    )


@router.get("/ltv", response_model=list[LTVData])
async def client_ltv(
    limit: int = Query(20, le=100),
    user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(
            Client.id,
            Client.name,
            func.coalesce(func.sum(Transaction.ad_amount), 0).label("total_spend"),
            func.coalesce(func.sum(Transaction.commission), 0).label("total_commission"),
            func.count(Transaction.id).label("txn_count"),
        )
        .join(Transaction, (Transaction.client_id == Client.id) & (Transaction.status == "confirmed"), isouter=True)
        .group_by(Client.id, Client.name)
        .order_by(func.sum(Transaction.ad_amount).desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    rows = result.all()
    return [
        LTVData(
            client_id=str(r[0]), client_name=r[1],
            total_spend=r[2], total_commission=r[3],
            transaction_count=r[4],
            avg_transaction=Decimal(str(r[2])) / max(r[4], 1),
        )
        for r in rows
    ]


@router.get("/commission-breakdown", response_model=list[CommissionBreakdownItem])
async def commission_breakdown(user: dict = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    stmt = (
        select(
            Client.plan,
            func.coalesce(func.sum(Transaction.commission), 0).label("total_commission"),
            func.count(Transaction.id).label("txn_count"),
        )
        .join(Transaction, (Transaction.client_id == Client.id) & (Transaction.status == "confirmed"), isouter=True)
        .group_by(Client.plan)
        .order_by(func.sum(Transaction.commission).desc())
    )
    result = await db.execute(stmt)
    rows = result.all()
    return [
        CommissionBreakdownItem(
            plan=r[0] or "unknown",
            total_commission=r[1],
            transaction_count=r[2],
            avg_rate=(Decimal(str(r[1])) / max(r[2], 1)) if r[2] else None,
        )
        for r in rows
    ]


# ────────────────────────── Deposits ──────────────────────────

@router.get("/deposits", response_model=list[DepositOut])
async def list_deposits(
    status: Optional[str] = Query(None, description="pending, completed, failed, cancelled"),
    client_id: Optional[str] = Query(None),
    payment_method: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None, description="ISO date, e.g. 2024-01-01"),
    date_to: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, le=200),
    user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(WalletTransaction, Wallet.client_id, Client.name)
        .join(Wallet, WalletTransaction.wallet_id == Wallet.id)
        .join(Client, Wallet.client_id == Client.id)
        .where(WalletTransaction.type == "deposit")
    )
    if status:
        stmt = stmt.where(WalletTransaction.status == status)
    if client_id:
        stmt = stmt.where(Wallet.client_id == _uuid.UUID(client_id))
    if payment_method:
        stmt = stmt.where(WalletTransaction.payment_method == payment_method)
    if date_from:
        stmt = stmt.where(WalletTransaction.created_at >= date_from)
    if date_to:
        stmt = stmt.where(WalletTransaction.created_at <= date_to)

    stmt = stmt.order_by(WalletTransaction.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    rows = result.all()

    return [
        DepositOut(
            id=str(wt.id), wallet_id=str(wt.wallet_id),
            client_id=str(cid), client_name=cname,
            type=wt.type, amount=wt.amount, fee=wt.fee or 0,
            net_amount=wt.net_amount, currency=wt.currency or "USD",
            payment_method=wt.payment_method, payment_reference=wt.payment_reference,
            status=wt.status, notes=wt.notes,
            created_at=wt.created_at, completed_at=wt.completed_at,
        )
        for wt, cid, cname in rows
    ]


@router.put("/deposits/{deposit_id}/approve")
async def approve_deposit(
    deposit_id: str,
    user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(WalletTransaction).where(
        WalletTransaction.id == _uuid.UUID(deposit_id),
        WalletTransaction.type == "deposit",
    )
    wt = (await db.execute(stmt)).scalar_one_or_none()
    if not wt:
        raise HTTPException(404, "Deposit not found")
    if wt.status != "pending":
        raise HTTPException(400, f"Cannot approve deposit with status '{wt.status}'")

    wt.status = "completed"
    wt.completed_at = datetime.now(timezone.utc)

    # Credit wallet balance
    wallet = (await db.execute(select(Wallet).where(Wallet.id == wt.wallet_id))).scalar_one()
    wallet.balance = (wallet.balance or 0) + wt.net_amount
    log.info(f"Deposit {deposit_id} approved by {user['email']}, credited {wt.net_amount} to wallet {wallet.id}")
    return {"detail": "Deposit approved", "id": deposit_id}


@router.put("/deposits/{deposit_id}/reject")
async def reject_deposit(
    deposit_id: str,
    body: DepositRejectBody,
    user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(WalletTransaction).where(
        WalletTransaction.id == _uuid.UUID(deposit_id),
        WalletTransaction.type == "deposit",
    )
    wt = (await db.execute(stmt)).scalar_one_or_none()
    if not wt:
        raise HTTPException(404, "Deposit not found")
    if wt.status != "pending":
        raise HTTPException(400, f"Cannot reject deposit with status '{wt.status}'")

    wt.status = "failed"
    wt.notes = f"Rejected: {body.reason}" + (f" (prev: {wt.notes})" if wt.notes else "")
    log.info(f"Deposit {deposit_id} rejected by {user['email']}: {body.reason}")
    return {"detail": "Deposit rejected", "id": deposit_id}


# ────────────────────────── Revenue Breakdown ──────────────────────────

@router.get("/revenue/breakdown", response_model=list[RevenueBreakdownItem])
async def revenue_breakdown(
    user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    # Completed deposits
    dep_total = (await db.execute(
        select(
            func.coalesce(func.sum(WalletTransaction.amount), 0),
            func.count(WalletTransaction.id),
        )
        .where(WalletTransaction.type == "deposit", WalletTransaction.status == "completed")
    )).one()

    # Active subscription MRR
    sub_total = (await db.execute(
        select(
            func.coalesce(func.sum(Subscription.price), 0),
            func.count(Subscription.id),
        )
        .where(Subscription.status == "active")
    )).one()

    # Fees from deposits
    fee_total = (await db.execute(
        select(
            func.coalesce(func.sum(WalletTransaction.fee), 0),
            func.count(WalletTransaction.id),
        )
        .where(WalletTransaction.fee > 0, WalletTransaction.status == "completed")
    )).one()

    # Commission revenue
    comm_total = (await db.execute(
        select(
            func.coalesce(func.sum(Transaction.commission), 0),
            func.count(Transaction.id),
        )
        .where(Transaction.status == "confirmed")
    )).one()

    return [
        RevenueBreakdownItem(source="deposits", amount=dep_total[0], count=dep_total[1]),
        RevenueBreakdownItem(source="subscriptions", amount=sub_total[0], count=sub_total[1]),
        RevenueBreakdownItem(source="fees", amount=fee_total[0], count=fee_total[1]),
        RevenueBreakdownItem(source="commissions", amount=comm_total[0], count=comm_total[1]),
    ]


# ────────────────────────── Adjustments ──────────────────────────

@router.post("/adjustments", response_model=AdjustmentOut, status_code=201)
async def create_adjustment(
    body: AdjustmentCreate,
    user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    if body.type not in ("credit", "debit"):
        raise HTTPException(400, "type must be 'credit' or 'debit'")
    if body.amount <= 0:
        raise HTTPException(400, "amount must be positive")

    client = (await db.execute(
        select(Client).where(Client.id == _uuid.UUID(body.client_id))
    )).scalar_one_or_none()
    if not client:
        raise HTTPException(404, "Client not found")

    # Apply to wallet
    wallet = (await db.execute(
        select(Wallet).where(Wallet.client_id == client.id)
    )).scalar_one_or_none()
    if not wallet:
        raise HTTPException(404, "Client has no wallet")

    if body.type == "credit":
        wallet.balance = (wallet.balance or 0) + body.amount
    else:
        wallet.balance = (wallet.balance or 0) - body.amount

    adj = BalanceAdjustment(
        client_id=client.id,
        type=body.type,
        amount=body.amount,
        reason=body.reason,
        created_by=user["id"],
    )
    db.add(adj)
    await db.flush()

    log.info(f"Adjustment {adj.id}: {body.type} {body.amount} for client {client.name} by {user['email']}")
    return AdjustmentOut(
        id=str(adj.id), client_id=str(client.id), client_name=client.name,
        type=adj.type, amount=adj.amount, reason=adj.reason,
        created_by=user["email"], created_at=adj.created_at,
    )


@router.get("/adjustments", response_model=list[AdjustmentOut])
async def list_adjustments(
    client_id: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, le=200),
    user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(BalanceAdjustment, Client.name)
        .join(Client, BalanceAdjustment.client_id == Client.id)
    )
    if client_id:
        stmt = stmt.where(BalanceAdjustment.client_id == _uuid.UUID(client_id))

    stmt = stmt.order_by(BalanceAdjustment.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    rows = result.all()

    return [
        AdjustmentOut(
            id=str(adj.id), client_id=str(adj.client_id), client_name=cname,
            type=adj.type, amount=adj.amount, reason=adj.reason,
            created_by=str(adj.created_by), created_at=adj.created_at,
        )
        for adj, cname in rows
    ]


# ────────────────────────── Alerts ──────────────────────────

@router.get("/alerts", response_model=list[LowBalanceAlert])
async def low_balance_alerts(
    threshold: Decimal = Query(Decimal("50"), description="Balance threshold in USD"),
    user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Client.id, Client.name, Wallet.balance, Wallet.currency)
        .join(Wallet, Wallet.client_id == Client.id)
        .where(Client.status == "active", Wallet.balance < threshold)
        .order_by(Wallet.balance.asc())
    )
    result = await db.execute(stmt)
    rows = result.all()

    return [
        LowBalanceAlert(
            client_id=str(r[0]), client_name=r[1],
            wallet_balance=r[2] or 0, currency=r[3] or "USD",
        )
        for r in rows
    ]


# ────────────────────────── Summary ──────────────────────────

@router.get("/summary", response_model=FinanceSummary)
async def finance_summary(
    user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    # Deposit totals
    dep_totals = (await db.execute(
        select(
            func.coalesce(func.sum(WalletTransaction.amount), 0),
            func.count(WalletTransaction.id).filter(WalletTransaction.status == "completed"),
            func.count(WalletTransaction.id).filter(WalletTransaction.status == "pending"),
            func.count(WalletTransaction.id).filter(WalletTransaction.status == "failed"),
        )
        .where(WalletTransaction.type == "deposit")
    )).one()

    # Total revenue
    total_rev = (await db.execute(
        select(func.coalesce(func.sum(RevenueLedger.amount), 0))
    )).scalar()

    # Active subscriptions & MRR
    sub_data = (await db.execute(
        select(
            func.count(Subscription.id),
            func.coalesce(func.sum(Subscription.price), 0),
        )
        .where(Subscription.status == "active")
    )).one()

    # Adjustment count
    adj_count = (await db.execute(
        select(func.count(BalanceAdjustment.id))
    )).scalar() or 0

    return FinanceSummary(
        total_deposits=dep_totals[0],
        completed_deposits=dep_totals[1],
        pending_deposits=dep_totals[2],
        failed_deposits=dep_totals[3],
        total_revenue=total_rev,
        active_subscriptions=sub_data[0],
        subscription_mrr=sub_data[1],
        total_adjustments=adj_count,
    )
