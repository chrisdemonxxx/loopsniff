import logging
from urllib.parse import urlencode
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.config import get_settings
from app.database import get_db
from app.models import FacebookIntegration
from app.facebook.schemas import (
    FacebookAuthURL,
    FacebookCallbackRequest,
    FacebookTokenResponse,
    FacebookPage,
    FacebookPageList,
    InstagramAccount,
    InstagramAccountList,
    MetaAdAccountInfo,
    MetaAdAccountList,
    FacebookConnectionStatus,
    DisconnectResponse,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/facebook", tags=["Facebook"])

GRAPH_API = "https://graph.facebook.com/v21.0"
OAUTH_SCOPES = [
    "ads_management",
    "ads_read",
    "pages_show_list",
    "pages_read_engagement",
    "instagram_basic",
    "instagram_manage_insights",
    "business_management",
    "read_insights",
]


def _settings():
    return get_settings()


async def _get_integration(client_id: str, db: AsyncSession) -> FacebookIntegration | None:
    result = await db.execute(
        select(FacebookIntegration).where(
            FacebookIntegration.client_id == UUID(client_id),
            FacebookIntegration.status == "active",
        )
    )
    return result.scalar_one_or_none()


# ── Auth URL ──

@router.get("/auth-url", response_model=FacebookAuthURL)
async def get_auth_url(user: dict = Depends(get_current_user)):
    """Generate Facebook OAuth URL with required permissions."""
    settings = _settings()
    if not settings.FACEBOOK_APP_ID:
        raise HTTPException(status_code=500, detail="Facebook App ID not configured")

    params = {
        "client_id": settings.FACEBOOK_APP_ID,
        "redirect_uri": settings.FACEBOOK_REDIRECT_URI,
        "scope": ",".join(OAUTH_SCOPES),
        "response_type": "code",
        "state": user["client_id"] or user["id"],
    }
    auth_url = f"https://www.facebook.com/v21.0/dialog/oauth?{urlencode(params)}"
    return FacebookAuthURL(auth_url=auth_url)


# ── OAuth Callback ──

@router.post("/callback", response_model=FacebookTokenResponse)
async def handle_callback(
    req: FacebookCallbackRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Exchange OAuth code for access token and store integration."""
    settings = _settings()
    redirect_uri = req.redirect_uri or settings.FACEBOOK_REDIRECT_URI

    # Exchange code for short-lived token
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GRAPH_API}/oauth/access_token",
            params={
                "client_id": settings.FACEBOOK_APP_ID,
                "client_secret": settings.FACEBOOK_APP_SECRET,
                "redirect_uri": redirect_uri,
                "code": req.code,
            },
        )
        if resp.status_code != 200:
            log.error(f"Facebook token exchange failed: {resp.text}")
            raise HTTPException(status_code=400, detail="Failed to exchange code for access token")
        token_data = resp.json()

    short_token = token_data.get("access_token")
    if not short_token:
        raise HTTPException(status_code=400, detail="No access token returned from Facebook")

    # Exchange for long-lived token
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GRAPH_API}/oauth/access_token",
            params={
                "grant_type": "fb_exchange_token",
                "client_id": settings.FACEBOOK_APP_ID,
                "client_secret": settings.FACEBOOK_APP_SECRET,
                "fb_exchange_token": short_token,
            },
        )
        if resp.status_code == 200:
            long_data = resp.json()
            access_token = long_data.get("access_token", short_token)
        else:
            access_token = short_token

    # Get user info
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GRAPH_API}/me",
            params={"access_token": access_token, "fields": "id,name"},
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to fetch Facebook user info")
        fb_user = resp.json()

    client_id = user["client_id"] or user["id"]

    # Upsert integration
    existing = await _get_integration(client_id, db)
    if existing:
        existing.facebook_user_id = fb_user["id"]
        existing.facebook_user_name = fb_user.get("name")
        existing.access_token = access_token
        existing.status = "active"
        existing.scopes = OAUTH_SCOPES
    else:
        integration = FacebookIntegration(
            client_id=UUID(client_id),
            facebook_user_id=fb_user["id"],
            facebook_user_name=fb_user.get("name"),
            access_token=access_token,
            scopes=OAUTH_SCOPES,
        )
        db.add(integration)

    return FacebookTokenResponse(
        connected=True,
        facebook_user_id=fb_user["id"],
        name=fb_user.get("name", ""),
        message="Facebook account connected successfully",
    )


# ── Pages ──

@router.get("/pages", response_model=FacebookPageList)
async def list_pages(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List Facebook pages available to the connected account."""
    client_id = user["client_id"] or user["id"]
    integration = await _get_integration(client_id, db)
    if not integration:
        raise HTTPException(status_code=404, detail="Facebook not connected")

    connected_ids = {p["id"] for p in (integration.connected_pages or [])}

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GRAPH_API}/me/accounts",
            params={
                "access_token": integration.access_token,
                "fields": "id,name,category,access_token",
            },
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to fetch pages from Facebook")
        data = resp.json()

    pages = [
        FacebookPage(
            id=p["id"],
            name=p["name"],
            category=p.get("category"),
            connected=p["id"] in connected_ids,
        )
        for p in data.get("data", [])
    ]
    return FacebookPageList(pages=pages)


@router.post("/pages/{page_id}/connect")
async def connect_page(
    page_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Connect a Facebook page to the client's account."""
    client_id = user["client_id"] or user["id"]
    integration = await _get_integration(client_id, db)
    if not integration:
        raise HTTPException(status_code=404, detail="Facebook not connected")

    # Fetch page details and page-scoped token
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GRAPH_API}/{page_id}",
            params={
                "access_token": integration.access_token,
                "fields": "id,name,category,access_token",
            },
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=404, detail="Page not found or not accessible")
        page_data = resp.json()

    pages = list(integration.connected_pages or [])
    if not any(p["id"] == page_id for p in pages):
        pages.append({
            "id": page_data["id"],
            "name": page_data["name"],
            "access_token": page_data.get("access_token", ""),
        })
        integration.connected_pages = pages

    return {"connected": True, "page_id": page_id, "name": page_data["name"]}


