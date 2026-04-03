import logging
from typing import Any

import httpx

log = logging.getLogger(__name__)

GRAPH_API_BASE = "https://graph.facebook.com/v21.0"


class MetaAPIError(Exception):
    """Raised when the Meta Marketing API returns an error."""

    def __init__(self, message: str, status_code: int = 400, error_data: dict | None = None):
        self.message = message
        self.status_code = status_code
        self.error_data = error_data or {}
        super().__init__(self.message)


class MetaAPIClient:
    """Async wrapper around the Meta Marketing API (Graph API v21.0)."""

    def __init__(self, timeout: float = 30.0):
        self._timeout = timeout

    def _headers(self, access_token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {access_token}"}

    async def _request(
        self,
        method: str,
        url: str,
        access_token: str,
        *,
        params: dict | None = None,
        json_body: dict | None = None,
        data: dict | None = None,
        files: dict | None = None,
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.request(
                method,
                url,
                headers=self._headers(access_token),
                params=params,
                json=json_body if not data and not files else None,
                data=data,
                files=files,
            )

        body = resp.json() if resp.text else {}
        if resp.status_code >= 400 or "error" in body:
            err = body.get("error", {})
            msg = err.get("message", body.get("message", resp.text))
            log.error("Meta API error %s %s: %s", method, url, msg)
            raise MetaAPIError(message=str(msg), status_code=resp.status_code, error_data=err)
        return body

    # ── Ad Accounts ──

    async def get_ad_accounts(self, access_token: str) -> list[dict]:
        """List ad accounts accessible via Business Manager."""
        url = f"{GRAPH_API_BASE}/me/adaccounts"
        params = {"fields": "id,account_id,name,currency,timezone_name,business_name,account_status"}
        result = await self._request("GET", url, access_token, params=params)
        return result.get("data", [])

    # ── Campaigns ──

    async def create_campaign(
        self, ad_account_id: str, access_token: str, campaign_data: dict
    ) -> dict:
        url = f"{GRAPH_API_BASE}/act_{ad_account_id}/campaigns"
        return await self._request("POST", url, access_token, json_body=campaign_data)

    async def update_campaign_status(
        self, campaign_id: str, access_token: str, status: str
    ) -> dict:
        url = f"{GRAPH_API_BASE}/{campaign_id}"
        return await self._request("POST", url, access_token, json_body={"status": status})

    # ── Ad Sets ──

    async def create_adset(
        self, ad_account_id: str, access_token: str, adset_data: dict
    ) -> dict:
        url = f"{GRAPH_API_BASE}/act_{ad_account_id}/adsets"
        return await self._request("POST", url, access_token, json_body=adset_data)

    # ── Ads ──

    async def create_ad(
        self, ad_account_id: str, access_token: str, ad_data: dict
    ) -> dict:
        url = f"{GRAPH_API_BASE}/act_{ad_account_id}/ads"
        return await self._request("POST", url, access_token, json_body=ad_data)

    # ── Business Manager ──

    async def create_ad_account(
        self,
        business_id: str,
        access_token: str,
        account_data: dict,
    ) -> dict:
        """Create a new ad account under a Business Manager.

        ``account_data`` should include at least ``name``, ``currency``,
        ``timezone_id`` and ``end_advertiser``.
        """
        url = f"{GRAPH_API_BASE}/{business_id}/adaccount"
        return await self._request("POST", url, access_token, data=account_data)

    # ── Insights ──

    async def get_campaign_insights(
        self, campaign_id: str, access_token: str, date_preset: str = "last_30d"
    ) -> list[dict]:
        url = f"{GRAPH_API_BASE}/{campaign_id}/insights"
        params = {
            "fields": "campaign_name,spend,impressions,clicks,ctr,cpc,cpm,conversions,cost_per_action_type,actions",
            "date_preset": date_preset,
        }
        result = await self._request("GET", url, access_token, params=params)
        return result.get("data", [])

    async def get_adset_insights(
        self, adset_id: str, access_token: str, date_preset: str = "last_30d"
    ) -> list[dict]:
        url = f"{GRAPH_API_BASE}/{adset_id}/insights"
        params = {
            "fields": "adset_name,spend,impressions,clicks,ctr,cpc,cpm,conversions,cost_per_action_type,actions",
            "date_preset": date_preset,
        }
        result = await self._request("GET", url, access_token, params=params)
        return result.get("data", [])

    async def get_ad_insights(
        self, ad_id: str, access_token: str, date_preset: str = "last_30d"
    ) -> list[dict]:
        url = f"{GRAPH_API_BASE}/{ad_id}/insights"
        params = {
            "fields": "ad_name,spend,impressions,clicks,ctr,cpc,cpm,conversions,cost_per_action_type,actions",
            "date_preset": date_preset,
        }
        result = await self._request("GET", url, access_token, params=params)
        return result.get("data", [])

    async def get_account_insights(
        self,
        ad_account_id: str,
        access_token: str,
        *,
        date_preset: str | None = None,
        time_range: dict | None = None,
        level: str = "account",
        time_increment: str = "1",
    ) -> list[dict]:
        """Fetch spend / impression / click data for an ad account.

        Use *either* ``date_preset`` (e.g. ``"last_7d"``) *or*
        ``time_range`` (``{"since": "2024-01-01", "until": "2024-01-07"}``).
        ``time_increment="1"`` returns daily rows.
        """
        url = f"{GRAPH_API_BASE}/act_{ad_account_id}/insights"
        params: dict[str, str] = {
            "fields": "spend,impressions,clicks,conversions,date_start,date_stop",
            "level": level,
            "time_increment": time_increment,
        }
        if time_range:
            import json as _json
            params["time_range"] = _json.dumps(time_range)
        else:
            params["date_preset"] = date_preset or "last_7d"
        result = await self._request("GET", url, access_token, params=params)
        return result.get("data", [])

    # ── Targeting ──

    async def get_targeting_options(
        self, access_token: str, query: str
    ) -> list[dict]:
        url = f"{GRAPH_API_BASE}/search"
        params = {"type": "adinterest", "q": query}
        result = await self._request("GET", url, access_token, params=params)
        return result.get("data", [])

    # ── Image Upload ──

    async def upload_image(
        self, ad_account_id: str, access_token: str, image_data: bytes
    ) -> dict:
        url = f"{GRAPH_API_BASE}/act_{ad_account_id}/adimages"
        files = {"filename": ("ad_image.jpg", image_data, "image/jpeg")}
        return await self._request("POST", url, access_token, files=files)
