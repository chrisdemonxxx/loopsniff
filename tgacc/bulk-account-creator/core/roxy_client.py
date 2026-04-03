"""
Roxy Browser Client
Real HTTP client for the Roxy Browser local API.

API docs: https://faq.roxybrowser.com/api-documentation/api-endpoint.html
Endpoints use ``/browser/*`` prefix.  Every mutating call requires
``workspaceId``.  Profiles are identified by ``dirId`` (a hex string).
"""
import asyncio
import random
import uuid
import aiohttp
from typing import Dict, Any, Optional, List
from loguru import logger


class RoxyBrowserClient:
    """Client for Roxy Browser local REST API (v3)."""

    def __init__(self, api_key: str, api_host: str = "http://127.0.0.1:50000"):
        self.api_key = api_key
        self.api_host = api_host.rstrip("/")
        self._session: Optional[aiohttp.ClientSession] = None
        self._workspace_id: Optional[int] = None

    # -- session management --------------------------------------------------

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                base_url=self.api_host,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                },
                timeout=aiohttp.ClientTimeout(total=30),
            )
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    # -- helpers --------------------------------------------------------------

    async def _request(
        self, method: str, path: str, json: Optional[dict] = None
    ) -> Dict[str, Any]:
        session = await self._get_session()
        async with session.request(method, path, json=json) as resp:
            body = await resp.json(content_type=None)
            if resp.status >= 400:
                raise RoxyAPIError(resp.status, body)
            code = body.get("code") if isinstance(body, dict) else None
            if code is not None and code != 0:
                raise RoxyAPIError(code, body.get("msg", body))
            return body

    async def _ensure_workspace(self) -> int:
        """Resolve and cache the first workspace ID."""
        if self._workspace_id is not None:
            return self._workspace_id
        data = await self._request("GET", "/browser/workspace")
        rows = data.get("data", {}).get("rows", [])
        if not rows:
            raise RoxyAPIError(0, "No workspaces found — open Roxy Browser first")
        self._workspace_id = rows[0]["id"]
        logger.debug("Using workspace {} ({})", self._workspace_id, rows[0].get("workspaceName"))
        return self._workspace_id

    # -- profile CRUD ---------------------------------------------------------

    async def create_profile(self, profile_config: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new browser profile.

        ``profile_config`` should contain at minimum ``windowName``.
        ``workspaceId`` is injected automatically.

        Returns dict with ``id`` (= dirId) and ``name``.
        """
        ws = await self._ensure_workspace()
        body = {**profile_config, "workspaceId": ws}
        data = await self._request("POST", "/browser/create", json=body)
        dir_id = data.get("data", {}).get("dirId", "")
        name = body.get("windowName", "")
        logger.info("Profile created: {} ({})", dir_id, name)
        return {"id": dir_id, "name": name, "raw": data}

    async def get_profile(self, profile_id: str) -> Dict[str, Any]:
        ws = await self._ensure_workspace()
        data = await self._request(
            "GET", f"/browser/detail?workspaceId={ws}&dirId={profile_id}"
        )
        return data.get("data", data)

    async def update_profile(
        self, profile_id: str, updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Modify profile fields (proxy, fingerprint, etc.)."""
        ws = await self._ensure_workspace()
        body = {**updates, "workspaceId": ws, "dirId": profile_id}
        return await self._request("POST", "/browser/modify", json=body)

    async def delete_profile(self, profile_id: str) -> None:
        ws = await self._ensure_workspace()
        await self._request(
            "POST", "/browser/delete", json={"workspaceId": ws, "dirIds": [profile_id]}
        )
        logger.info("Profile deleted: {}", profile_id)

    async def list_profiles(
        self, limit: int = 100, offset: int = 0
    ) -> List[Dict[str, Any]]:
        ws = await self._ensure_workspace()
        data = await self._request(
            "GET", f"/browser/list_v3?workspaceId={ws}&page_index=1&page_size={limit}"
        )
        rows = data.get("data", {}).get("rows", [])
        return rows

    # -- lifecycle ------------------------------------------------------------

    async def start_profile(self, profile_id: str) -> Dict[str, Any]:
        """Open a browser profile and return CDP connection info.

        Returns dict with ``ws_endpoint`` for Playwright connection.
        """
        ws = await self._ensure_workspace()
        data = await self._request(
            "POST", "/browser/open",
            json={"workspaceId": ws, "dirId": profile_id},
        )
        info = data.get("data", {})
        # Roxy returns debugPort or ws url
        debug_port = info.get("debugPort") or info.get("debug_port")
        ws_url = info.get("ws_endpoint") or info.get("wsEndpoint") or info.get("ws")
        if not ws_url and debug_port:
            ws_url = f"ws://127.0.0.1:{debug_port}"
        result = {"ws_endpoint": ws_url, "status": "running", **info}
        logger.info("Profile started: {} → {}", profile_id, ws_url)
        return result

    async def stop_profile(self, profile_id: str) -> None:
        ws = await self._ensure_workspace()
        await self._request(
            "POST", "/browser/close",
            json={"workspaceId": ws, "dirId": profile_id},
        )
        logger.info("Profile stopped: {}", profile_id)

    # -- CDP convenience ------------------------------------------------------

    @staticmethod
    def cdp_url(port: int) -> str:
        return f"ws://127.0.0.1:{port}"


class RoxyAPIError(Exception):
    def __init__(self, status: int, detail: Any):
        self.status = status
        self.detail = detail
        super().__init__(f"Roxy API {status}: {detail}")


# ---------------------------------------------------------------------------
# Profile generation helpers
# ---------------------------------------------------------------------------

COUNTRY_SETTINGS = {
    "us": {"locale": "en-US", "timezone": "GMT-05:00 America/New_York", "country": "US"},
    "uk": {"locale": "en-GB", "timezone": "GMT+00:00 Europe/London", "country": "GB"},
    "ca": {"locale": "en-CA", "timezone": "GMT-05:00 America/Toronto", "country": "CA"},
    "de": {"locale": "de-DE", "timezone": "GMT+01:00 Europe/Berlin", "country": "DE"},
    "au": {"locale": "en-AU", "timezone": "GMT+11:00 Australia/Sydney", "country": "AU"},
    "fr": {"locale": "fr-FR", "timezone": "GMT+01:00 Europe/Paris", "country": "FR"},
    "br": {"locale": "pt-BR", "timezone": "GMT-03:00 America/Sao_Paulo", "country": "BR"},
    "in": {"locale": "en-IN", "timezone": "GMT+05:30 Asia/Kolkata", "country": "IN"},
}


def generate_roxy_profile(
    account_type: str,
    country: str = "us",
    proxy_config: Optional[Dict] = None,
) -> Dict[str, Any]:
    """Build a profile config dict for ``POST /browser/create``.

    ``proxy_config`` should be a dict from ``parse_proxy_string()``
    containing ``host, port, username, password``.
    """
    cc = COUNTRY_SETTINGS.get(
        country, COUNTRY_SETTINGS["us"]
    )

    profile: Dict[str, Any] = {
        "windowName": f"{account_type}-{country}-{uuid.uuid4().hex[:8]}",
        "os": "Windows",
        "osVersion": "11",
        "fingerInfo": {
            "isLanguageBaseIp": False,
            "language": cc["locale"],
            "isDisplayLanguageBaseIp": False,
            "displayLanguage": cc["locale"],
            "isTimeZone": False,
            "timeZone": cc["timezone"],
            "isPositionBaseIp": True,
            "position": 1,
            "canvas": True,
            "webGL": True,
            "audioContext": True,
            "doNotTrack": True,
            "useGpu": True,
            "hardwareConcurrent": str(random.choice([4, 8, 12, 16])),
            "deviceMemory": str(random.choice([4, 8, 16])),
            "openWidth": "1280",
            "openHeight": "800",
        },
    }

    if proxy_config:
        profile["proxyInfo"] = {
            "proxyMethod": "custom",
            "proxyCategory": "HTTP",
            "ipType": "IPV4",
            "host": proxy_config.get("host", ""),
            "port": str(proxy_config.get("port", "")),
            "proxyUserName": proxy_config.get("username", ""),
            "proxyPassword": proxy_config.get("password", ""),
        }
    else:
        profile["proxyInfo"] = {
            "proxyMethod": "custom",
            "proxyCategory": "noproxy",
        }

    return profile


def parse_proxy_string(proxy_str: str) -> Dict[str, Any]:
    """Parse ``host:port:user:pass`` or ``host:port`` into a proxy config dict."""
    parts = proxy_str.strip().split(":")
    cfg: Dict[str, Any] = {"type": "http", "host": parts[0], "port": int(parts[1])}
    if len(parts) >= 4:
        cfg["username"] = parts[2]
        cfg["password"] = ":".join(parts[3:])
    return cfg
