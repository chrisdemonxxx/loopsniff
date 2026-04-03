import uuid
import hashlib
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Campaign, Sequence, SequenceStep, CampaignLead, ABTest
from app.auth.dependencies import get_current_user, require_admin
from app.outreach.campaign_schemas import (
    CampaignCreate,
    CampaignUpdate,
    CampaignOut,
    CampaignLeadEnroll,
    CampaignLeadOut,
    LeadUploadResult,
    BulkLeadUpload,
    SequenceCreate,
    SequenceUpdate,
    SequenceOut,
    ABTestOut,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/outreach/campaigns", tags=["campaigns"])
seq_router = APIRouter(prefix="/outreach/sequences", tags=["campaigns"])


# ═══════════════════════════════════════════════════════════════
#  Campaign CRUD
# ═══════════════════════════════════════════════════════════════

@router.get("", response_model=list[CampaignOut])
async def list_campaigns(
    status: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    stmt = select(Campaign).options(
        selectinload(Campaign.sequence).selectinload(Sequence.steps)
    )
    if status:
        stmt = stmt.where(Campaign.status == status)
    if q:
        stmt = stmt.where(Campaign.name.ilike(f"%{q}%"))
    stmt = stmt.order_by(Campaign.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("", response_model=CampaignOut, status_code=201)
async def create_campaign(
    body: CampaignCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
):
    seq_id = body.sequence_id

    # Inline sequence creation
    if seq_id is None and body.steps:
        seq = Sequence(name=f"{body.name} – sequence")
        db.add(seq)
        await db.flush()
        for step_data in body.steps:
            step = SequenceStep(
                sequence_id=seq.id,
                step_order=step_data.step_order,
                delay_hours=step_data.delay_hours,
                template_a=step_data.template_a,
                template_b=step_data.template_b,
                step_type=step_data.step_type,
            )
            db.add(step)
        await db.flush()
        seq_id = seq.id

    campaign = Campaign(
        name=body.name,
        description=body.description,
        status=body.status,
        target_niche=body.target_niche,
        platform=body.platform,
        sequence_id=seq_id,
        daily_send_cap=body.daily_send_cap,
        send_window_start=body.send_window_start,
        send_window_end=body.send_window_end,
    )
    db.add(campaign)
    await db.flush()
    await db.refresh(campaign, attribute_names=["sequence"])
    return campaign


@router.get("/{campaign_id}", response_model=CampaignOut)
async def get_campaign(
    campaign_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    stmt = (
        select(Campaign)
        .options(selectinload(Campaign.sequence).selectinload(Sequence.steps))
        .where(Campaign.id == campaign_id)
    )
    result = await db.execute(stmt)
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(404, "Campaign not found")

    # Attach lead count
    count_stmt = select(func.count()).where(CampaignLead.campaign_id == campaign_id)
    lead_count = (await db.execute(count_stmt)).scalar() or 0
    campaign.lead_count = lead_count  # type: ignore[attr-defined]
    return campaign


@router.put("/{campaign_id}", response_model=CampaignOut)
async def update_campaign(
    campaign_id: uuid.UUID,
    body: CampaignUpdate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
):
    stmt = select(Campaign).where(Campaign.id == campaign_id)
    result = await db.execute(stmt)
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(404, "Campaign not found")

    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(campaign, field, value)

    await db.flush()
    await db.refresh(campaign, attribute_names=["sequence"])
    return campaign


@router.delete("/{campaign_id}", status_code=204)
async def delete_campaign(
    campaign_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
):
    stmt = select(Campaign).where(Campaign.id == campaign_id)
    result = await db.execute(stmt)
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    if campaign.status != "draft":
        raise HTTPException(400, "Only draft campaigns can be deleted")
    await db.delete(campaign)
    await db.flush()


# ═══════════════════════════════════════════════════════════════
#  Lead enrolment & listing
# ═══════════════════════════════════════════════════════════════

@router.post("/{campaign_id}/enroll", response_model=CampaignLeadOut, status_code=201)
async def enroll_lead(
    campaign_id: uuid.UUID,
    body: CampaignLeadEnroll,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    # Verify campaign exists
    camp = (await db.execute(select(Campaign).where(Campaign.id == campaign_id))).scalar_one_or_none()
    if not camp:
        raise HTTPException(404, "Campaign not found")

    # Dedup within campaign
    dup = (
        await db.execute(
            select(CampaignLead).where(
                CampaignLead.campaign_id == campaign_id,
                CampaignLead.tg_username == body.tg_username,
            )
        )
    ).scalar_one_or_none()
    if dup:
        raise HTTPException(409, "Lead already enrolled in this campaign")

    variant = "A" if int(hashlib.md5(body.tg_username.encode()).hexdigest(), 16) % 2 == 0 else "B"

    lead = CampaignLead(
        campaign_id=campaign_id,
        tg_username=body.tg_username,
        tg_user_id=body.tg_user_id,
        ab_variant=variant,
    )
    db.add(lead)
    camp.total_enrolled = (camp.total_enrolled or 0) + 1
    await db.flush()
    await db.refresh(lead)
    return lead


@router.get("/{campaign_id}/leads", response_model=list[CampaignLeadOut])
async def list_campaign_leads(
    campaign_id: uuid.UUID,
    status: Optional[str] = Query(None),
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    stmt = select(CampaignLead).where(CampaignLead.campaign_id == campaign_id)
    if status:
        stmt = stmt.where(CampaignLead.status == status)
    stmt = stmt.order_by(CampaignLead.enrolled_at.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/{campaign_id}/upload-leads", response_model=LeadUploadResult)
async def upload_leads(
    campaign_id: uuid.UUID,
    body: BulkLeadUpload,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    camp = (await db.execute(select(Campaign).where(Campaign.id == campaign_id))).scalar_one_or_none()
    if not camp:
        raise HTTPException(404, "Campaign not found")

    # Fetch existing usernames for dedup
    existing_stmt = select(CampaignLead.tg_username).where(
        CampaignLead.campaign_id == campaign_id
    )
    existing = set((await db.execute(existing_stmt)).scalars().all())

    imported = 0
    duplicates = 0
    errors = 0

    for item in body.leads:
        if not item.tg_username:
            errors += 1
            continue
        if item.tg_username in existing:
            duplicates += 1
            continue
        variant = "A" if int(hashlib.md5(item.tg_username.encode()).hexdigest(), 16) % 2 == 0 else "B"
        lead = CampaignLead(
            campaign_id=campaign_id,
            tg_username=item.tg_username,
            tg_user_id=item.tg_user_id,
            ab_variant=variant,
        )
        db.add(lead)
        existing.add(item.tg_username)
        imported += 1

    camp.total_enrolled = (camp.total_enrolled or 0) + imported
    await db.flush()

    return LeadUploadResult(
        total=len(body.leads),
        imported=imported,
        duplicates=duplicates,
        errors=errors,
    )


# ═══════════════════════════════════════════════════════════════
#  AB Test results
# ═══════════════════════════════════════════════════════════════

@router.get("/{campaign_id}/ab-results", response_model=list[ABTestOut])
async def get_ab_results(
    campaign_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    stmt = (
        select(ABTest)
        .where(ABTest.campaign_id == campaign_id)
        .order_by(ABTest.created_at)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


# ═══════════════════════════════════════════════════════════════
#  Sequence CRUD (sub-router)
# ═══════════════════════════════════════════════════════════════

@seq_router.get("", response_model=list[SequenceOut])
async def list_sequences(
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    stmt = (
        select(Sequence)
        .options(selectinload(Sequence.steps))
        .order_by(Sequence.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


@seq_router.post("", response_model=SequenceOut, status_code=201)
async def create_sequence(
    body: SequenceCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
):
    seq = Sequence(name=body.name, description=body.description)
    db.add(seq)
    await db.flush()

    for step_data in body.steps:
        step = SequenceStep(
            sequence_id=seq.id,
            step_order=step_data.step_order,
            delay_hours=step_data.delay_hours,
            template_a=step_data.template_a,
            template_b=step_data.template_b,
            step_type=step_data.step_type,
        )
        db.add(step)

    await db.flush()
    await db.refresh(seq, attribute_names=["steps"])
    return seq


@seq_router.get("/{sequence_id}", response_model=SequenceOut)
async def get_sequence(
    sequence_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    stmt = (
        select(Sequence)
        .options(selectinload(Sequence.steps))
        .where(Sequence.id == sequence_id)
    )
    result = await db.execute(stmt)
    seq = result.scalar_one_or_none()
    if not seq:
        raise HTTPException(404, "Sequence not found")
    return seq


@seq_router.put("/{sequence_id}", response_model=SequenceOut)
async def update_sequence(
    sequence_id: uuid.UUID,
    body: SequenceUpdate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
):
    stmt = (
        select(Sequence)
        .options(selectinload(Sequence.steps))
        .where(Sequence.id == sequence_id)
    )
    result = await db.execute(stmt)
    seq = result.scalar_one_or_none()
    if not seq:
        raise HTTPException(404, "Sequence not found")

    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(seq, field, value)

    await db.flush()
    await db.refresh(seq, attribute_names=["steps"])
    return seq