# ── Instagram Accounts ──

@router.get("/instagram-accounts", response_model=InstagramAccountList)
async def list_instagram_accounts(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List Instagram business accounts linked to connected pages."""
    client_id = user["client_id"] or user["id"]
    integration = await _get_integration(client_id, db)
    if not integration:
        raise HTTPException(status_code=404, detail="Facebook not connected")

    connected_ids = {a["id"] for a in (integration.connected_ig_accounts or [])}
    accounts: list[InstagramAccount] = []

    # Get IG accounts from each connected page
    pages = integration.connected_pages or []
    if not pages:
        # Fetch pages to discover IG accounts
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{GRAPH_API}/me/accounts",
                params={
                    "access_token": integration.access_token,
                    "fields": "id,name,access_token",
                },
            )
            if resp.status_code == 200:
                pages = resp.json().get("data", [])

    for page in pages:
        page_token = page.get("access_token", integration.access_token)
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{GRAPH_API}/{page['id']}",
                params={
                    "access_token": page_token,
                    "fields": "instagram_business_account{id,username,name,profile_picture_url,followers_count}",
                },
            )
            if resp.status_code != 200:
                continue
            data = resp.json()

        ig = data.get("instagram_business_account")
        if ig and not any(a.id == ig["id"] for a in accounts):
            accounts.append(InstagramAccount(
                id=ig["id"],
                username=ig.get("username"),
                name=ig.get("name"),
                profile_picture_url=ig.get("profile_picture_url"),
                followers_count=ig.get("followers_count"),
                connected=ig["id"] in connected_ids,
            ))

    return InstagramAccountList(accounts=accounts)


@router.post("/instagram-accounts/{ig_id}/connect")
async def connect_instagram_account(
    ig_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Connect an Instagram business account."""
    client_id = user["client_id"] or user["id"]
    integration = await _get_integration(client_id, db)
    if not integration:
        raise HTTPException(status_code=404, detail="Facebook not connected")

    # Fetch IG account info
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GRAPH_API}/{ig_id}",
            params={
                "access_token": integration.access_token,
                "fields": "id,username,name",
            },
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=404, detail="Instagram account not found")
        ig_data = resp.json()

    ig_accounts = list(integration.connected_ig_accounts or [])
    if not any(a["id"] == ig_id for a in ig_accounts):
        ig_accounts.append({
            "id": ig_data["id"],
            "username": ig_data.get("username", ""),
            "name": ig_data.get("name", ""),
        })
        integration.connected_ig_accounts = ig_accounts

    return {"connected": True, "ig_id": ig_id, "username": ig_data.get("username", "")}


