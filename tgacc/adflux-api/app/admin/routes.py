from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional

from app.database import get_db
from app.models import (
    Client, AdAccount, Transaction, RevenueLedger,
    OutreachLead, AuditLog, AdminUser,
)
from app.auth.dependencies import require_admin
from app.admin.schemas import DashboardStats, AuditLogOut, AdminUserOut, AdminUserUpdate

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/dashboard", response_model=DashboardStats)
async def dashboard(user: dict = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    total_clients = (await db.execute(select(func.count(Client.id)))).scalar() or 0
    active_clients = (await db.execute(
        select(func.count(Client.id)).where(Client.status == "active")
    )).scalar() or 0
    total_accounts = (await db.execute(select(func.count(AdAccount.id)))).scalar() or 0
    active_accounts = (await db.execute(
        select(func.count(AdAccount.id)).where(AdAccount.status == "active")
    )).scalar() or 0
    banned_accounts = (await db.execute(
        select(func.count(AdAccount.id)).where(AdAccount.status == "banned")
    )).scalar() or 0
    total_revenue = float(
        (await db.execute(select(func.coalesce(func.sum(RevenueLedger.amount), 0)))).scalar()
    )
    pending_txns = (await db.execute(
        select(func.count(Transaction.id)).where(Transaction.status == "pending")
    )).scalar() or 0
    outreach_leads = (await db.execute(select(func.count(OutreachLead.id)))).scalar() or 0

    return DashboardStats(
        total_clients=total_clients, active_clients=active_clients,
        total_accounts=total_accounts, active_accounts=active_accounts,
        banned_accounts=banned_accounts, total_revenue=total_revenue,
        pending_transactions=pending_txns, outreach_leads=outreach_leads,
    )


@router.get("/audit", response_model=list[AuditLogOut])
async def audit_log(
    action: Optional[str] = Query(None),
    admin_id: Optional[UUID] = Query(None),
    skip: int = 0, limit: int = 50,
    user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(AuditLog)
    if action:
        stmt = stmt.where(AuditLog.action.ilike(f"%{action}%"))
    if admin_id:
        stmt = stmt.where(AuditLog.admin_id == admin_id)
    stmt = stmt.order_by(AuditLog.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/users", response_model=list[AdminUserOut])
async def list_admin_users(
    skip: int = 0, limit: int = 50,
    user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(AdminUser).order_by(AdminUser.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/users/{user_id}", response_model=AdminUserOut)
async def get_admin_user(
    user_id: UUID,
    user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(AdminUser).where(AdminUser.id == user_id))
    admin = result.scalar_one_or_none()
    if not admin:
        raise HTTPException(status_code=404, detail="Admin user not found")
    return admin


@router.put("/users/{user_id}", response_model=AdminUserOut)
async def update_admin_user(
    user_id: UUID, data: AdminUserUpdate,
    user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(AdminUser).where(AdminUser.id == user_id))
    admin = result.scalar_one_or_none()
    if not admin:
        raise HTTPException(status_code=404, detail="Admin user not found")
    allowed_fields = {"name", "role", "is_active"}
    for k, v in data.model_dump(exclude_unset=True).items():
        if k in allowed_fields:
            setattr(admin, k, v)
    await db.flush()
    await db.refresh(admin)
    return admin
