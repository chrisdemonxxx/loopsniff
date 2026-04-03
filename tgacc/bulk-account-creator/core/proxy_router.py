"""
Unified proxy router for the Telegram bulk outreach framework.

Supports multiple proxy providers (residential, mobile, datacenter) with
automatic fallback, IP rotation, session binding, and health checks.

Usage::

    router = ProxyRouter.from_config()
    proxy = await router.get_proxy_for_session("session_001", country="US")
    # ... session gets burned ...
    new_proxy = await router.rotate_and_rebind("session_001")
"""

from __future__ import annotations

import asyncio
import os
import random
import string
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

import aiohttp
from dotenv import load_dotenv
from loguru import logger

try:
    import python_socks
    SOCKS5 = python_socks.ProxyType.SOCKS5
except ImportError:
    try:
        import socks  # type: ignore[import-untyped]
        SOCKS5 = socks.SOCKS5
    except ImportError:
        SOCKS5 = 2  # raw int fallback matching python-socks SOCKS5


# ── Constants ───────────────────────────────────────────────────────────────

_IP_CHECK_URL = "https://api.ipify.org?format=json"
_IP_CHECK_TIMEOUT = aiohttp.ClientTimeout(total=15)
_ROTATION_STABILISATION_SECS = 12  # wait after mobile modem reconnect
_ROTATION_MAX_RETRIES = 3
_ROTATION_RETRY_DELAY = 5  # seconds between retry attempts


# ── Data types ──────────────────────────────────────────────────────────────

class ProxyType(Enum):
    RESIDENTIAL = "residential"
    MOBILE = "mobile"
    DATACENTER = "datacenter"


@dataclass
class ProxyConfig:
    """Describes a single proxy endpoint with all connection details."""

    host: str
    port: int
    username: str
    password: str
    proxy_type: ProxyType
    country: str = "US"
    session_id: str = ""
    rotation_url: str = ""

    def to_telethon_proxy(self) -> tuple:
        """Return ``(socks.SOCKS5, host, port, True, username, password)``."""
        return (SOCKS5, self.host, self.port, True, self.username, self.password)

    def to_url(self, scheme: str = "socks5") -> str:
        """Return ``socks5://user:pass@host:port``."""
        return f"{scheme}://{self.username}:{self.password}@{self.host}:{self.port}"

    def to_aiohttp_proxy(self) -> str:
        """Return HTTP proxy URL suitable for aiohttp ``proxy=`` kwarg."""
        return self.to_url(scheme="http")


# ── Abstract provider ──────────────────────────────────────────────────────

class BaseProxyProvider(ABC):
    """Interface every proxy provider must implement."""

    @abstractmethod
    async def get_proxy(self, country: str = "US", session_id: str = "") -> ProxyConfig:
        ...

    @abstractmethod
    async def rotate_ip(self, proxy: ProxyConfig) -> bool:
        ...

    @abstractmethod
    async def health_check(self, proxy: ProxyConfig) -> bool:
        ...

    @abstractmethod
    async def get_current_ip(self, proxy: ProxyConfig) -> str:
        ...

    # ── shared helpers ──────────────────────────────────────────────────────

    async def _fetch_ip_via_proxy(self, proxy: ProxyConfig) -> str:
        """Resolve external IP by issuing a request through *proxy*."""
        try:
            async with aiohttp.ClientSession(timeout=_IP_CHECK_TIMEOUT) as sess:
                async with sess.get(
                    _IP_CHECK_URL, proxy=proxy.to_aiohttp_proxy()
                ) as resp:
                    data = await resp.json()
                    return data.get("ip", "")
        except Exception as exc:
            logger.warning("IP check failed via {}: {}", proxy.host, exc)
            return ""


# ── Proxy-Seller residential provider ──────────────────────────────────────

