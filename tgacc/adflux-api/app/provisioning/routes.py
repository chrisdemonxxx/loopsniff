import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, require_admin
from app.database import get_db
from app.models import AdAccount, MetaAdAccount, ProvisioningRequest
from app.meta.client import MetaAPIClient, MetaAPIError
from app.provisioning.schemas import (
    ProvisioningRequestCreate,
    ProvisioningRequestOut,
    ProvisioningApproval,
    ProvisioningRejection,
    ProvisioningExecuteRequest,
    ProvisioningExecuteOut,
    PlatformInfo,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/provisioning", tags=["Provisioning"])

PLATFORMS = [
    PlatformInfo(
        platform="meta",
        display_name="Meta (Facebook & Instagram)",
        requirements=["Business Manager ID", "Facebook Page", "Valid payment method"],
        supported_currencies=["USD", "EUR", "GBP", "CAD", "AUD"],
        min_spend=5,
    ),
    PlatformInfo(
        platform="google",
        display_name="Google Ads",
        requirements=["Google account", "Business website", "Valid payment method"],
        supported_currencies=["USD", "EUR", "GBP", "CAD", "AUD", "JPY"],
        min_spend=10,
    ),
    PlatformInfo(
        platform="tiktok",
        display_name="TikTok Ads",
        requirements=["TikTok Business Center", "Business verification"],
        supported_currencies=["USD", "EUR", "GBP"],
        min_spend=20,
    ),
    PlatformInfo(
        platform="snapchat",
        display_name="Snapchat Ads",
        requirements=["Snapchat Business account", "Valid payment method"],
        supported_currencies=["USD", "EUR", "GBP", "CAD", "AUD"],
        min_spend=5,
    ),
]


@router.post("/request", response_model=ProvisioningRequestOut, status_code=201)
async def create_provisioning_request(
    data: ProvisioningRequestCreate,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Client requests a new ad account on a specific platform."""
    client_id = user.get("client_id")
    if not client_id:
        raise HTTPException(status_code=400, detail="No client profile associated with this user")

    req = ProvisioningRequest(
        client_id=uuid.UUID(client_id),
        platform=data.platform,
        business_name=data.business_name,
        business_url=data.business_url,
        business_type=data.business_type,
        spend_limit=data.spend_limit,
        currency=data.currency,
        timezone=data.timezone,
        notes=data.notes,
        status="pending",
    )
    db.add(req)
    await db.flush()
    await db.commit()
    await db.refresh(req)
    return req


@router.get("/requests", response_model=list[ProvisioningRequestOut])
async def list_provisioning_requests(
    status: str | None = Query(None),
    skip: int = 0,
    limit: int = 50,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List provisioning requests. Clients see their own; admins see all."""
    stmt = select(ProvisioningRequest)
    if user.get("user_type") == "client":
        client_id = user.get("client_id")
        if not client_id:
            return []
        stmt = stmt.where(ProvisioningRequest.client_id == uuid.UUID(client_id))
    if status:
        stmt = stmt.where(ProvisioningRequest.status == status)
    stmt = stmt.order_by(ProvisioningRequest.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.put("/requests/{request_id}/approve", response_model=ProvisioningRequestOut)
async def approve_provisioning_request(
    request_id: uuid.UUID,
    data: ProvisioningApproval,
    user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Admin approves a provisioning request and creates the ad account in DB."""
    result = await db.execute(
        select(ProvisioningRequest).where(ProvisioningRequest.id == request_id)
    )
    req = result.scalar_one_or_none()
    if not req:
        raise HTTPException(status_code=404, detail="Provisioning request not found")
    if req.status != "pending":
        raise HTTPException(status_code=400, detail=f"Request already {req.status}")

    acct = AdAccount(
        client_id=req.client_id,
        platform=req.platform,
        account_id=data.account_id,
        name=data.account_name or f"{req.business_name} - {req.platform}",
        daily_limit=data.daily_limit,
        status="active",
    )
    db.add(acct)

    req.status = "approved"
    req.admin_notes = data.admin_notes
    req.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await db.commit()
    await db.refresh(req)
    return req


@router.put("/requests/{request_id}/reject", response_model=ProvisioningRequestOut)
async def reject_provisioning_request(
    request_id: uuid.UUID,
    data: ProvisioningRejection,
    user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Admin rejects a provisioning request with a reason."""
    result = await db.execute(
        select(ProvisioningRequest).where(ProvisioningRequest.id == request_id)
    )
    req = result.scalar_one_or_none()
    if not req:
        raise HTTPException(status_code=404, detail="Provisioning request not found")
    if req.status != "pending":
        raise HTTPException(status_code=400, detail=f"Request already {req.status}")

    req.status = "rejected"
    req.reject_reason = data.reason
    req.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await db.commit()
    await db.refresh(req)
    return req


@router.get("/platforms", response_model=list[PlatformInfo])
async def list_platforms(user: dict = Depends(get_current_user)):
    """List available advertising platforms and their requirements."""
    return PLATFORMS


META_TIMEZONE_MAP = {
    "UTC": 0, "US/Eastern": 1, "US/Central": 2, "US/Mountain": 3,
    "US/Pacific": 4, "Europe/London": 5, "Europe/Paris": 6,
    "Asia/Tokyo": 7, "Asia/Hong_Kong": 8, "Australia/Sydney": 9,
}

meta_client = MetaAPIClient()


@router.post("/requests/{request_id}/execute", response_model=ProvisioningExecuteOut)
async def execute_provisioning(
    request_id: uuid.UUID,
    data: ProvisioningExecuteRequest,
    user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Execute an approved provisioning request by calling the ad platform API.

    Currently supports Meta (Facebook/Instagram). On success the
    ProvisioningRequest is marked ``provisioned`` and the local AdAccount is
    updated with the real platform account id.  On failure the request moves
    to ``failed`` with error details.
    """
    result = await db.execute(
        select(ProvisioningRequest).where(ProvisioningRequest.id == request_id)
    )
    req = result.scalar_one_or_none()
    if not req:
        raise HTTPException(status_code=404, detail="Provisioning request not found")
    if req.status != "approved":
        raise HTTPException(
            status_code=400,
            detail=f"Only approved requests can be executed (current: {req.status})",
        )

    if req.platform != "meta":
        raise HTTPException(
            status_code=400,
            detail=f"Automated provisioning not yet supported for {req.platform}",
        )

    # Build Meta account creation payload
    tz_id = META_TIMEZONE_MAP.get(req.timezone, 0)
    account_data = {
        "name": req.business_name,
        "currency": req.currency or "USD",
        "timezone_id": str(tz_id),
        "end_advertiser": data.business_manager_id,
        "media_agency": "NONE",
        "partner": "NONE",
    }

    try:
        meta_result = await meta_client.create_ad_account(
            business_id=data.business_manager_id,
            access_token=data.access_token,
            account_data=account_data,
        )
    except MetaAPIError as exc:
        req.status = "failed"
        req.admin_notes = (req.admin_notes or "") + f"\nExecution failed: {exc.message}"
        req.updated_at = datetime.now(timezone.utc)
        await db.commit()
        log.error("Meta provisioning failed for %s: %s", request_id, exc.message)
        return ProvisioningExecuteOut(
            request_id=req.id,
            status="failed",
            error=exc.message,
        )

    platform_account_id = meta_result.get("id", "")
    # Meta returns ids like "act_123456789" — strip prefix for storage
    raw_id = platform_account_id.replace("act_", "")

    # Find the AdAccount created during approval and update it
    acct_stmt = select(AdAccount).where(
        AdAccount.client_id == req.client_id,
        AdAccount.platform == "meta",
    ).order_by(AdAccount.created_at.desc())
    acct_row = await db.execute(acct_stmt)
    ad_account = acct_row.scalar_one_or_none()

    if ad_account:
        ad_account.account_id = raw_id
        ad_account.name = ad_account.name or req.business_name

        # Create MetaAdAccount record linking to the real platform account
        meta_acct = MetaAdAccount(
            ad_account_id=ad_account.id,
            meta_account_id=platform_account_id,
            access_token=data.access_token,
            business_manager_id=data.business_manager_id,
            timezone=req.timezone or "UTC",
            currency=req.currency or "USD",
            status="active",
        )
        db.add(meta_acct)

    req.status = "provisioned"
    req.admin_notes = (req.admin_notes or "") + f"\nProvisioned: {platform_account_id}"
    req.updated_at = datetime.now(timezone.utc)
    await db.commit()

    log.info("Provisioned Meta account %s for request %s", platform_account_id, request_id)
    return ProvisioningExecuteOut(
        request_id=req.id,
        status="provisioned",
        platform_account_id=platform_account_id,
        ad_account_id=ad_account.id if ad_account else None,
    )
