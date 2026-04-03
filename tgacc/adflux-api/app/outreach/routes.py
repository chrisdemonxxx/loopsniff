import os
import uuid
import logging
import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional

from app.database import get_db
from app.models import OutreachLead
from app.auth.dependencies import get_current_user, require_admin
from app.outreach.schemas import (
    OutreachLeadOut, OutreachLeadUpdate, OutreachLeadCreate, FunnelStats,
)
from app.config import get_settings

log = logging.getLogger(__name__)
router = APIRouter(prefix="/outreach", tags=["outreach"])
settings = get_settings()


# ── PostgreSQL-backed endpoints (primary) ──

@router.get("/leads", response_model=list[OutreachLeadOut])
async def list_leads(
    stage: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    skip: int = 0, limit: int = 50,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(OutreachLead)
    if stage:
        stmt = stmt.where(OutreachLead.stage == stage)
    if source:
        stmt = stmt.where(OutreachLead.source == source)
    if q:
        stmt = stmt.where(OutreachLead.tg_username.ilike(f"%{q}%"))
    stmt = stmt.order_by(OutreachLead.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/leads/{lead_id}", response_model=OutreachLeadOut)
async def get_lead(lead_id: uuid.UUID, user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(OutreachLead).where(OutreachLead.id == lead_id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead


@router.post("/leads", response_model=OutreachLeadOut, status_code=201)
async def create_lead(data: OutreachLeadCreate, user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    lead = OutreachLead(**data.model_dump())
    db.add(lead)
    await db.flush()
    await db.refresh(lead)
    return lead


@router.put("/leads/{lead_id}", response_model=OutreachLeadOut)
async def update_lead(
    lead_id: uuid.UUID, data: OutreachLeadUpdate,
    user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(OutreachLead).where(OutreachLead.id == lead_id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(lead, k, v)
    await db.flush()
    await db.refresh(lead)
    return lead


@router.delete("/leads/{lead_id}")
async def delete_lead(lead_id: uuid.UUID, user: dict = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(OutreachLead).where(OutreachLead.id == lead_id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    await db.delete(lead)
    return {"detail": "Lead deleted"}


@router.get("/funnel", response_model=FunnelStats)
async def funnel_stats(user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    total = (await db.execute(select(func.count(OutreachLead.id)))).scalar() or 0
    stages = {}
    for stage_name in ("new", "contacted", "qualified", "proposal", "converted", "lost"):
        count = (await db.execute(
            select(func.count(OutreachLead.id)).where(OutreachLead.stage == stage_name)
        )).scalar() or 0
        stages[stage_name] = count
    return FunnelStats(total=total, **stages)


# ── SQLite bridge to existing outreach DB ──

@router.get("/sqlite/leads")
async def sqlite_leads(
    stage: Optional[str] = Query(None),
    limit: int = 50,
    user: dict = Depends(get_current_user),
):
    db_path = settings.OUTREACH_DB_PATH
    if not os.path.exists(db_path):
        raise HTTPException(status_code=404, detail="Outreach SQLite DB not found")

    try:
        async with aiosqlite.connect(db_path) as db:
            db.row_factory = aiosqlite.Row
            query = "SELECT * FROM leads"
            params = []
            if stage:
                query += " WHERE status = ?"
                params.append(stage)
            query += " ORDER BY rowid DESC LIMIT ?"
            params.append(limit)
            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        log.error("SQLite bridge error: %s", e)
        raise HTTPException(status_code=500, detail="Error reading outreach DB")


@router.get("/sqlite/stats")
async def sqlite_stats(user: dict = Depends(get_current_user)):
    db_path = settings.OUTREACH_DB_PATH
    if not os.path.exists(db_path):
        raise HTTPException(status_code=404, detail="Outreach SQLite DB not found")

    try:
        async with aiosqlite.connect(db_path) as db:
            cursor = await db.execute("SELECT status, COUNT(*) as cnt FROM leads GROUP BY status")
            rows = await cursor.fetchall()
            return {row[0]: row[1] for row in rows}
    except Exception as e:
        log.error("SQLite bridge error: %s", e)
        raise HTTPException(status_code=500, detail="Error reading outreach DB")


# ── SQLite conversation monitoring ──

@router.get("/sqlite/conversations")
async def sqlite_conversations(
    limit: int = Query(50, ge=1, le=500),
    skip: int = Query(0, ge=0),
    status: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    user: dict = Depends(get_current_user),
):
    db_path = settings.OUTREACH_DB_PATH
    if not os.path.exists(db_path):
        raise HTTPException(status_code=404, detail="Outreach SQLite DB not found")

    try:
        async with aiosqlite.connect(db_path) as db:
            db.row_factory = aiosqlite.Row
            query = """
                SELECT l.username, l.status, l.source, l.contacted_by, l.bant_score, l.notes,
                       l.contacted_at,
                       COUNT(m.id) as message_count,
                       SUM(CASE WHEN m.direction = 'inbound' THEN 1 ELSE 0 END) as incoming_count,
                       MAX(m.sent_at) as last_message_at,
                       (SELECT m2.text FROM messages m2 WHERE m2.lead_username = l.username ORDER BY m2.sent_at DESC LIMIT 1) as last_message_preview
                FROM leads l
                JOIN messages m ON m.lead_username = l.username
            """
            conditions = []
            params: list = []
            if status:
                conditions.append("l.status = ?")
                params.append(status)
            if q:
                conditions.append("l.username LIKE ?")
                params.append(f"%{q}%")
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            query += """
                GROUP BY l.username
                ORDER BY MAX(m.sent_at) DESC
                LIMIT ? OFFSET ?
            """
            params.extend([limit, skip])
            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        log.error("SQLite bridge error: %s", e)
        raise HTTPException(status_code=500, detail="Error reading outreach DB")


@router.get("/sqlite/conversations/active")
async def sqlite_conversations_active(
    hours: int = Query(24, ge=1, le=720),
    user: dict = Depends(get_current_user),
):
    db_path = settings.OUTREACH_DB_PATH
    if not os.path.exists(db_path):
        raise HTTPException(status_code=404, detail="Outreach SQLite DB not found")

    try:
        async with aiosqlite.connect(db_path) as db:
            db.row_factory = aiosqlite.Row
            query = """
                SELECT l.username, l.status, l.bant_score, l.contacted_by,
                       COUNT(m.id) as message_count,
                       MAX(m.sent_at) as last_message_at
                FROM leads l
                JOIN messages m ON m.lead_username = l.username
                WHERE m.sent_at >= datetime('now', '-' || ? || ' hours')
                GROUP BY l.username
                ORDER BY MAX(m.sent_at) DESC
            """
            cursor = await db.execute(query, [str(hours)])
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        log.error("SQLite bridge error: %s", e)
        raise HTTPException(status_code=500, detail="Error reading outreach DB")


@router.get("/sqlite/conversations/{username}/messages")
async def sqlite_conversation_messages(
    username: str,
    limit: int = Query(200, ge=1, le=1000),
    skip: int = Query(0, ge=0),
    user: dict = Depends(get_current_user),
):
    db_path = settings.OUTREACH_DB_PATH
    if not os.path.exists(db_path):
        raise HTTPException(status_code=404, detail="Outreach SQLite DB not found")

    try:
        async with aiosqlite.connect(db_path) as db:
            db.row_factory = aiosqlite.Row

            # Fetch lead info
            cursor = await db.execute("SELECT * FROM leads WHERE username = ?", [username])
            lead_row = await cursor.fetchone()
            if not lead_row:
                raise HTTPException(status_code=404, detail="Lead not found")
            lead = dict(lead_row)

            # Total message count
            cursor = await db.execute(
                "SELECT COUNT(*) FROM messages WHERE lead_username = ?", [username]
            )
            total = (await cursor.fetchone())[0]

            # Fetch messages
            cursor = await db.execute(
                """
                SELECT m.id, m.lead_username, m.account_phone, m.direction, m.text, m.sent_at, m.template_id
                FROM messages m
                WHERE m.lead_username = ?
                ORDER BY m.sent_at ASC
                LIMIT ? OFFSET ?
                """,
                [username, limit, skip],
            )
            rows = await cursor.fetchall()
            messages = [dict(row) for row in rows]

            return {"lead": lead, "messages": messages, "total": total}
    except HTTPException:
        raise
    except Exception as e:
        log.error("SQLite bridge error: %s", e)
        raise HTTPException(status_code=500, detail="Error reading outreach DB")
