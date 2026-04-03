import logging
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.meta.client import MetaAPIClient, MetaAPIError
from app.meta.schemas import (
    CampaignCreate,
    CampaignStatusUpdate,
    CampaignOut,
    AdSetCreate,
    AdSetOut,
    AdCreate,
    AdOut,
    InsightsOut,
    TargetingSearchOut,
    TargetingSearchResult,
    ImageUploadOut,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/meta", tags=["Meta"])
meta_client = MetaAPIClient()


def _handle_meta_error(exc: MetaAPIError):
    raise HTTPException(status_code=exc.status_code, detail=exc.message)


# ── Campaigns ──

@router.post("/campaigns", response_model=CampaignOut)
async def create_campaign(
    data: CampaignCreate,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a campaign via Meta Marketing API."""
    payload = {
        "name": data.name,
        "objective": data.objective,
        "status": data.status,
        "special_ad_categories": data.special_ad_categories,
        "buying_type": data.buying_type,
    }
    if data.daily_budget is not None:
        payload["daily_budget"] = data.daily_budget
    if data.lifetime_budget is not None:
        payload["lifetime_budget"] = data.lifetime_budget
    if data.bid_strategy:
        payload["bid_strategy"] = data.bid_strategy
    if data.start_time:
        payload["start_time"] = data.start_time
    if data.end_time:
        payload["end_time"] = data.end_time

    try:
        result = await meta_client.create_campaign(data.ad_account_id, data.access_token, payload)
    except MetaAPIError as exc:
        _handle_meta_error(exc)
    return CampaignOut(id=result.get("id", ""), name=data.name, objective=data.objective, status=data.status)


@router.put("/campaigns/{campaign_id}/status", response_model=CampaignOut)
async def update_campaign_status(
    campaign_id: str,
    data: CampaignStatusUpdate,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update campaign status (ACTIVE, PAUSED, DELETED, ARCHIVED)."""
    try:
        await meta_client.update_campaign_status(campaign_id, data.access_token, data.status)
    except MetaAPIError as exc:
        _handle_meta_error(exc)
    return CampaignOut(id=campaign_id, status=data.status, message="Status updated")


# ── Ad Sets ──

@router.post("/adsets", response_model=AdSetOut)
async def create_adset(
    data: AdSetCreate,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create an ad set via Meta Marketing API."""
    payload = {
        "campaign_id": data.campaign_id,
        "name": data.name,
        "status": data.status,
        "billing_event": data.billing_event,
        "targeting": data.targeting,
    }
    if data.daily_budget is not None:
        payload["daily_budget"] = data.daily_budget
    if data.lifetime_budget is not None:
        payload["lifetime_budget"] = data.lifetime_budget
    if data.bid_strategy:
        payload["bid_strategy"] = data.bid_strategy
    if data.bid_amount is not None:
        payload["bid_amount"] = data.bid_amount
    if data.optimization_goal:
        payload["optimization_goal"] = data.optimization_goal
    if data.start_time:
        payload["start_time"] = data.start_time
    if data.end_time:
        payload["end_time"] = data.end_time

    try:
        result = await meta_client.create_adset(data.ad_account_id, data.access_token, payload)
    except MetaAPIError as exc:
        _handle_meta_error(exc)
    return AdSetOut(id=result.get("id", ""), name=data.name, status=data.status)


# ── Ads ──

@router.post("/ads", response_model=AdOut)
async def create_ad(
    data: AdCreate,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create an ad via Meta Marketing API."""
    payload = {
        "adset_id": data.adset_id,
        "name": data.name,
        "status": data.status,
        "creative": data.creative,
    }
    if data.tracking_specs:
        payload["tracking_specs"] = data.tracking_specs

    try:
        result = await meta_client.create_ad(data.ad_account_id, data.access_token, payload)
    except MetaAPIError as exc:
        _handle_meta_error(exc)
    return AdOut(id=result.get("id", ""), name=data.name, status=data.status)


# ── Insights ──

@router.get("/insights/campaign/{campaign_id}", response_model=InsightsOut)
async def get_campaign_insights(
    campaign_id: str,
    access_token: str = Query(...),
    date_preset: str = Query("last_30d"),
    user: dict = Depends(get_current_user),
):
    """Get performance insights for a campaign."""
    try:
        data = await meta_client.get_campaign_insights(campaign_id, access_token, date_preset)
    except MetaAPIError as exc:
        _handle_meta_error(exc)
    return InsightsOut(data=data)


@router.get("/insights/adset/{adset_id}", response_model=InsightsOut)
async def get_adset_insights(
    adset_id: str,
    access_token: str = Query(...),
    date_preset: str = Query("last_30d"),
    user: dict = Depends(get_current_user),
):
    """Get performance insights for an ad set."""
    try:
        data = await meta_client.get_adset_insights(adset_id, access_token, date_preset)
    except MetaAPIError as exc:
        _handle_meta_error(exc)
    return InsightsOut(data=data)


@router.get("/insights/ad/{ad_id}", response_model=InsightsOut)
async def get_ad_insights(
    ad_id: str,
    access_token: str = Query(...),
    date_preset: str = Query("last_30d"),
    user: dict = Depends(get_current_user),
):
    """Get performance insights for an ad."""
    try:
        data = await meta_client.get_ad_insights(ad_id, access_token, date_preset)
    except MetaAPIError as exc:
        _handle_meta_error(exc)
    return InsightsOut(data=data)


# ── Targeting ──

@router.get("/targeting/search", response_model=TargetingSearchOut)
async def search_targeting(
    q: str = Query(..., min_length=1),
    access_token: str = Query(...),
    user: dict = Depends(get_current_user),
):
    """Search Meta targeting options (interests, behaviors)."""
    try:
        raw = await meta_client.get_targeting_options(access_token, q)
    except MetaAPIError as exc:
        _handle_meta_error(exc)
    results = [
        TargetingSearchResult(
            id=item.get("id", ""),
            name=item.get("name", ""),
            audience_size_lower_bound=item.get("audience_size_lower_bound"),
            audience_size_upper_bound=item.get("audience_size_upper_bound"),
            type=item.get("type"),
            path=item.get("path"),
        )
        for item in raw
    ]
    return TargetingSearchOut(results=results)


# ── Image Upload ──

@router.post("/images/upload", response_model=ImageUploadOut)
async def upload_image(
    ad_account_id: str = Query(...),
    access_token: str = Query(...),
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    """Upload an ad image to a Meta ad account."""
    image_bytes = await file.read()
    try:
        result = await meta_client.upload_image(ad_account_id, access_token, image_bytes)
    except MetaAPIError as exc:
        _handle_meta_error(exc)

    images = result.get("images", {})
    first = next(iter(images.values()), {}) if images else {}
    return ImageUploadOut(
        image_hash=first.get("hash"),
        image_url=first.get("url"),
        message="Image uploaded successfully",
    )