class ProxySellerResidential(BaseProxyProvider):
    """Proxy-Seller residential rotating proxy.

    Rotation is achieved by generating a new ``session_id`` segment in the
    username string — every unique ``_s_<id>`` value maps to a different
    upstream IP.

    Username format::

        {base_user}_c_{COUNTRY}_s_{SESSION_ID}
    """

    _GATEWAYS = {
        "US": "us.res.proxy-seller.com",
        "EU": "res.proxy-seller.com",
        "JP": "asia.res.proxy-seller.com",
        "ASIA": "asia2.res.proxy-seller.com",
    }

    def __init__(
        self,
        username: str,
        password: str,
        gateway: str = "",
        port: int = 10000,
    ):
        self._base_user = username
        self._password = password
        self._gateway = gateway  # auto-select if empty
        self._port = port

    def _pick_gateway(self, country: str) -> str:
        if self._gateway:
            return self._gateway
        cc = country.upper()[:2]
        if cc == "US":
            return self._GATEWAYS["US"]
        if cc == "JP":
            return self._GATEWAYS["JP"]
        return self._GATEWAYS["EU"]

    @staticmethod
    def _random_session() -> str:
        return "".join(random.choices(string.ascii_lowercase + string.digits, k=12))

    def _build_username(self, country: str, session_id: str) -> str:
        user = f"{self._base_user}_c_{country.upper()[:2]}"
        if session_id:
            user += f"_s_{session_id}_ttl_1440m"
        return user

    # ── interface ───────────────────────────────────────────────────────────

    async def get_proxy(self, country: str = "US", session_id: str = "") -> ProxyConfig:
        sid = session_id or self._random_session()
        gateway = self._pick_gateway(country)
        username = self._build_username(country, sid)
        return ProxyConfig(
            host=gateway,
            port=self._port,
            username=username,
            password=self._password,
            proxy_type=ProxyType.RESIDENTIAL,
            country=country.upper()[:2],
            session_id=sid,
        )

    async def rotate_ip(self, proxy: ProxyConfig) -> bool:
        """Rotate by assigning a new session_id (new upstream IP)."""
        old_sid = proxy.session_id
        new_sid = self._random_session()
        proxy.session_id = new_sid
        proxy.username = self._build_username(proxy.country, new_sid)
        logger.info(
            "Residential rotation: session {} → {} on {}",
            old_sid, new_sid, proxy.host,
        )
        return True

    async def health_check(self, proxy: ProxyConfig) -> bool:
        ip = await self.get_current_ip(proxy)
        return bool(ip)

    async def get_current_ip(self, proxy: ProxyConfig) -> str:
        return await self._fetch_ip_via_proxy(proxy)


# ── Mobile proxy provider ──────────────────────────────────────────────────

class MobileProxyProvider(BaseProxyProvider):
    """Generic mobile proxy with HTTP-API-triggered modem rotation.

    ``rotation_url`` is a GET endpoint that triggers the modem to reconnect,
    e.g. ``http://provider.example/api/rotate?key=abc123``.
    """

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        rotation_url: str,
        country: str = "US",
    ):
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._rotation_url = rotation_url
        self._country = country.upper()[:2]

    async def get_proxy(self, country: str = "US", session_id: str = "") -> ProxyConfig:
        return ProxyConfig(
            host=self._host,
            port=self._port,
            username=self._username,
            password=self._password,
            proxy_type=ProxyType.MOBILE,
            country=self._country,
            session_id=session_id,
            rotation_url=self._rotation_url,
        )

    async def rotate_ip(self, proxy: ProxyConfig) -> bool:
        """Fire the rotation endpoint, wait for modem reconnect, verify."""
        if not self._rotation_url:
            logger.error("Mobile rotation URL not configured")
            return False

        old_ip = await self.get_current_ip(proxy)
        logger.info("Mobile rotation starting — old IP: {}", old_ip or "unknown")

        for attempt in range(1, _ROTATION_MAX_RETRIES + 1):
            try:
                async with aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as sess:
                    async with sess.get(self._rotation_url) as resp:
                        status = resp.status
                        body = await resp.text()
                        logger.debug(
                            "Rotation API response (attempt {}): HTTP {} — {}",
                            attempt, status, body[:200],
                        )
            except Exception as exc:
                logger.warning(
                    "Rotation API call failed (attempt {}): {}", attempt, exc
                )
                if attempt < _ROTATION_MAX_RETRIES:
                    await asyncio.sleep(_ROTATION_RETRY_DELAY)
                continue

            # Wait for modem to reconnect and stabilise
            wait = _ROTATION_STABILISATION_SECS + random.uniform(0, 3)
            logger.debug("Waiting {:.1f}s for modem stabilisation…", wait)
            await asyncio.sleep(wait)

            new_ip = await self.get_current_ip(proxy)
            if new_ip and new_ip != old_ip:
                logger.info(
                    "Mobile rotation succeeded: {} → {} (attempt {})",
                    old_ip, new_ip, attempt,
                )
                return True

            logger.warning(
                "IP unchanged after rotation attempt {} (still {})",
                attempt, new_ip or "unknown",
            )
            if attempt < _ROTATION_MAX_RETRIES:
                await asyncio.sleep(_ROTATION_RETRY_DELAY)

        logger.error(
            "Mobile rotation FAILED after {} attempts — IP may still be {}",
            _ROTATION_MAX_RETRIES, old_ip,
        )
        return False

    async def health_check(self, proxy: ProxyConfig) -> bool:
        ip = await self.get_current_ip(proxy)
        return bool(ip)

    async def get_current_ip(self, proxy: ProxyConfig) -> str:
        return await self._fetch_ip_via_proxy(proxy)


