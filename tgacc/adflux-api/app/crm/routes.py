from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload
from typing import Optional

from app.database import get_db
from app.models import CRMLead, TeamTarget, AdminUser, Client
from app.auth.dependencies import require_admin
from app.crm.schemas import (
    CRMLeadOut, CRMLeadCreate, CRMLeadUpdate, CRMLeadBulkImport,
    CRMLeadStats, TeamTargetOut, TeamTargetCreate,
)

router = APIRouter(prefix="/crm", tags=["crm"])


def _calc_bant_score(lead) -> int:
    score = 0
    if lead.budget:
        score += 25
    if lead.authority:
        score += 25
    if lead.need:
        score += 25
    if lead.timeline:
        score += 25
    return score


def _lead_to_out(lead: CRMLead) -> dict:
    data = {c.key: getattr(lead, c.key) for c in CRMLead.__table__.columns}
    data["assigned_bdm_name"] = lead.assigned_bdm.name if lead.assigned_bdm else None
    return data


# ── Lead Management ──


@router.get("/leads/stats", response_model=CRMLeadStats)
async def lead_stats(user: dict = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    total = (await db.execute(select(func.count(CRMLead.id)))).scalar() or 0

    status_rows = (await db.execute(
        select(CRMLead.status, func.count(CRMLead.id)).group_by(CRMLead.status)
    )).all()
    by_status = {row[0] or "unknown": row[1] for row in status_rows}

    priority_rows = (await db.execute(
        select(CRMLead.priority, func.count(CRMLead.id)).group_by(CRMLead.priority)
    )).all()
    by_priority = {row[0] or "unknown": row[1] for row in priority_rows}

    source_rows = (await db.execute(
        select(CRMLead.source, func.count(CRMLead.id)).group_by(CRMLead.source)
    )).all()
    by_source = {(row[0] or "unknown"): row[1] for row in source_rows}

    avg_bant = (await db.execute(
        select(func.coalesce(func.avg(CRMLead.bant_score), 0))
    )).scalar()

    return CRMLeadStats(
        total=total, by_status=by_status, by_priority=by_priority,
        by_source=by_source, avg_bant_score=float(avg_bant),
    )


@router.get("/leads", response_model=list[CRMLeadOut])
async def list_leads(
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    assigned_bdm_id: Optional[UUID] = Query(None),
    search: Optional[str] = Query(None),
    sort_by: str = Query("created_at"),
    sort_dir: str = Query("desc"),
    offset: int = 0,
    limit: int = 50,
    user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(CRMLead).options(selectinload(CRMLead.assigned_bdm))
    if status:
        stmt = stmt.where(CRMLead.status == status)
    if priority:
        stmt = stmt.where(CRMLead.priority == priority)
    if source:
        stmt = stmt.where(CRMLead.source == source)
    if assigned_bdm_id:
        stmt = stmt.where(CRMLead.assigned_bdm_id == assigned_bdm_id)
    if search:
        stmt = stmt.where(or_(
            CRMLead.name.ilike(f"%{search}%"),
            CRMLead.email.ilike(f"%{search}%"),
            CRMLead.company.ilike(f"%{search}%"),
        ))
    col = getattr(CRMLead, sort_by, CRMLead.created_at)
    stmt = stmt.order_by(col.desc() if sort_dir == "desc" else col.asc())
    stmt = stmt.offset(offset).limit(limit)
    result = await db.execute(stmt)
    leads = result.scalars().all()
    return [_lead_to_out(l) for l in leads]


@router.post("/leads", response_model=CRMLeadOut, status_code=201)
async def create_lead(data: CRMLeadCreate, user: dict = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    lead = CRMLead(**data.model_dump())
    lead.bant_score = _calc_bant_score(lead)
    db.add(lead)
    await db.flush()
    await db.refresh(lead, attribute_names=["assigned_bdm"])
    return _lead_to_out(lead)


@router.get("/leads/{lead_id}", response_model=CRMLeadOut)
async def get_lead(lead_id: UUID, user: dict = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    stmt = select(CRMLead).options(selectinload(CRMLead.assigned_bdm)).where(CRMLead.id == lead_id)
    result = await db.execute(stmt)
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return _lead_to_out(lead)


@router.put("/leads/{lead_id}", response_model=CRMLeadOut)
async def update_lead(
    lead_id: UUID, data: CRMLeadUpdate,
    user: dict = Depends(require_admin), db: AsyncSession = Depends(get_db),
):
    stmt = select(CRMLead).options(selectinload(CRMLead.assigned_bdm)).where(CRMLead.id == lead_id)
    result = await db.execute(stmt)
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(lead, k, v)
    lead.bant_score = _calc_bant_score(lead)
    await db.flush()
    await db.refresh(lead, attribute_names=["assigned_bdm"])
    return _lead_to_out(lead)


@router.delete("/leads/{lead_id}")
async def delete_lead(lead_id: UUID, user: dict = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(CRMLead).where(CRMLead.id == lead_id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    await db.delete(lead)
    return {"detail": "Lead deleted"}


@router.post("/leads/bulk", response_model=dict, status_code=201)
async def bulk_import_leads(
    data: CRMLeadBulkImport,
    user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    created = 0
    updated = 0
    skipped = 0
    for item in data.leads:
        dump = item.model_dump()
        if item.email:
            existing = (await db.execute(
                select(CRMLead).where(CRMLead.email == item.email)
            )).scalar_one_or_none()
            if existing:
                for k, v in dump.items():
                    if v is not None:
                        setattr(existing, k, v)
                existing.bant_score = _calc_bant_score(existing)
                updated += 1
                continue
        lead = CRMLead(**dump)
        lead.bant_score = _calc_bant_score(lead)
        db.add(lead)
        created += 1
    await db.flush()
    return {"created": created, "updated": updated, "skipped": skipped}


@router.put("/leads/{lead_id}/assign", response_model=CRMLeadOut)
async def assign_lead(
    lead_id: UUID,
    assigned_bdm_id: UUID = Query(...),
    user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(CRMLead).options(selectinload(CRMLead.assigned_bdm)).where(CRMLead.id == lead_id)
    result = await db.execute(stmt)
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    bdm = (await db.execute(select(AdminUser).where(AdminUser.id == assigned_bdm_id))).scalar_one_or_none()
    if not bdm:
        raise HTTPException(status_code=404, detail="BDM user not found")
    lead.assigned_bdm_id = assigned_bdm_id
    await db.flush()
    await db.refresh(lead, attribute_names=["assigned_bdm"])
    return _lead_to_out(lead)


@router.put("/leads/{lead_id}/convert", response_model=CRMLeadOut)
async def convert_lead(
    lead_id: UUID,
    user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(CRMLead).options(selectinload(CRMLead.assigned_bdm)).where(CRMLead.id == lead_id)
    result = await db.execute(stmt)
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    if lead.converted_client_id:
        raise HTTPException(status_code=400, detail="Lead already converted")
    client = Client(
        name=lead.name,
        company=lead.company,
        email=lead.email,
        tg_username=lead.telegram_username,
        notes=f"Converted from CRM lead. Source: {lead.source or 'N/A'}",
    )
    db.add(client)
    await db.flush()
    lead.converted_client_id = client.id
    lead.status = "converted"
    await db.flush()
    await db.refresh(lead, attribute_names=["assigned_bdm"])
    return _lead_to_out(lead)


# ── Team Targets ──


@router.get("/targets", response_model=list[TeamTargetOut])
async def list_targets(
    skip: int = 0, limit: int = 50,
    user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(TeamTarget)
        .options(selectinload(TeamTarget.admin))
        .order_by(TeamTarget.created_at.desc())
        .offset(skip).limit(limit)
    )
    result = await db.execute(stmt)
    targets = result.scalars().all()
    out = []
    for t in targets:
        data = {c.key: getattr(t, c.key) for c in TeamTarget.__table__.columns}
        data["admin_name"] = t.admin.name if t.admin else None
        out.append(data)
    return out


@router.post("/targets", response_model=TeamTargetOut, status_code=201)
async def create_target(data: TeamTargetCreate, user: dict = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    target = TeamTarget(**data.model_dump(), achieved_value=0)
    db.add(target)
    await db.flush()
    await db.refresh(target, attribute_names=["admin"])
    data_out = {c.key: getattr(target, c.key) for c in TeamTarget.__table__.columns}
    data_out["admin_name"] = target.admin.name if target.admin else None
    return data_out


@router.put("/targets/{target_id}", response_model=TeamTargetOut)
async def update_target(
    target_id: UUID, data: TeamTargetCreate,
    user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(TeamTarget).options(selectinload(TeamTarget.admin)).where(TeamTarget.id == target_id)
    result = await db.execute(stmt)
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(target, k, v)
    await db.flush()
    await db.refresh(target, attribute_names=["admin"])
    data_out = {c.key: getattr(target, c.key) for c in TeamTarget.__table__.columns}
    data_out["admin_name"] = target.admin.name if target.admin else None
    return data_out


@router.delete("/targets/{target_id}")
async def delete_target(target_id: UUID, user: dict = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(TeamTarget).where(TeamTarget.id == target_id))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")
    await db.delete(target)
    return {"detail": "Target deleted"}
