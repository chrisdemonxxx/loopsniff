"""
SMS-Man API Client — correct ``/control`` endpoint variant.
Reference: https://sms-man.com/api  |  GitHub: smsmancom/smsman
"""
import aiohttp
import asyncio
from typing import Optional, Dict, Any, List

from loguru import logger


class SMSManError(Exception):
    """Error from SMS-Man API."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(f"[{code}] {message}")


class SMSManClient:
    """Async client for SMS-Man ``/control`` API.

    Correct base URL:  ``https://api.sms-man.com/control``
    Auth parameter:    ``token`` (not ``key``).
    """

    BASE_URL = "https://api.sms-man.com/control"

    # Well-known IDs
    TELEGRAM_APP_ID = "3"

    def __init__(self, token: str):
        self.token = token
        self._session: Optional[aiohttp.ClientSession] = None

    # ── session management ───────────────────────────────────────────────

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
            )
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    # ── low-level request ────────────────────────────────────────────────

    async def _request(self, endpoint: str, extra_params: Optional[Dict] = None) -> Any:
        """Fire a GET to ``/control/{endpoint}`` and return parsed JSON.

        Raises :class:`SMSManError` on API-level errors.
        """
        session = await self._get_session()
        params = {"token": self.token}
        if extra_params:
            params.update(extra_params)

        url = f"{self.BASE_URL}/{endpoint}"
        async with session.get(url, params=params) as resp:
            text = await resp.text()
            if resp.status != 200:
                raise SMSManError("http_error", f"HTTP {resp.status}: {text[:200]}")
            try:
                data = await resp.json(content_type=None)
            except Exception:
                raise SMSManError("parse_error", f"Non-JSON response: {text[:200]}")

            # API-level error
            if isinstance(data, dict) and "error_code" in data and data["error_code"] != "wait_sms":
                raise SMSManError(data["error_code"], data.get("error_msg", ""))
            return data

    # ── public methods ───────────────────────────────────────────────────

    async def get_balance(self) -> float:
        """Return account balance (float)."""
        data = await self._request("get-balance")
        return float(data["balance"])

    async def get_countries(self) -> List[Dict]:
        """Return list of ``{id, title, code}`` dicts.

        The raw API returns a dict keyed by ID string; we normalise to a list.
        """
        data = await self._request("countries")
        if isinstance(data, dict):
            return list(data.values())
        return data

    async def get_applications(self) -> List[Dict]:
        """Return list of ``{id, name/title, code}`` dicts."""
        data = await self._request("applications")
        if isinstance(data, dict):
            return list(data.values())
        return data

    async def get_prices(self, country_id: str) -> Dict:
        """Return price map keyed by app ID."""
        return await self._request("get-prices", {"country_id": country_id})

    async def get_limits(self, country_id: str, application_id: str) -> List[Dict]:
        """Return available number counts."""
        return await self._request("limits", {
            "country_id": country_id,
            "application_id": application_id,
        })

    async def find_country_id(self, country_code: str) -> Optional[str]:
        """Look up the SMS-Man ``country_id`` for a 2-letter ISO code.

        Falls back to partial title matching (e.g. "us" → "USA").
        """
        mapping = {
            "us": ["usa", "united states"],
            "gb": ["united kingdom", "uk"],
            "uk": ["united kingdom", "uk"],
            "ca": ["canada"],
            "de": ["germany"],
            "fr": ["france"],
            "in": ["india"],
            "br": ["brazil"],
            "ru": ["russia"],
            "ua": ["ukraine"],
            "ph": ["philippines"],
            "id": ["indonesia"],
        }
        countries = await self.get_countries()
        needles = mapping.get(country_code.lower(), [country_code.lower()])

        for c in countries:
            title = (c.get("title") or "").lower()
            cid = str(c.get("id", ""))
            for needle in needles:
                if needle == title or needle in title:
                    return cid
        return None

    # ── number lifecycle ─────────────────────────────────────────────────

    async def get_number(
        self,
        country_id: str,
        application_id: str = TELEGRAM_APP_ID,
    ) -> Dict[str, Any]:
        """Request a virtual phone number.

        Returns::

            {"request_id": 123, "country_id": 1, "application_id": 3,
             "number": "79002415539"}
        """
        data = await self._request("get-number", {
            "country_id": country_id,
            "application_id": application_id,
        })
        logger.debug("get-number response: {}", data)
        return data

    async def get_sms(self, request_id) -> Dict[str, Any]:
        """Poll once for the SMS.

        Returns dict with ``sms_code`` on success, or raises
        ``SMSManError("wait_sms", ...)`` if still pending.
        """
        session = await self._get_session()
        params = {"token": self.token, "request_id": str(request_id)}
        url = f"{self.BASE_URL}/get-sms"

        async with session.get(url, params=params) as resp:
            data = await resp.json(content_type=None)

        if isinstance(data, dict) and "sms_code" in data and data["sms_code"]:
            return data
        if isinstance(data, dict) and data.get("error_code") == "wait_sms":
            raise SMSManError("wait_sms", data.get("error_msg", "waiting"))
        if isinstance(data, dict) and "error_code" in data:
            raise SMSManError(data["error_code"], data.get("error_msg", ""))
        raise SMSManError("unknown", f"Unexpected: {data}")

    async def set_status(self, request_id, status: str = "reject") -> bool:
        """Set activation status.  ``reject`` = cancel & refund."""
        data = await self._request("set-status", {
            "request_id": str(request_id),
            "status": status,
        })
        return data.get("success", False) if isinstance(data, dict) else False

    # ── convenience helpers ──────────────────────────────────────────────

    async def wait_for_code(
        self,
        request_id,
        timeout: int = 300,
        poll_interval: int = 5,
    ) -> str:
        """Poll ``get-sms`` until a code arrives or *timeout* seconds pass.

        Returns the verification code string.
        Raises ``TimeoutError`` after cancelling the number.
        """
        deadline = asyncio.get_event_loop().time() + timeout
        while True:
            try:
                result = await self.get_sms(request_id)
                return result["sms_code"]
            except SMSManError as e:
                if e.code != "wait_sms":
                    raise
            if asyncio.get_event_loop().time() > deadline:
                await self.set_status(request_id, "reject")
                raise TimeoutError(f"SMS not received within {timeout}s")
            await asyncio.sleep(poll_interval)

    async def get_telegram_number(self, country: str = "us") -> Dict[str, Any]:
        """High-level: resolve country → request Telegram number.

        Returns ``{"request_id": ..., "number": ..., "country_id": ...}``.
        """
        country_id = await self.find_country_id(country)
        if not country_id:
            raise SMSManError("country_not_found", f"Cannot map '{country}' to SMS-Man country_id")
        logger.info("Resolved country '{}' → country_id={}", country, country_id)
        return await self.get_number(country_id, self.TELEGRAM_APP_ID)

    async def get_verification_code(
        self,
        country: str = "us",
        timeout: int = 300,
    ) -> tuple:
        """End-to-end: get Telegram number + wait for code.

        Returns ``(phone_number, verification_code, request_id)``.
        """
        num = await self.get_telegram_number(country)
        request_id = num["request_id"]
        phone = num["number"]
        logger.info("Got number {} (request_id={}), waiting for code…", phone, request_id)

        try:
            code = await self.wait_for_code(request_id, timeout)
            logger.info("✓ Code received: {}", code)
            return phone, code, request_id
        except Exception:
            await self.set_status(request_id, "reject")
            raise
