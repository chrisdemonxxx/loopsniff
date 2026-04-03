"""NOWPayments crypto payment engine for the outreach bot."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import uuid
from typing import Optional

import aiohttp

log = logging.getLogger(__name__)


class NOWPaymentsClient:
    """Async wrapper for the NOWPayments v1 API."""

    BASE_URL = "https://api.nowpayments.io/v1"

    def __init__(
        self,
        api_key: str | None = None,
        ipn_secret: str | None = None,
    ):
        self.api_key = api_key or os.getenv("NOWPAYMENTS_API_KEY", "")
        self.ipn_secret = ipn_secret or os.getenv("NOWPAYMENTS_IPN_SECRET", "")

    # -- helpers --

    def _headers(self) -> dict:
        return {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
        }

    async def _get(self, path: str, params: dict | None = None) -> dict:
        url = f"{self.BASE_URL}{path}"
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, headers=self._headers(), params=params,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                data = await resp.json()
                if resp.status != 200:
                    log.error("NOWPayments GET %s → %d: %s", path, resp.status, data)
                return data

    async def _post(self, path: str, payload: dict) -> dict:
        url = f"{self.BASE_URL}{path}"
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, headers=self._headers(), json=payload,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                data = await resp.json()
                if resp.status not in (200, 201):
                    log.error("NOWPayments POST %s → %d: %s", path, resp.status, data)
                return data

    # -- public API --

    async def get_available_currencies(self) -> list[str]:
        """GET /currencies — list of supported crypto tickers."""
        data = await self._get("/currencies")
        return data.get("currencies", [])

    async def get_min_amount(self, currency_from: str, currency_to: str) -> float:
        """GET /min-amount — minimum payment amount for a pair."""
        data = await self._get("/min-amount", {
            "currency_from": currency_from,
            "currency_to": currency_to,
        })
        return float(data.get("min_amount", 0))

    async def create_invoice(
        self,
        price_amount: float,
        price_currency: str = "usd",
        pay_currency: str = "btc",
        order_id: str | None = None,
        order_description: str | None = None,
        ipn_callback_url: str | None = None,
    ) -> dict:
        """POST /invoice — create a payment invoice.

        Returns dict with keys: id, invoice_url, order_id, etc.
        """
        payload: dict = {
            "price_amount": price_amount,
            "price_currency": price_currency,
            "pay_currency": pay_currency,
            "order_id": order_id or str(uuid.uuid4()),
            "order_description": order_description or "AdFlux Media — Ad Account Top-Up",
            "is_fixed_rate": True,
            "is_fee_paid_by_user": False,
        }
        if ipn_callback_url:
            payload["ipn_callback_url"] = ipn_callback_url

        data = await self._post("/invoice", payload)
        log.info("Invoice created: id=%s url=%s", data.get("id"), data.get("invoice_url"))
        return data

    async def get_payment_status(self, payment_id: str) -> dict:
        """GET /payment/{payment_id} — check payment status."""
        return await self._get(f"/payment/{payment_id}")

    async def verify_ipn(self, payload: dict, signature: str) -> bool:
        """Verify IPN webhook signature using HMAC-SHA512.

        NOWPayments signs the sorted JSON body with the IPN secret.
        """
        if not self.ipn_secret:
            log.warning("IPN secret not configured — skipping verification")
            return False

        sorted_payload = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        expected = hmac.new(
            self.ipn_secret.encode(),
            sorted_payload.encode(),
            hashlib.sha512,
        ).hexdigest()

        valid = hmac.compare_digest(expected, signature)
        if not valid:
            log.warning("IPN signature mismatch")
        return valid

    async def get_estimate(
        self, amount: float, currency_from: str, currency_to: str
    ) -> dict:
        """GET /estimate — estimated crypto amount for a fiat value."""
        return await self._get("/estimate", {
            "amount": amount,
            "currency_from": currency_from,
            "currency_to": currency_to,
        })
