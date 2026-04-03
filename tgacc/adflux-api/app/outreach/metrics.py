import os
import uuid
import logging

import aiosqlite
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models import (
    Campaign,
    CampaignLead,
    ABTest,
    SequenceStep,
    Sequence,
    OutreachLead,
)
from app.auth.dependencies import get_current_user
from app.config import get_settings
from app.outreach.metrics_schemas import (
    OverallMetrics,
    CampaignMetrics,
    StepMetrics,
    ABResult,
    DailySendStats,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/outreach/metrics", tags=["outreach-metrics"])


async def _get_sqlite_path() -> str:
    settings = get_settings()
    return settings.OUTREACH_DB_PATH


# ---------- a) Overall metrics ----------


@router.get("", response_model=OverallMetrics)
async def get_overall_metrics(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Overall metrics combining PostgreSQL lead stages and SQLite message counts."""

    # --- PostgreSQL: count OutreachLead by stage ---
    stage_query = select(
        OutreachLead.stage, func.count(OutreachLead.id)
    ).group_by(OutreachLead.stage)
    result = await db.execute(stage_query)
    stage_counts: dict[str, int] = {row[0]: row[1] for row in result.all()}

    total_leads = sum(stage_counts.values())
    total_contacted = stage_counts.get("contacted", 0)
    total_replied = stage_counts.get("replied", 0)
    total_qualified = stage_counts.get("qualified", 0)
    total_converted = stage_counts.get("converted", 0)
    total_lost = stage_counts.get("lost", 0)

    # --- SQLite: message stats ---
    avg_messages_per_lead = 0.0
    sqlite_path = await _get_sqlite_path()
    if os.path.exists(sqlite_path):
        try:
            async with aiosqlite.connect(sqlite_path) as sdb:
                cursor = await sdb.execute(
                    "SELECT COUNT(*) as total_msgs, "
                    "COUNT(DISTINCT tg_user_id) as unique_leads "
                    "FROM messages WHERE direction = 'outbound'"
                )
                row = await cursor.fetchone()
                if row and row[1]:
                    avg_messages_per_lead = round(row[0] / row[1], 2)
        except Exception:
            logger.exception("Failed to read SQLite for overall metrics")

    reply_rate = round(total_replied / total_contacted, 4) if total_contacted else 0.0
    qualification_rate = (
        round(total_qualified / total_contacted, 4) if total_contacted else 0.0
    )
    conversion_rate = (
        round(total_converted / total_leads, 4) if total_leads else 0.0
    )

    return OverallMetrics(
        total_leads=total_leads,
        total_contacted=total_contacted,
        total_replied=total_replied,
        total_qualified=total_qualified,
        total_converted=total_converted,
        total_lost=total_lost,
        reply_rate=reply_rate,
        qualification_rate=qualification_rate,
        conversion_rate=conversion_rate,
        avg_messages_per_lead=avg_messages_per_lead,
    )


# ---------- b) Per-campaign metrics ----------


@router.get("/campaigns", response_model=list[CampaignMetrics])
async def get_campaign_metrics(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Per-campaign metrics with lead counts grouped by status."""

    campaigns_result = await db.execute(select(Campaign))
    campaigns = campaigns_result.scalars().all()

    metrics: list[CampaignMetrics] = []
    for campaign in campaigns:
        status_query = (
            select(CampaignLead.status, func.count(CampaignLead.id))
            .where(CampaignLead.campaign_id == campaign.id)
            .group_by(CampaignLead.status)
        )
        result = await db.execute(status_query)
        status_counts: dict[str, int] = {row[0]: row[1] for row in result.all()}

        enrolled = sum(status_counts.values())
        sent = status_counts.get("in_sequence", 0) + status_counts.get("replied", 0) + status_counts.get("converted", 0)
        replied = status_counts.get("replied", 0)
        converted = status_counts.get("converted", 0)

        reply_rate = round(replied / sent, 4) if sent else 0.0
        conversion_rate = round(converted / enrolled, 4) if enrolled else 0.0

        metrics.append(
            CampaignMetrics(
                campaign_id=str(campaign.id),
                campaign_name=campaign.name,
                enrolled=enrolled,
                sent=sent,
                replied=replied,
                converted=converted,
                reply_rate=reply_rate,
                conversion_rate=conversion_rate,
            )
        )

    return metrics


# ---------- c) Per-step drop-off ----------


@router.get("/campaigns/{campaign_id}/steps", response_model=list[StepMetrics])
async def get_step_metrics(
    campaign_id: str,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Per-step drop-off metrics for a campaign's sequence."""

    cid = uuid.UUID(campaign_id)

    # Get the campaign's sequence
    campaign_result = await db.execute(
        select(Campaign).where(Campaign.id == cid)
    )
    campaign = campaign_result.scalar_one_or_none()
    if not campaign or not campaign.sequence_id:
        return []

    # Get sequence steps ordered by step_order
    steps_result = await db.execute(
        select(SequenceStep)
        .where(SequenceStep.sequence_id == campaign.sequence_id)
        .order_by(SequenceStep.step_order)
    )
    steps = steps_result.scalars().all()
    if not steps:
        return []

    # Count leads that reached each step (current_step >= step_order)
    metrics: list[StepMetrics] = []
    prev_sent = None

    for step in steps:
        sent_query = (
            select(func.count(CampaignLead.id))
            .where(
                CampaignLead.campaign_id == cid,
                CampaignLead.current_step >= step.step_order,
            )
        )
        sent_result = await db.execute(sent_query)
        sent = sent_result.scalar() or 0

        replied_query = (
            select(func.count(CampaignLead.id))
            .where(
                CampaignLead.campaign_id == cid,
                CampaignLead.current_step == step.step_order,
                CampaignLead.status == "replied",
            )
        )
        replied_result = await db.execute(replied_query)
        replied = replied_result.scalar() or 0

        drop_off_rate = 0.0
        if prev_sent is not None and prev_sent > 0:
            drop_off_rate = round(1 - (sent / prev_sent), 4)

        metrics.append(
            StepMetrics(
                step_order=step.step_order,
                template_a_preview=(step.template_a[:80] if step.template_a else None),
                template_b_preview=(step.template_b[:80] if step.template_b else None),
                sent=sent,
                replied=replied,
                drop_off_rate=drop_off_rate,
            )
        )
        prev_sent = sent

    return metrics


# ---------- d) A/B test results ----------


@router.get("/campaigns/{campaign_id}/ab", response_model=list[ABResult])
async def get_ab_results(
    campaign_id: str,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """A/B test results for a campaign."""

    cid = uuid.UUID(campaign_id)

    ab_query = (
        select(ABTest, SequenceStep.step_order)
        .join(SequenceStep, ABTest.step_id == SequenceStep.id)
        .where(ABTest.campaign_id == cid)
        .order_by(SequenceStep.step_order)
    )
    result = await db.execute(ab_query)
    rows = result.all()

    results: list[ABResult] = []
    for ab, step_order in rows:
        a_rate = (
            round(ab.variant_a_replied / ab.variant_a_sent, 4)
            if ab.variant_a_sent
            else 0.0
        )
        b_rate = (
            round(ab.variant_b_replied / ab.variant_b_sent, 4)
            if ab.variant_b_sent
            else 0.0
        )

        winner = ab.winner
        if winner is None and ab.variant_a_sent and ab.variant_b_sent:
            winner = "A" if a_rate > b_rate else ("B" if b_rate > a_rate else None)

        significance = float(ab.significance) if ab.significance is not None else None

        results.append(
            ABResult(
                step_order=step_order,
                variant_a_sent=ab.variant_a_sent,
                variant_a_replied=ab.variant_a_replied,
                variant_a_rate=a_rate,
                variant_b_sent=ab.variant_b_sent,
                variant_b_replied=ab.variant_b_replied,
                variant_b_rate=b_rate,
                winner=winner,
                significance=significance,
            )
        )

    return results


# ---------- e) Daily send/reply stats ----------


@router.get("/daily", response_model=list[DailySendStats])
async def get_daily_stats(
    days: int = Query(default=30, ge=1, le=365),
    _user: dict = Depends(get_current_user),
):
    """Daily send and reply counts from the SQLite outreach database."""

    sqlite_path = await _get_sqlite_path()
    if not os.path.exists(sqlite_path):
        return []

    try:
        async with aiosqlite.connect(sqlite_path) as sdb:
            sdb.row_factory = aiosqlite.Row
            cursor = await sdb.execute(
                "SELECT date(sent_at) as day, "
                "COUNT(*) as sent, "
                "SUM(CASE WHEN direction = 'inbound' THEN 1 ELSE 0 END) as replied "
                "FROM messages "
                "WHERE sent_at >= date('now', ?) "
                "GROUP BY date(sent_at) "
                "ORDER BY day DESC",
                (f"-{days} days",),
            )
            rows = await cursor.fetchall()

        return [
            DailySendStats(
                date=row["day"],
                sent=row["sent"],
                replied=row["replied"] or 0,
            )
            for row in rows
        ]
    except Exception:
        logger.exception("Failed to read SQLite for daily stats")
        return []
