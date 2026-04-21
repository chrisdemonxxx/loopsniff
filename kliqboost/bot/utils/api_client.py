import logging
from typing import Optional

import aiohttp

from config import API_BASE_URL, API_TOKEN

logger = logging.getLogger(__name__)

_REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=15)


class APIError(Exception):
    """Raised when the Kliqboost API returns a non-success response."""

    def __init__(self, status: int, detail: str = ""):
        self.status = status
        self.detail = detail
        super().__init__(f"API {status}: {detail}")


class KliqboostAPIClient:
    """Async HTTP client for the Kliqboost API."""

    def __init__(self, base_url: Optional[str] = None, token: Optional[str] = None):
        self.base_url = (base_url or API_BASE_URL).rstrip("/")
        self.token = token or API_TOKEN

    def _headers(self) -> dict:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: Optional[dict] = None,
        params: Optional[dict] = None,
    ) -> dict:
        url = f"{self.base_url}{path}"
        try:
            async with aiohttp.ClientSession(
                timeout=_REQUEST_TIMEOUT
            ) as session:
                async with session.request(
                    method, url, json=json, params=params, headers=self._headers()
                ) as resp:
                    body = await resp.json() if resp.content_type == "application/json" else {}
                    if resp.status >= 400:
                        detail = body.get("detail", "") if isinstance(body, dict) else str(body)
                        raise APIError(resp.status, detail)
                    return body
        except aiohttp.ClientError as exc:
            logger.error("API connection error (%s %s): %s", method, url, exc)
            raise
        except TimeoutError:
            logger.error("API request timed out: %s %s", method, url)
            raise

    # ── Clients ───────────────────────────────────────────────────────────

    async def get_client_by_telegram_id(self, telegram_id: int) -> Optional[dict]:
        """Look up a client by their Telegram user ID."""
        try:
            clients = await self._request(
                "GET", "/clients", params={"q": str(telegram_id), "limit": "1"}
            )
            if clients:
                for c in clients:
                    if c.get("tg_user_id") == telegram_id:
                        return c
            return None
        except (APIError, aiohttp.ClientError, TimeoutError):
            return None

    async def get_client(self, client_id: str) -> Optional[dict]:
        """Fetch a client by UUID."""
        try:
            return await self._request("GET", f"/clients/{client_id}")
        except APIError as exc:
            if exc.status == 404:
                return None
            raise

    async def create_client(self, data: dict) -> dict:
        """Register a new client in the API."""
        return await self._request("POST", "/clients", json=data)

    # ── Orders ────────────────────────────────────────────────────────────

    async def create_order(self, order_data: dict) -> dict:
        """Create a new order.

        order_data should match OrderCreate schema:
          client_id, order_type, amount, currency, details, notes
        """
        return await self._request("POST", "/orders", json=order_data)

    async def get_order(self, order_id: str) -> Optional[dict]:
        """Fetch an order by UUID."""
        try:
            return await self._request("GET", f"/orders/{order_id}")
        except APIError as exc:
            if exc.status == 404:
                return None
            raise

    async def list_orders(
        self, client_id: Optional[str] = None, status: Optional[str] = None
    ) -> list[dict]:
        """List orders, optionally filtered by client or status."""
        params: dict[str, str] = {}
        if client_id:
            params["client_id"] = client_id
        if status:
            params["status"] = status
        return await self._request("GET", "/orders", params=params)

    # ── Payments ──────────────────────────────────────────────────────────

    async def create_topup(
        self,
        client_id: str,
        account_id: str,
        ad_amount: float,
        pay_currency: str = "btc",
    ) -> dict:
        """Create a top-up payment transaction."""
        return await self._request(
            "POST",
            "/payments/topup",
            json={
                "client_id": client_id,
                "account_id": account_id,
                "ad_amount": ad_amount,
                "pay_currency": pay_currency,
            },
        )

    async def get_payment_status(self, payment_id: str) -> Optional[dict]:
        """Check the status of a payment."""
        try:
            return await self._request("GET", f"/payments/status/{payment_id}")
        except APIError as exc:
            if exc.status == 404:
                return None
            raise

    async def list_transactions(
        self, client_id: Optional[str] = None, status: Optional[str] = None
    ) -> list[dict]:
        """List payment transactions."""
        params: dict[str, str] = {}
        if client_id:
            params["client_id"] = client_id
        if status:
            params["status"] = status
        return await self._request("GET", "/payments/transactions", params=params)

    # ── Account Status ────────────────────────────────────────────────────

    async def get_account_status(self, client_id: str) -> Optional[dict]:
        """Get aggregated account status for a client (orders + transactions)."""
        try:
            orders = await self.list_orders(client_id=client_id)
            transactions = await self.list_transactions(client_id=client_id)
            return {
                "client_id": client_id,
                "total_orders": len(orders),
                "pending_orders": sum(1 for o in orders if o.get("status") == "pending"),
                "delivered_orders": sum(1 for o in orders if o.get("status") == "delivered"),
                "total_transactions": len(transactions),
                "confirmed_transactions": sum(
                    1 for t in transactions if t.get("status") == "confirmed"
                ),
            }
        except (APIError, aiohttp.ClientError, TimeoutError):
            return None


# Singleton for convenience
api_client = KliqboostAPIClient()