# ── Ad Accounts ──

@router.get("/ad-accounts", response_model=MetaAdAccountList)
async def list_ad_accounts(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List Meta ad accounts from Business Manager."""
    client_id = user["client_id"] or user["id"]
    integration = await _get_integration(client_id, db)
    if not integration:
        raise HTTPException(status_code=404, detail="Facebook not connected")

    connected_ids = {a["id"] for a in (integration.connected_ad_accounts or [])}

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GRAPH_API}/me/adaccounts",
            params={
                "access_token": integration.access_token,
                "fields": "id,account_id,name,currency,timezone_name,business_name",
            },
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to fetch ad accounts from Meta")
        data = resp.json()

    ad_accounts = [
        MetaAdAccountInfo(
            id=a["id"],
            account_id=a.get("account_id", a["id"]),
            name=a.get("name", "Unnamed"),
            currency=a.get("currency"),
            timezone=a.get("timezone_name"),
            business_name=a.get("business_name"),
            connected=a["id"] in connected_ids,
        )
        for a in data.get("data", [])
    ]
    return MetaAdAccountList(ad_accounts=ad_accounts)


@router.post("/ad-accounts/{ad_account_id}/connect")
async def connect_ad_account(
    ad_account_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Connect a Meta ad account to the platform."""
    client_id = user["client_id"] or user["id"]
    integration = await _get_integration(client_id, db)
    if not integration:
        raise HTTPException(status_code=404, detail="Facebook not connected")

    # Fetch ad account info
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GRAPH_API}/{ad_account_id}",
            params={
                "access_token": integration.access_token,
                "fields": "id,account_id,name,currency,timezone_name",
            },
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=404, detail="Ad account not found")
        acct_data = resp.json()

    ad_accounts = list(integration.connected_ad_accounts or [])
    if not any(a["id"] == ad_account_id for a in ad_accounts):
        ad_accounts.append({
            "id": acct_data["id"],
            "account_id": acct_data.get("account_id", ad_account_id),
            "name": acct_data.get("name", ""),
            "currency": acct_data.get("currency", "USD"),
            "timezone": acct_data.get("timezone_name", "UTC"),
        })
        integration.connected_ad_accounts = ad_accounts

    return {
        "connected": True,
        "ad_account_id": ad_account_id,
        "name": acct_data.get("name", ""),
    }


# ── Disconnect ──

@router.delete("/disconnect", response_model=DisconnectResponse)
async def disconnect_facebook(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Disconnect the Facebook integration."""
    client_id = user["client_id"] or user["id"]
    integration = await _get_integration(client_id, db)
    if not integration:
        raise HTTPException(status_code=404, detail="Facebook not connected")

    integration.status = "disconnected"
    integration.connected_pages = []
    integration.connected_ig_accounts = []
    integration.connected_ad_accounts = []

    return DisconnectResponse(
        disconnected=True,
        message="Facebook integration disconnected successfully",
    )


# ── Status ──

@router.get("/status", response_model=FacebookConnectionStatus)
async def get_status(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Check current Facebook connection status."""
    client_id = user["client_id"] or user["id"]
    integration = await _get_integration(client_id, db)

    if not integration:
        return FacebookConnectionStatus(connected=False)

    pages = [
        FacebookPage(id=p["id"], name=p["name"], connected=True)
        for p in (integration.connected_pages or [])
    ]
    ig_accounts = [
        InstagramAccount(
            id=a["id"],
            username=a.get("username"),
            name=a.get("name"),
            connected=True,
        )
        for a in (integration.connected_ig_accounts or [])
    ]
    ad_accounts = [
        MetaAdAccountInfo(
            id=a["id"],
            account_id=a.get("account_id", a["id"]),
            name=a.get("name", ""),
            currency=a.get("currency"),
            timezone=a.get("timezone"),
            connected=True,
        )
        for a in (integration.connected_ad_accounts or [])
    ]

    return FacebookConnectionStatus(
        connected=True,
        facebook_user_id=integration.facebook_user_id,
        facebook_user_name=integration.facebook_user_name,
        connected_at=integration.created_at,
        pages=pages,
        instagram_accounts=ig_accounts,
        ad_accounts=ad_accounts,
    )
