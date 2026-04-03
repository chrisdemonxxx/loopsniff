import secrets
from uuid import UUID
from datetime import datetime, timezone
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional
import logging

from app.database import get_db
from app.models import AffiliateCode, AffiliateReferral, AffiliateCommission, Client
from app.auth.dependencies import get_current_user, require_admin
from app.affiliate.schemas import (
    AffiliateCodeOut, AffiliateCodeCreate, AffiliateCodeUpdate,
    ReferralOut, CommissionOut, CommissionStatusUpdate, AffiliateStats,
)

log = logging.getLogger(__name__)
router = APIRouter(tags=["affiliate"])


def _require_client_id(user: dict) -> UUID:
    client_id = user.get("client_id")
    if not client_id:
        raise HTTPException(status_code=403, detail="No client associated with this user")
    return UUID(client_id)


# ── Client-facing endpoints ──


@router.get("/affiliate/code", response_model=AffiliateCodeOut)
async def get_or_create_affiliate_code(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    client_id = _require_client_id(user)
    result = await db.execute(
        select(AffiliateCode).where(AffiliateCode.client_id == client_id)
    )
    code = result.scalar_one_or_none()
    if code:
        return code

    new_code = AffiliateCode(
        client_id=client_id,
        code=secrets.token_urlsafe(6),
        commission_percent=Decimal("40"),
    )
    db.add(new_code)
    await db.flush()
    await db.commit()
    await db.refresh(new_code)
    return new_code


@router.post("/affiliate/code", response_model=AffiliateCodeOut, status_code=201)
async def create_affiliate_code(
    data: AffiliateCodeCreate,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    client_id = _require_client_id(user)

    # Check if user already has an affiliate code
    existing = await db.execute(
        select(AffiliateCode).where(AffiliateCode.client_id == client_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Affiliate code already exists")

    code_str = data.code or secrets.token_urlsafe(6)

    # Check uniqueness
    dup = await db.execute(select(AffiliateCode).where(AffiliateCode.code == code_str))
    if dup.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Code already taken")

    new_code = AffiliateCode(
        client_id=client_id,
        code=code_str,
        commission_percent=data.commission_percent,
    )
    db.add(new_code)
    await db.flush()
    await db.commit()
    await db.refresh(new_code)
    return new_code


@router.get("/affiliate/referrals", response_model=list[ReferralOut])
async def list_referrals(
    skip: int = 0, limit: int = 50,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    client_id = _require_client_id(user)
    result = await db.execute(
        select(AffiliateCode.id).where(AffiliateCode.client_id == client_id)
    )
    code = result.scalar_one_or_none()
    if not code:
        return []

    stmt = (
        select(AffiliateReferral, Client.name.label("client_name"))
        .join(Client, Client.id == AffiliateReferral.referred_client_id, isouter=True)
        .where(AffiliateReferral.affiliate_code_id == code)
        .order_by(AffiliateReferral.created_at.desc())
        .offset(skip).limit(limit)
    )
    rows = (await db.execute(stmt)).all()
    return [
        ReferralOut(
            id=ref.id,
            affiliate_code_id=ref.affiliate_code_id,
            referred_client_id=ref.referred_client_id,
            status=ref.status,
            total_commission=ref.total_commission,
            created_at=ref.created_at,
            referred_client_name=client_name,
        )
        for ref, client_name in rows
    ]


@router.get("/affiliate/commissions", response_model=list[CommissionOut])
async def list_commissions(
    skip: int = 0, limit: int = 50,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    client_id = _require_client_id(user)
    result = await db.execute(
        select(AffiliateCode.id).where(AffiliateCode.client_id == client_id)
    )
    code_id = result.scalar_one_or_none()
    if not code_id:
        return []

    stmt = (
        select(AffiliateCommission)
        .where(AffiliateCommission.affiliate_code_id == code_id)
        .order_by(AffiliateCommission.created_at.desc())
        .offset(skip).limit(limit)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/affiliate/stats", response_model=AffiliateStats)
async def get_affiliate_stats(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    client_id = _require_client_id(user)
    result = await db.execute(
        select(AffiliateCode).where(AffiliateCode.client_id == client_id)
    )
    code = result.scalar_one_or_none()
    if not code:
        return AffiliateStats(
            total_referrals=0, active_referrals=0,
            total_earnings=Decimal("0"), pending_earnings=Decimal("0"),
            commission_rate=Decimal("40"),
        )

    total_referrals = (await db.execute(
        select(func.count()).select_from(AffiliateReferral)
        .where(AffiliateReferral.affiliate_code_id == code.id)
    )).scalar() or 0

    active_referrals = (await db.execute(
        select(func.count()).select_from(AffiliateReferral)
        .where(AffiliateReferral.affiliate_code_id == code.id, AffiliateReferral.status == "active")
    )).scalar() or 0

    total_earnings = (await db.execute(
        select(func.coalesce(func.sum(AffiliateCommission.amount), 0))
        .where(AffiliateCommission.affiliate_code_id == code.id, AffiliateCommission.status == "paid")
    )).scalar() or Decimal("0")

    pending_earnings = (await db.execute(
        select(func.coalesce(func.sum(AffiliateCommission.amount), 0))
        .where(AffiliateCommission.affiliate_code_id == code.id, AffiliateCommission.status.in_(["pending", "approved"]))
    )).scalar() or Decimal("0")

    return AffiliateStats(
        total_referrals=total_referrals,
        active_referrals=active_referrals,
        total_earnings=total_earnings,
        pending_earnings=pending_earnings,
        commission_rate=code.commission_percent,
    )


# ── Admin-facing endpoints ──


@router.get("/admin/affiliates", response_model=list[AffiliateCodeOut])
async def admin_list_affiliates(
    skip: int = 0, limit: int = 50,
    user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(AffiliateCode)
        .order_by(AffiliateCode.created_at.desc())
        .offset(skip).limit(limit)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/admin/affiliates/{affiliate_id}", response_model=AffiliateCodeOut)
async def admin_get_affiliate(
    affiliate_id: UUID,
    user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AffiliateCode).where(AffiliateCode.id == affiliate_id)
    )
    code = result.scalar_one_or_none()
    if not code:
        raise HTTPException(status_code=404, detail="Affiliate code not found")
    return code


@router.put("/admin/affiliates/{affiliate_id}", response_model=AffiliateCodeOut)
async def admin_update_affiliate(
    affiliate_id: UUID,
    data: AffiliateCodeUpdate,
    user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AffiliateCode).where(AffiliateCode.id == affiliate_id)
    )
    code = result.scalar_one_or_none()
    if not code:
        raise HTTPException(status_code=404, detail="Affiliate code not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(code, k, v)
    await db.flush()
    await db.commit()
    await db.refresh(code)
    return code


@router.get("/admin/referrals", response_model=list[ReferralOut])
async def admin_list_referrals(
    affiliate_code_id: Optional[UUID] = Query(None),
    skip: int = 0, limit: int = 50,
    user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(AffiliateReferral, Client.name.label("client_name"))
        .join(Client, Client.id == AffiliateReferral.referred_client_id, isouter=True)
    )
    if affiliate_code_id:
        stmt = stmt.where(AffiliateReferral.affiliate_code_id == affiliate_code_id)
    stmt = stmt.order_by(AffiliateReferral.created_at.desc()).offset(skip).limit(limit)
    rows = (await db.execute(stmt)).all()
    return [
        ReferralOut(
            id=ref.id,
            affiliate_code_id=ref.affiliate_code_id,
            referred_client_id=ref.referred_client_id,
            status=ref.status,
            total_commission=ref.total_commission,
            created_at=ref.created_at,
            referred_client_name=client_name,
        )
        for ref, client_name in rows
    ]


@router.put("/admin/commissions/{commission_id}/status", response_model=CommissionOut)
async def admin_update_commission_status(
    commission_id: UUID,
    data: CommissionStatusUpdate,
    user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    if data.status not in ("approved", "paid"):
        raise HTTPException(status_code=400, detail="Status must be 'approved' or 'paid'")

    result = await db.execute(
        select(AffiliateCommission).where(AffiliateCommission.id == commission_id)
    )
    commission = result.scalar_one_or_none()
    if not commission:
        raise HTTPException(status_code=404, detail="Commission not found")

    commission.status = data.status
    if data.status == "paid":
        commission.paid_at = datetime.now(timezone.utc)
    await db.flush()
    await db.commit()
    await db.refresh(commission)
    return commission
