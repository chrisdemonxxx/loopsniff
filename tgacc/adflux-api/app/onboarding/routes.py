import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from passlib.hash import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.jwt import create_access_token, create_refresh_token, create_verification_token
from app.auth.schemas import TokenResponse
from app.database import get_db
from app.email.service import send_verification_email
from app.models import Client, ClientUser, Subscription, SubscriptionPlan, Wallet
from app.onboarding.schemas import (
    OnboardingCompleteRequest,
    OnboardingRegister,
    OnboardingStatusOut,
    PlanSelectRequest,
    PlatformSelectRequest,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.post("/register", response_model=TokenResponse)
async def onboarding_register(
    data: OnboardingRegister,
    db: AsyncSession = Depends(get_db),
):
    """Create a new client account during onboarding. No auth required."""
    result = await db.execute(select(ClientUser).where(ClientUser.email == data.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    client = Client(
        name=data.name,
        company=data.company_name,
        email=data.email,
        status="onboarding",
    )
    db.add(client)
    await db.flush()
    await db.commit()

    hashed = bcrypt.hash(data.password)
    user = ClientUser(
        client_id=client.id,
        email=data.email,
        name=data.name,
        password_hash=hashed,
        role="owner",
    )
    db.add(user)
    await db.flush()
    await db.commit()

    if data.phone:
        client.notes = f"Phone: {data.phone}"
        await db.flush()
        await db.commit()

    wallet = Wallet(client_id=client.id, currency="USD", balance=0, frozen_balance=0)
    db.add(wallet)

    subscription = Subscription(
        client_id=client.id,
        plan="starter",
        price=0,
        interval_type="monthly",
        status="active",
    )
    db.add(subscription)
    await db.flush()
    await db.commit()

    verification_token = create_verification_token(data.email)
    await send_verification_email(data.email, verification_token, data.name)

    token_data = {
        "sub": str(user.id),
        "user_type": "client",
        "role": "owner",
        "client_id": str(client.id),
    }
    access = create_access_token(token_data)
    refresh = create_refresh_token(token_data)

    log.info("Onboarding: registered client %s (%s)", client.id, data.email)
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        user_type="client",
        user_id=str(user.id),
        name=user.name or user.email,
        client_id=str(client.id),
    )


@router.post("/select-platforms")
async def select_platforms(
    data: PlatformSelectRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Store selected ad platforms for the onboarding client."""
    client_id = user.get("client_id")
    if not client_id:
        raise HTTPException(status_code=400, detail="No client linked to this user")

    result = await db.execute(select(Client).where(Client.id == UUID(client_id)))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    client.niche = ",".join(data.platforms)
    await db.flush()
    await db.commit()

    log.info("Onboarding: client %s selected platforms: %s", client_id, data.platforms)
    return {"detail": "Platforms saved", "platforms": data.platforms}


@router.post("/select-plan")
async def select_plan(
    data: PlanSelectRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Store the selected subscription plan for the onboarding client."""
    client_id = user.get("client_id")
    if not client_id:
        raise HTTPException(status_code=400, detail="No client linked to this user")

    result = await db.execute(
        select(SubscriptionPlan).where(
            SubscriptionPlan.slug == data.plan_slug,
            SubscriptionPlan.is_active == True,
        )
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    valid_intervals = ("monthly", "semiannual", "annual")
    if data.interval not in valid_intervals:
        raise HTTPException(status_code=400, detail="Invalid interval")

    client_result = await db.execute(select(Client).where(Client.id == UUID(client_id)))
    client = client_result.scalar_one_or_none()
    if client:
        client.plan = plan.slug
    await db.flush()
    await db.commit()

    log.info("Onboarding: client %s selected plan %s (%s)", client_id, plan.slug, data.interval)
    return {"detail": "Plan saved", "plan": plan.slug, "interval": data.interval}


@router.post("/complete")
async def complete_onboarding(
    data: OnboardingCompleteRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Finalize onboarding and activate the client account."""
    client_id = user.get("client_id")
    if not client_id:
        raise HTTPException(status_code=400, detail="No client linked to this user")

    result = await db.execute(select(Client).where(Client.id == UUID(client_id)))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    client.status = "active"
    client.onboarded_at = datetime.now(timezone.utc)
    await db.flush()
    await db.commit()

    log.info("Onboarding: client %s completed (payment: %s)", client_id, data.payment_method or "pay_later")
    return {"detail": "Onboarding complete", "status": "active"}


@router.get("/status", response_model=OnboardingStatusOut)
async def onboarding_status(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Check the current onboarding progress for the authenticated client."""
    client_id = user.get("client_id")

    status = OnboardingStatusOut(
        user_id=user["id"],
        client_id=client_id,
        account_created=True,
    )

    if not client_id:
        return status

    result = await db.execute(select(Client).where(Client.id == UUID(client_id)))
    client = result.scalar_one_or_none()
    if not client:
        return status

    if client.niche:
        status.platforms_selected = True
        status.selected_platforms = [p.strip() for p in client.niche.split(",") if p.strip()]

    if client.plan and client.plan != "starter":
        status.plan_selected = True
        status.selected_plan = client.plan

    if client.status == "active" and client.onboarded_at:
        status.onboarding_completed = True

    return status
