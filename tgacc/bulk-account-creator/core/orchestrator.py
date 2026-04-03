"""
Account Creation Orchestrator
Coordinates Roxy Browser, proxy, SMS, and Telegram signup.
Supports fully-automated and semi-automated (interactive) modes.
"""
import asyncio
import json
import os
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from loguru import logger

from core.roxy_client import (
    RoxyBrowserClient,
    generate_roxy_profile,
    parse_proxy_string,
)
from core.telegram_signup import TelegramSignup
from core.proxy_client import ProxySellerClient
from core.sms_client import SMSManClient


class AccountCreator:
    """Main orchestrator for automated Telegram account creation."""

    def __init__(
        self,
        roxy_api_key: str,
        roxy_api_host: str = "http://127.0.0.1:50000",
        proxy_api_key: str = "",
        sms_api_key: str = "",
    ):
        self.roxy = RoxyBrowserClient(roxy_api_key, roxy_api_host)
        self.proxy_client = ProxySellerClient(proxy_api_key) if proxy_api_key else None
        self.sms_client = SMSManClient(sms_api_key) if sms_api_key else None

    async def close(self):
        await self.roxy.close()
        if self.sms_client:
            await self.sms_client.close()
        if self.proxy_client:
            await self.proxy_client.close()

    # ── Semi-automated flow (interactive prompts) ────────────────────────────

    async def create_account_interactive(
        self,
        country: str = "us",
        proxy_str: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create one Telegram account with interactive prompts for
        proxy credentials and SMS code.

        Args:
            country: 2-letter country code.
            proxy_str: ``host:port:user:pass`` or None to prompt.

        Returns:
            Result dict with status, profile_id, phone, etc.
        """
        profile_id = None
        result: Dict[str, Any] = {"status": "failed", "country": country}

        try:
            # ── Step 1: Proxy ────────────────────────────────────────────
            logger.info("[1/6] Proxy configuration")
            if proxy_str:
                proxy_cfg = parse_proxy_string(proxy_str)
            elif self.proxy_client:
                proxy = await self.proxy_client.get_residential_proxy(country)
                proxy_str = ProxySellerClient.format_proxy_string(proxy)
                proxy_cfg = parse_proxy_string(proxy_str)
                logger.info("  Using residential proxy: {}:{}", proxy["host"], proxy["port"])
            else:
                proxy_str = input("  Enter proxy (host:port:user:pass) or press Enter to skip: ").strip()
                proxy_cfg = parse_proxy_string(proxy_str) if proxy_str else None

            # ── Step 2: Create Roxy profile ──────────────────────────────
            logger.info("[2/6] Creating browser profile")
            profile_config = generate_roxy_profile("telegram", country, proxy_cfg)
            profile = await self.roxy.create_profile(profile_config)
            profile_id = profile["id"]
            profile_name = profile.get("name", profile_config.get("name", ""))
            logger.info("  ✓ Profile: {} ({})", profile_id, profile_name)

            # ── Step 3: Start browser ────────────────────────────────────
            logger.info("[3/6] Starting browser")
            started = await self.roxy.start_profile(profile_id)
            ws_endpoint = started.get("ws_endpoint", "ws://127.0.0.1:9222")
            logger.info("  ✓ CDP: {}", ws_endpoint)

            # ── Step 4: Get phone number ─────────────────────────────────
            logger.info("[4/6] SMS verification")
            phone = None
            sms_request_id = None

            if self.sms_client:
                try:
                    num_data = await self.sms_client.get_telegram_number(country)
                    phone = num_data["number"]
                    sms_request_id = num_data["request_id"]
                    logger.info("  Got number from SMS-Man: {} (req={})", phone, sms_request_id)
                except Exception as e:
                    logger.warning("  SMS-Man failed ({}), enter manually", e)

            if not phone:
                phone = input("  Enter phone number (with country code, e.g. +12125551234): ").strip()

            # ── Step 5: Automate Telegram signup ─────────────────────────
            logger.info("[5/6] Automating Telegram Web signup")
            tg = TelegramSignup(ws_endpoint)
            try:
                page = await tg.connect()
                await tg.open_telegram()
                await tg.enter_phone(phone)

                # Wait for code
                code_ready = await tg.wait_for_code_prompt(timeout=30_000)
                if not code_ready:
                    logger.warning("  Code prompt not detected, continuing anyway")

                # Get verification code
                code = None
                if sms_request_id and self.sms_client:
                    try:
                        code = await self.sms_client.wait_for_code(sms_request_id, timeout=180)
                        logger.info("  ✓ Code from SMS-Man: {}", code)
                    except Exception as e:
                        logger.warning("  SMS-Man code fetch failed ({})", e)

                if not code:
                    code = input("  Enter verification code: ").strip()

                await tg.enter_code(code)
                await tg.complete_profile("User")
                logged_in = await tg.is_logged_in(timeout=15_000)

                if logged_in:
                    logger.info("  ✓✓✓ Account created successfully!")
                else:
                    logger.warning("  Login could not be verified (may still be OK)")

            finally:
                await tg.disconnect()

            # ── Step 6: Save & stop ──────────────────────────────────────
            logger.info("[6/6] Saving session")
            await self.roxy.stop_profile(profile_id)
            logger.info("  ✓ Profile stopped (session saved in Roxy)")

            result = {
                "status": "success" if logged_in else "unverified",
                "profile_id": profile_id,
                "profile_name": profile_name,
                "phone": phone,
                "country": country,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        except KeyboardInterrupt:
            logger.info("Cancelled by user")
            result["error"] = "cancelled"
        except Exception as e:
            logger.error("Error: {}", e)
            result["error"] = str(e)
        finally:
            # Cleanup on failure
            if result.get("status") == "failed" and profile_id:
                try:
                    await self.roxy.stop_profile(profile_id)
                except Exception:
                    pass

        return result

    # ── Fully-automated flow ─────────────────────────────────────────────────

    async def create_account_auto(
        self,
        country: str = "us",
        proxy_str: Optional[str] = None,
        phone: Optional[str] = None,
        code: Optional[str] = None,
        first_name: str = "User",
    ) -> Dict[str, Any]:
        """Fully non-interactive: all params pre-supplied or fetched via API.

        If ``phone`` is None, requests one from SMS-Man.
        If ``code`` is None, polls SMS-Man for the code.
        If ``proxy_str`` is None, picks one from Proxy-Seller.
        """
        profile_id = None
        sms_request_id = None
        result: Dict[str, Any] = {"status": "failed", "country": country}

        try:
            # ── Resolve proxy ────────────────────────────────────────────
            if not proxy_str and self.proxy_client:
                logger.info("Fetching residential proxy for country='{}'…", country)
                proxy = await self.proxy_client.get_residential_proxy(country)
                proxy_str = ProxySellerClient.format_proxy_string(proxy)
                logger.info("  Using residential proxy: {}:{}", proxy["host"], proxy["port"])

            proxy_cfg = parse_proxy_string(proxy_str) if proxy_str else None

            # ── Create Roxy profile ──────────────────────────────────────
            profile_config = generate_roxy_profile("telegram", country, proxy_cfg)
            profile = await self.roxy.create_profile(profile_config)
            profile_id = profile["id"]
            logger.info("Profile created: {}", profile_id)

            # ── Start browser ────────────────────────────────────────────
            started = await self.roxy.start_profile(profile_id)
            ws = started.get("ws_endpoint", "ws://127.0.0.1:9222")

            # ── Resolve phone ────────────────────────────────────────────
            if not phone and self.sms_client:
                num_data = await self.sms_client.get_telegram_number(country)
                phone = num_data["number"]
                sms_request_id = num_data["request_id"]
                logger.info("Got number {} (req={})", phone, sms_request_id)

            if not phone:
                raise ValueError("No phone number available (no SMS client and none provided)")

            # ── Telegram signup ──────────────────────────────────────────
            tg = TelegramSignup(ws)
            try:
                await tg.connect()
                await tg.open_telegram()
                await tg.enter_phone(phone)
                await tg.wait_for_code_prompt(timeout=30_000)

                # Resolve code
                if not code and sms_request_id and self.sms_client:
                    code = await self.sms_client.wait_for_code(sms_request_id, timeout=300)
                    logger.info("✓ SMS code received: {}", code)

                if not code:
                    raise ValueError("No verification code available")

                await tg.enter_code(code)
                await tg.complete_profile(first_name)
                logged_in = await tg.is_logged_in(timeout=15_000)
            finally:
                await tg.disconnect()

            await self.roxy.stop_profile(profile_id)

            result = {
                "status": "success" if logged_in else "unverified",
                "profile_id": profile_id,
                "phone": phone,
                "country": country,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            logger.error("Auto creation failed: {}", e)
            result["error"] = str(e)
            # Cancel SMS number if we requested one
            if sms_request_id and self.sms_client:
                try:
                    await self.sms_client.set_status(sms_request_id, "reject")
                except Exception:
                    pass
            if profile_id:
                try:
                    await self.roxy.stop_profile(profile_id)
                except Exception:
                    pass

        return result

    # ── Batch mode ───────────────────────────────────────────────────────────

    async def create_batch(
        self,
        accounts: list[Dict[str, Any]],
        concurrency: int = 3,
    ) -> list[Dict[str, Any]]:
        """Create multiple accounts with limited concurrency.

        Each item in ``accounts`` may have: country, proxy, phone, code, name.
        If phone/proxy are omitted, they are auto-resolved via APIs.
        """
        sem = asyncio.Semaphore(concurrency)
        results = []

        async def _create_one(acct: Dict[str, Any]):
            async with sem:
                r = await self.create_account_auto(
                    country=acct.get("country", "us"),
                    proxy_str=acct.get("proxy"),
                    phone=acct.get("phone"),
                    code=acct.get("code"),
                    first_name=acct.get("name", "User"),
                )
                results.append(r)

        tasks = [_create_one(a) for a in accounts]
        await asyncio.gather(*tasks, return_exceptions=True)
        return results

    # ── Utilities ────────────────────────────────────────────────────────────

    async def list_profiles(self) -> list:
        return await self.roxy.list_profiles()

    async def check_balance(self) -> Dict[str, Any]:
        balances: Dict[str, Any] = {}
        if self.sms_client:
            try:
                balances["sms_man"] = await self.sms_client.get_balance()
            except Exception as e:
                balances["sms_man"] = f"error: {e}"
        if self.proxy_client:
            try:
                balances["proxy_seller_balance"] = await self.proxy_client.get_balance()
                proxies = await self.proxy_client.get_proxy_list()
                balances["proxy_seller_active"] = len(proxies)
            except Exception as e:
                balances["proxy_seller"] = f"error: {e}"
        return balances

