from uuid import UUID
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_
from typing import Optional
import logging

from app.database import get_db
from app.models import Alert
from app.auth.dependencies import get_current_user, require_admin
from app.alerts.schemas import AlertOut, AlertCreate, AlertUpdate

log = logging.getLogger(__name__)
router = APIRouter(tags=["alerts"])


# ── Client-facing ──

@router.get("/alerts/active", response_model=list[AlertOut])
async def get_active_alerts(user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    now = datetime.now(timezone.utc)
    stmt = select(Alert).where(
        Alert.is_active == True,
        or_(Alert.starts_at == None, Alert.starts_at <= now),
        or_(Alert.expires_at == None, Alert.expires_at > now),
    )

    client_id = user.get("client_id")
    if client_id:
        stmt = stmt.where(
            or_(
                Alert.scope == "global",
                and_(Alert.scope == "user", Alert.target_client_id == UUID(client_id)),
            )
        )
    else:
        # Admin users see all global alerts
        stmt = stmt.where(Alert.scope == "global")

    stmt = stmt.order_by(Alert.created_at.desc())
    result = await db.execute(stmt)
    return result.scalars().all()


# ── Admin-facing ──

@router.get("/admin/alerts", response_model=list[AlertOut])
async def admin_list_alerts(
    scope: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    skip: int = 0, limit: int = 50,
    user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Alert)
    if scope:
        stmt = stmt.where(Alert.scope == scope)
    if is_active is not None:
        stmt = stmt.where(Alert.is_active == is_active)
    stmt = stmt.order_by(Alert.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/admin/alerts", response_model=AlertOut, status_code=201)
async def admin_create_alert(data: AlertCreate, user: dict = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    alert = Alert(**data.model_dump(), created_by=UUID(user["id"]))
    db.add(alert)
    await db.flush()
    await db.refresh(alert)
    return alert


@router.put("/admin/alerts/{alert_id}", response_model=AlertOut)
async def admin_update_alert(
    alert_id: UUID, data: AlertUpdate,
    user: dict = Depends(require_admin), db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(alert, k, v)
    await db.flush()
    await db.refresh(alert)
    return alert


@router.delete("/admin/alerts/{alert_id}")
async def admin_delete_alert(alert_id: UUID, user: dict = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    await db.delete(alert)
    return {"detail": "Alert deleted"}
