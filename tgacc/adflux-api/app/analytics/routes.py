import csv
import io
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import AdAccount, SpendingRecord
from app.analytics.schemas import (
    OverviewMetrics,
    CampaignMetrics,
    DailyMetrics,
    PlatformMetrics,
    TopPerformingItem,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/analytics", tags=["Analytics"])


def _client_filter(user: dict):
    """Return client_id UUID if user is a client, else None (admin sees all)."""
    if user.get("user_type") == "client" and user.get("client_id"):
        return UUID(user["client_id"])
    return None


def _parse_date(value: str | None, default: date) -> date:
    if not value:
        return default
    try:
        return date.fromisoformat(value)
    except ValueError:
        return default


# ── Overview ──

@router.get("/overview", response_model=OverviewMetrics)
async def analytics_overview(
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Overall performance: spend, impressions, clicks, conversions, ROAS."""
    d_start = _parse_date(start_date, date.today() - timedelta(days=30))
    d_end = _parse_date(end_date, date.today())
    client_id = _client_filter(user)

    base = select(
        func.coalesce(func.sum(SpendingRecord.spend), 0).label("total_spend"),
        func.coalesce(func.sum(SpendingRecord.impressions), 0).label("total_impressions"),
        func.coalesce(func.sum(SpendingRecord.clicks), 0).label("total_clicks"),
        func.coalesce(func.sum(SpendingRecord.conversions), 0).label("total_conversions"),
    ).join(AdAccount, SpendingRecord.account_id == AdAccount.id).where(
        SpendingRecord.date.between(d_start, d_end)
    )
    if client_id:
        base = base.where(AdAccount.client_id == client_id)

    row = (await db.execute(base)).one()

    # Active accounts
    acct_stmt = select(func.count(AdAccount.id)).where(AdAccount.status == "active")
    if client_id:
        acct_stmt = acct_stmt.where(AdAccount.client_id == client_id)
    active_accounts = (await db.execute(acct_stmt)).scalar() or 0

    spend = Decimal(str(row.total_spend))
    clicks = int(row.total_clicks)
    impressions = int(row.total_impressions)
    conversions = int(row.total_conversions)

    ctr = (Decimal(clicks) / Decimal(impressions) * 100) if impressions else None
    cpc = (spend / Decimal(clicks)) if clicks else None

    return OverviewMetrics(
        total_spend=spend,
        total_impressions=impressions,
        total_clicks=clicks,
        total_conversions=conversions,
        ctr=ctr,
        cpc=cpc,
        active_accounts=active_accounts,
    )


# ── Per-Campaign Breakdown ──

@router.get("/campaigns", response_model=list[CampaignMetrics])
async def analytics_campaigns(
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    platform: str | None = Query(None),
    skip: int = 0,
    limit: int = 50,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Per-account campaign breakdown with date range filter."""
    d_start = _parse_date(start_date, date.today() - timedelta(days=30))
    d_end = _parse_date(end_date, date.today())
    client_id = _client_filter(user)

    stmt = (
        select(
            AdAccount.id.label("account_id"),
            AdAccount.name.label("account_name"),
            AdAccount.platform,
            SpendingRecord.date,
            func.sum(SpendingRecord.spend).label("spend"),
            func.sum(SpendingRecord.impressions).label("impressions"),
            func.sum(SpendingRecord.clicks).label("clicks"),
            func.sum(SpendingRecord.conversions).label("conversions"),
        )
        .join(AdAccount, SpendingRecord.account_id == AdAccount.id)
        .where(SpendingRecord.date.between(d_start, d_end))
        .group_by(AdAccount.id, AdAccount.name, AdAccount.platform, SpendingRecord.date)
        .order_by(SpendingRecord.date.desc())
        .offset(skip)
        .limit(limit)
    )
    if client_id:
        stmt = stmt.where(AdAccount.client_id == client_id)
    if platform:
        stmt = stmt.where(AdAccount.platform == platform)

    rows = (await db.execute(stmt)).all()
    results = []
    for r in rows:
        imp = int(r.impressions or 0)
        clk = int(r.clicks or 0)
        sp = Decimal(str(r.spend or 0))
        results.append(
            CampaignMetrics(
                account_id=r.account_id,
                account_name=r.account_name,
                platform=r.platform,
                date=r.date,
                spend=sp,
                impressions=imp,
                clicks=clk,
                conversions=int(r.conversions or 0),
                ctr=(Decimal(clk) / Decimal(imp) * 100) if imp else None,
                cpc=(sp / Decimal(clk)) if clk else None,
            )
        )
    return results


# ── Daily Timeseries ──

@router.get("/daily", response_model=list[DailyMetrics])
async def analytics_daily(
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Daily metrics timeseries."""
    d_start = _parse_date(start_date, date.today() - timedelta(days=30))
    d_end = _parse_date(end_date, date.today())
    client_id = _client_filter(user)

    stmt = (
        select(
            SpendingRecord.date,
            func.coalesce(func.sum(SpendingRecord.spend), 0).label("spend"),
            func.coalesce(func.sum(SpendingRecord.impressions), 0).label("impressions"),
            func.coalesce(func.sum(SpendingRecord.clicks), 0).label("clicks"),
            func.coalesce(func.sum(SpendingRecord.conversions), 0).label("conversions"),
        )
        .join(AdAccount, SpendingRecord.account_id == AdAccount.id)
        .where(SpendingRecord.date.between(d_start, d_end))
        .group_by(SpendingRecord.date)
        .order_by(SpendingRecord.date)
    )
    if client_id:
        stmt = stmt.where(AdAccount.client_id == client_id)

    rows = (await db.execute(stmt)).all()
    return [
        DailyMetrics(
            date=r.date,
            spend=Decimal(str(r.spend)),
            impressions=int(r.impressions),
            clicks=int(r.clicks),
            conversions=int(r.conversions),
        )
        for r in rows
    ]


# ── Platform Breakdown ──

@router.get("/platforms", response_model=list[PlatformMetrics])
async def analytics_platforms(
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Performance breakdown by platform."""
    d_start = _parse_date(start_date, date.today() - timedelta(days=30))
    d_end = _parse_date(end_date, date.today())
    client_id = _client_filter(user)

    stmt = (
        select(
            AdAccount.platform,
            func.coalesce(func.sum(SpendingRecord.spend), 0).label("spend"),
            func.coalesce(func.sum(SpendingRecord.impressions), 0).label("impressions"),
            func.coalesce(func.sum(SpendingRecord.clicks), 0).label("clicks"),
            func.coalesce(func.sum(SpendingRecord.conversions), 0).label("conversions"),
            func.count(func.distinct(AdAccount.id)).label("accounts"),
        )
        .join(AdAccount, SpendingRecord.account_id == AdAccount.id)
        .where(SpendingRecord.date.between(d_start, d_end))
        .group_by(AdAccount.platform)
    )
    if client_id:
        stmt = stmt.where(AdAccount.client_id == client_id)

    rows = (await db.execute(stmt)).all()
    return [
        PlatformMetrics(
            platform=r.platform,
            spend=Decimal(str(r.spend)),
            impressions=int(r.impressions),
            clicks=int(r.clicks),
            conversions=int(r.conversions),
            accounts=int(r.accounts),
        )
        for r in rows
    ]


# ── Top Performing ──

@router.get("/top-performing", response_model=list[TopPerformingItem])
async def analytics_top_performing(
    metric: str = Query("spend", regex="^(spend|impressions|clicks|conversions)$"),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    limit: int = Query(10, le=50),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Top campaigns/accounts by a given metric."""
    d_start = _parse_date(start_date, date.today() - timedelta(days=30))
    d_end = _parse_date(end_date, date.today())
    client_id = _client_filter(user)

    metric_col = {
        "spend": func.sum(SpendingRecord.spend),
        "impressions": func.sum(SpendingRecord.impressions),
        "clicks": func.sum(SpendingRecord.clicks),
        "conversions": func.sum(SpendingRecord.conversions),
    }[metric]

    stmt = (
        select(
            AdAccount.id.label("account_id"),
            AdAccount.name.label("account_name"),
            AdAccount.platform,
            metric_col.label("metric_value"),
            func.coalesce(func.sum(SpendingRecord.spend), 0).label("spend"),
            func.coalesce(func.sum(SpendingRecord.impressions), 0).label("impressions"),
            func.coalesce(func.sum(SpendingRecord.clicks), 0).label("clicks"),
            func.coalesce(func.sum(SpendingRecord.conversions), 0).label("conversions"),
        )
        .join(AdAccount, SpendingRecord.account_id == AdAccount.id)
        .where(SpendingRecord.date.between(d_start, d_end))
        .group_by(AdAccount.id, AdAccount.name, AdAccount.platform)
        .order_by(metric_col.desc())
        .limit(limit)
    )
    if client_id:
        stmt = stmt.where(AdAccount.client_id == client_id)

    rows = (await db.execute(stmt)).all()
    return [
        TopPerformingItem(
            account_id=r.account_id,
            account_name=r.account_name,
            platform=r.platform,
            metric_value=Decimal(str(r.metric_value or 0)),
            spend=Decimal(str(r.spend)),
            impressions=int(r.impressions),
            clicks=int(r.clicks),
            conversions=int(r.conversions),
        )
        for r in rows
    ]


# ── CSV Export ──

@router.get("/export")
async def analytics_export(
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Export analytics as CSV."""
    d_start = _parse_date(start_date, date.today() - timedelta(days=30))
    d_end = _parse_date(end_date, date.today())
    client_id = _client_filter(user)

    stmt = (
        select(
            AdAccount.name.label("account_name"),
            AdAccount.platform,
            SpendingRecord.date,
            SpendingRecord.spend,
            SpendingRecord.impressions,
            SpendingRecord.clicks,
            SpendingRecord.conversions,
        )
        .join(AdAccount, SpendingRecord.account_id == AdAccount.id)
        .where(SpendingRecord.date.between(d_start, d_end))
        .order_by(SpendingRecord.date.desc())
    )
    if client_id:
        stmt = stmt.where(AdAccount.client_id == client_id)

    rows = (await db.execute(stmt)).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Account", "Platform", "Date", "Spend", "Impressions", "Clicks", "Conversions"])
    for r in rows:
        writer.writerow([r.account_name, r.platform, r.date, r.spend, r.impressions, r.clicks, r.conversions])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=analytics_{d_start}_{d_end}.csv"},
    )