# ── Main router ─────────────────────────────────────────────────────────────

class ProxyRouter:
    """Manages providers, session↔proxy bindings, and rotation orchestration."""

    def __init__(self) -> None:
        self._providers: dict[ProxyType, BaseProxyProvider] = {}
        self._session_bindings: dict[str, ProxyConfig] = {}  # session_id → proxy
        self._rotation_count: int = 0
        self._rotation_log: list[dict] = []  # recent rotation events

    # ── provider registration ───────────────────────────────────────────────

    def register_provider(
        self, proxy_type: ProxyType, provider: BaseProxyProvider
    ) -> None:
        self._providers[proxy_type] = provider
        logger.info("Registered proxy provider: {}", proxy_type.value)

    # ── fallback ordering ───────────────────────────────────────────────────

    _FALLBACK_CHAIN = [ProxyType.MOBILE, ProxyType.RESIDENTIAL]

    def _resolve_provider(
        self, preferred: ProxyType = ProxyType.MOBILE
    ) -> tuple[ProxyType, BaseProxyProvider]:
        """Return the best available provider, walking the fallback chain."""
        if preferred in self._providers:
            return preferred, self._providers[preferred]

        for pt in self._FALLBACK_CHAIN:
            if pt in self._providers:
                logger.warning(
                    "Preferred {} unavailable, falling back to {}",
                    preferred.value, pt.value,
                )
                return pt, self._providers[pt]

        # Last resort: any registered provider
        if self._providers:
            pt, prov = next(iter(self._providers.items()))
            logger.warning("Using only available provider: {}", pt.value)
            return pt, prov

        raise RuntimeError("No proxy providers registered")

    # ── session binding ─────────────────────────────────────────────────────

    async def get_proxy_for_session(
        self,
        session_id: str,
        country: str = "US",
        preferred_type: ProxyType = ProxyType.MOBILE,
    ) -> ProxyConfig:
        """Get or create a proxy binding for *session_id*."""
        if session_id in self._session_bindings:
            logger.debug("Returning cached proxy for session {}", session_id)
            return self._session_bindings[session_id]

        _, provider = self._resolve_provider(preferred_type)
        proxy = await provider.get_proxy(country=country, session_id=session_id)
        self._session_bindings[session_id] = proxy
        logger.info(
            "Bound session {} → {}:{} ({})",
            session_id, proxy.host, proxy.port, proxy.proxy_type.value,
        )
        return proxy

    async def rotate_and_rebind(self, session_id: str) -> ProxyConfig:
        """Rotate IP for a burned session and return the refreshed proxy.

        1. Look up the current binding.
        2. Record the old IP.
        3. Ask the provider to rotate.
        4. Verify the IP actually changed.
        5. Remove the old session binding (caller will bind a new session).
        """
        proxy = self._session_bindings.get(session_id)
        if not proxy:
            raise KeyError(f"No proxy binding for session '{session_id}'")

        ptype, provider = self._resolve_provider(proxy.proxy_type)
        old_ip = await provider.get_current_ip(proxy)

        rotated = await provider.rotate_ip(proxy)
        if not rotated:
            logger.error("Rotation failed for session {}", session_id)
            raise RuntimeError(f"Proxy rotation failed for session '{session_id}'")

        # For mobile proxies the rotate_ip call already verifies the IP change.
        # For residential proxies the IP changes instantly with a new session_id.
        new_ip = await provider.get_current_ip(proxy)

        self._rotation_count += 1
        self._rotation_log.append({
            "session_id": session_id,
            "old_ip": old_ip,
            "new_ip": new_ip,
            "provider": ptype.value,
            "timestamp": time.time(),
        })
        # Keep last 100 rotation events
        if len(self._rotation_log) > 100:
            self._rotation_log = self._rotation_log[-100:]

        logger.info(
            "Rotation #{}: {} → {} (provider={}, session={})",
            self._rotation_count, old_ip, new_ip, ptype.value, session_id,
        )

        # Unbind old session
        del self._session_bindings[session_id]
        return proxy

    # ── health checks ───────────────────────────────────────────────────────

    async def health_check_all(self) -> dict[str, bool]:
        """Run health checks against every registered provider in parallel."""
        results: dict[str, bool] = {}

        async def _check(name: str, provider: BaseProxyProvider) -> None:
            try:
                proxy = await provider.get_proxy()
                ok = await provider.health_check(proxy)
                results[name] = ok
            except Exception as exc:
                logger.error("Health check failed for {}: {}", name, exc)
                results[name] = False

        tasks = [
            _check(ptype.value, prov) for ptype, prov in self._providers.items()
        ]
        await asyncio.gather(*tasks)
        return results

    async def verify_ip_changed(
        self, proxy: ProxyConfig, old_ip: str
    ) -> bool:
        """Confirm the proxy's external IP differs from *old_ip*."""
        _, provider = self._resolve_provider(proxy.proxy_type)
        new_ip = await provider.get_current_ip(proxy)
        changed = bool(new_ip) and new_ip != old_ip
        if not changed:
            logger.warning(
                "IP did NOT change — old={}, current={}", old_ip, new_ip
            )
        return changed

    # ── stats / introspection ───────────────────────────────────────────────

    def get_stats(self) -> dict:
        return {
            "rotation_count": self._rotation_count,
            "active_bindings": len(self._session_bindings),
            "bound_sessions": list(self._session_bindings.keys()),
            "registered_providers": [p.value for p in self._providers],
            "recent_rotations": self._rotation_log[-10:],
        }

    # ── factory ─────────────────────────────────────────────────────────────

    @classmethod
    def from_config(cls, config_path: str = ".env") -> "ProxyRouter":
        """Build a ``ProxyRouter`` from environment / ``.env`` variables.

        Recognised variables::

            PROXY_SELLER_USER   — Proxy-Seller residential username
            PROXY_SELLER_PASS   — Proxy-Seller residential password
            PROXY_SELLER_GW     — gateway override (optional)
            PROXY_SELLER_PORT   — port override (default 10000)
            PROXY_COUNTRY       — default country (default US)

            MOBILE_PROXY_HOST
            MOBILE_PROXY_PORT
            MOBILE_PROXY_USER
            MOBILE_PROXY_PASS
            MOBILE_PROXY_ROTATION_URL
            MOBILE_PROXY_COUNTRY
        """
        env_file = Path(config_path)
        if env_file.exists():
            load_dotenv(env_file)

        router = cls()
        country = os.getenv("PROXY_COUNTRY", "US")

        # -- Proxy-Seller residential ----------------------------------------
        ps_user = os.getenv("PROXY_SELLER_USER", "")
        ps_pass = os.getenv("PROXY_SELLER_PASS", os.getenv("PROXY_PASSWORD", ""))
        if ps_user:
            gateway = os.getenv("PROXY_SELLER_GW", "")
            port = int(os.getenv("PROXY_SELLER_PORT", "10000"))
            provider = ProxySellerResidential(
                username=ps_user,
                password=ps_pass,
                gateway=gateway,
                port=port,
            )
            router.register_provider(ProxyType.RESIDENTIAL, provider)
            logger.info("Proxy-Seller residential configured (user={})", ps_user)

        # -- Mobile proxy ----------------------------------------------------
        mob_host = os.getenv("MOBILE_PROXY_HOST", "")
        mob_port = os.getenv("MOBILE_PROXY_PORT", "0")
        mob_user = os.getenv("MOBILE_PROXY_USER", "")
        mob_pass = os.getenv("MOBILE_PROXY_PASS", "")
        mob_rotation = os.getenv("MOBILE_PROXY_ROTATION_URL", "")
        mob_country = os.getenv("MOBILE_PROXY_COUNTRY", country)

        if mob_host and int(mob_port):
            provider = MobileProxyProvider(
                host=mob_host,
                port=int(mob_port),
                username=mob_user,
                password=mob_pass,
                rotation_url=mob_rotation,
                country=mob_country,
            )
            router.register_provider(ProxyType.MOBILE, provider)
            logger.info("Mobile proxy configured ({}:{})", mob_host, mob_port)

        if not router._providers:
            logger.warning(
                "No proxy providers configured — set PROXY_SELLER_USER or "
                "MOBILE_PROXY_HOST in your environment"
            )

        return router
