"""Anti-ban engine — evasion protocols for throwaway Telegram outreach sessions.

Sub-components:
  a) MicroBatchController  — burn-and-churn batch lifecycle
  b) ApiIdPool             — api_id/api_hash rotation with quarantine
  c) DeviceTelemetryRandomizer — realistic device fingerprints
  d) GaussianJitter        — human-like timing via bell-curve delays
  e) TypingSimulator       — typing action before message dispatch
  f) ErrorHandler          — decide burn / rest / retry / skip per error
"""

from __future__ import annotations

import asyncio
import json
import math
import os
import secrets
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

import numpy as np
from loguru import logger


# ============================================================
# 3a. MICRO-BATCH CONTROLLER
# ============================================================

@dataclass
class MicroBatchConfig:
    min_messages: int = 1
    max_messages: int = 5
    default_batch_size: int = 3


class MicroBatchController:
    """Controls the micro-batch lifecycle for throwaway sessions."""

    def __init__(self, config: MicroBatchConfig | None = None):
        self.config = config or MicroBatchConfig()
        self._batch_count: int = 0

    def start_batch(self) -> int:
        """Start a new micro-batch. Returns the batch size (randomised within min-max)."""
        self._batch_count = 0
        span = self.config.max_messages - self.config.min_messages + 1
        size = secrets.randbelow(span) + self.config.min_messages
        return size

    def increment(self) -> int:
        """Increment batch counter. Returns current count."""
        self._batch_count += 1
        return self._batch_count

    def should_burn(self, batch_limit: int) -> bool:
        """Check if batch limit reached and session should be burned."""
        return self._batch_count >= batch_limit

    @property
    def count(self) -> int:
        return self._batch_count


# ============================================================
# 3b. API ID POOL ROTATION
# ============================================================

@dataclass
class ApiIdEntry:
    api_id: int
    api_hash: str
    sessions_bound: int = 0
    max_sessions: int = 12
    is_quarantined: bool = False
    quarantined_reason: str = ""


class ApiIdPool:
    """Manages a pool of api_id/api_hash pairs with load-balanced rotation."""

    def __init__(self, pool_path: str = "outreach/data/api_id_pool.json"):
        self.pool_path = pool_path
        self.pool: list[ApiIdEntry] = []

    def load(self):
        """Load pool from JSON file."""
        path = Path(self.pool_path)
        if not path.exists():
            logger.warning(f"API ID pool file not found: {self.pool_path}")
            return
        try:
            with open(path) as f:
                data = json.load(f)
            self.pool = [
                ApiIdEntry(
                    api_id=e["api_id"],
                    api_hash=e["api_hash"],
                    sessions_bound=e.get("sessions_bound", 0),
                    max_sessions=e.get("max_sessions", 12),
                    is_quarantined=e.get("is_quarantined", False),
                    quarantined_reason=e.get("quarantined_reason", ""),
                )
                for e in data
            ]
            logger.info(f"Loaded {len(self.pool)} api_id entries from {self.pool_path}")
        except Exception as exc:
            logger.error(f"Failed to load API ID pool: {exc}")

    def save(self):
        """Save pool to JSON file."""
        path = Path(self.pool_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = [
            {
                "api_id": e.api_id,
                "api_hash": e.api_hash,
                "sessions_bound": e.sessions_bound,
                "max_sessions": e.max_sessions,
                "is_quarantined": e.is_quarantined,
                "quarantined_reason": e.quarantined_reason,
            }
            for e in self.pool
        ]
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        logger.debug(f"Saved {len(self.pool)} api_id entries to {self.pool_path}")

    def get_available(self) -> Optional[ApiIdEntry]:
        """Get an api_id that hasn't reached its session limit (least-loaded first)."""
        candidates = [
            e for e in self.pool
            if not e.is_quarantined and e.sessions_bound < e.max_sessions
        ]
        if not candidates:
            return None
        candidates.sort(key=lambda e: e.sessions_bound)
        return candidates[0]

    def bind_session(self, api_id: int) -> bool:
        """Increment sessions_bound for an api_id. Returns False if at max."""
        for entry in self.pool:
            if entry.api_id == api_id:
                if entry.is_quarantined or entry.sessions_bound >= entry.max_sessions:
                    return False
                entry.sessions_bound += 1
                self.save()
                return True
        return False

    def unbind_session(self, api_id: int):
        """Decrement sessions_bound when a session is burned."""
        for entry in self.pool:
            if entry.api_id == api_id:
                entry.sessions_bound = max(0, entry.sessions_bound - 1)
                self.save()
                return

    def quarantine(self, api_id: int, reason: str = "API_ID_PUBLISHED_FLOOD"):
        """Quarantine an api_id — marks it as compromised."""
        for entry in self.pool:
            if entry.api_id == api_id:
                entry.is_quarantined = True
                entry.quarantined_reason = reason
                logger.critical(
                    f"API ID {api_id} QUARANTINED: {reason} "
                    f"({entry.sessions_bound} sessions affected)"
                )
        self.save()

    def add(self, api_id: int, api_hash: str, max_sessions: int = 12):
        """Add a new api_id to the pool."""
        for entry in self.pool:
            if entry.api_id == api_id:
                logger.warning(f"API ID {api_id} already in pool — skipping")
                return
        self.pool.append(ApiIdEntry(
            api_id=api_id,
            api_hash=api_hash,
            max_sessions=max_sessions,
        ))
        self.save()
        logger.info(f"Added API ID {api_id} to pool (max_sessions={max_sessions})")

    def get_stats(self) -> dict:
        """Pool statistics: total, available, quarantined, sessions_bound."""
        total = len(self.pool)
        quarantined = sum(1 for e in self.pool if e.is_quarantined)
        available = sum(
            1 for e in self.pool
            if not e.is_quarantined and e.sessions_bound < e.max_sessions
        )
        total_sessions = sum(e.sessions_bound for e in self.pool)
        return {
            "total": total,
            "available": available,
            "quarantined": quarantined,
            "total_sessions_bound": total_sessions,
        }


# ============================================================
# 3c. DEVICE TELEMETRY RANDOMIZER
# ============================================================

@dataclass
class DeviceProfile:
    device_model: str
    system_version: str
    app_version: str
    lang_code: str
    system_lang_code: str


class DeviceTelemetryRandomizer:
    """Generate consistent, realistic device fingerprints."""

    DEVICE_FAMILIES = [
        # iOS devices
        {
            "models": [
                "iPhone 14 Pro", "iPhone 14 Pro Max",
                "iPhone 15", "iPhone 15 Pro", "iPhone 15 Pro Max",
                "iPhone 16 Pro", "iPhone 16 Pro Max",
            ],
            "os_prefix": "iOS",
            "versions": [
                "16.5.1", "16.6", "17.0", "17.1.2", "17.2",
                "17.3.1", "17.4", "17.5.1", "18.0", "18.1",
            ],
        },
        # Samsung devices
        {
            "models": [
                "Samsung Galaxy S23", "Samsung Galaxy S23 Ultra",
                "Samsung Galaxy S24", "Samsung Galaxy S24 Ultra",
                "Samsung Galaxy S25 Ultra",
            ],
            "os_prefix": "Android",
            "versions": ["13.0", "14.0", "15.0"],
        },
        # Google Pixel devices
        {
            "models": [
                "Google Pixel 7", "Google Pixel 7 Pro",
                "Google Pixel 8", "Google Pixel 8 Pro",
                "Google Pixel 9 Pro",
            ],
            "os_prefix": "Android",
            "versions": ["13.0", "14.0", "15.0"],
        },
        # OnePlus devices
        {
            "models": ["OnePlus 11", "OnePlus 12", "OnePlus Nord 3"],
            "os_prefix": "Android",
            "versions": ["13.0", "14.0"],
        },
    ]

    APP_VERSIONS = [
        "11.5.4", "11.6.0", "11.6.2", "11.7.0",
        "11.7.4", "11.8.0", "11.8.2",
    ]

    LANG_MAP = {
        "US": "en", "GB": "en", "CA": "en", "AU": "en",
        "DE": "de", "FR": "fr", "ES": "es", "IT": "it",
        "RU": "ru", "UA": "uk", "BR": "pt", "IN": "hi",
        "JP": "ja", "KR": "ko", "CN": "zh",
    }

    def generate(self, country: str = "US") -> DeviceProfile:
        """Generate a random but internally-consistent device profile.

        Model and OS version always come from the same device family so
        impossible combinations (e.g. iOS on Samsung) are never produced.
        """
        family = secrets.choice(self.DEVICE_FAMILIES)
        model = secrets.choice(family["models"])
        os_version = secrets.choice(family["versions"])
        system_version = f"{family['os_prefix']} {os_version}"
        app_version = secrets.choice(self.APP_VERSIONS)
        lang_code = self.LANG_MAP.get(country.upper(), "en")

        return DeviceProfile(
            device_model=model,
            system_version=system_version,
            app_version=app_version,
            lang_code=lang_code,
            system_lang_code=lang_code,
        )

    def generate_batch(self, count: int, country: str = "US") -> list[DeviceProfile]:
        """Generate multiple unique device profiles."""
        profiles: list[DeviceProfile] = []
        seen: set[str] = set()
        for _ in range(count):
            for _attempt in range(20):
                p = self.generate(country)
                key = f"{p.device_model}|{p.system_version}"
                if key not in seen:
                    seen.add(key)
                    profiles.append(p)
                    break
            else:
                # Allow duplicates if uniqueness space exhausted
                profiles.append(self.generate(country))
        return profiles


# ============================================================
# 3d. GAUSSIAN JITTER ENGINE
# ============================================================

class GaussianJitter:
    """Injects human-like timing delays using Gaussian (bell-curve) distribution.

    Unlike uniform random, Gaussian clusters delays around a mean with natural
    variance — the resulting timing pattern is harder for anti-spam heuristics
    to fingerprint as automated.
    """

    @staticmethod
    async def sleep(
        base: float,
        sigma: float | None = None,
        min_val: float | None = None,
        max_val: float | None = None,
    ) -> float:
        """Sleep for a Gaussian-distributed duration.

        Args:
            base:    Mean delay in seconds.
            sigma:   Standard deviation (default: base * 0.3).
            min_val: Floor value (default: base * 0.5).
            max_val: Ceiling value (default: base * 2.0).

        Returns:
            Actual delay applied (seconds).
        """
        if sigma is None:
            sigma = base * 0.3
        if min_val is None:
            min_val = base * 0.5
        if max_val is None:
            max_val = base * 2.0

        delay = float(np.random.normal(base, sigma))
        delay = max(min_val, min(max_val, delay))

        logger.debug(f"Gaussian sleep: {delay:.1f}s (base={base}, σ={sigma})")
        await asyncio.sleep(delay)
        return delay

    @staticmethod
    async def inter_message_delay() -> float:
        """Standard delay between messages in a micro-batch (25s base, σ=8)."""
        return await GaussianJitter.sleep(base=25.0, sigma=8.0, min_val=12.0, max_val=50.0)

    @staticmethod
    async def inter_session_delay() -> float:
        """Delay between session rotations (10s base, σ=3)."""
        return await GaussianJitter.sleep(base=10.0, sigma=3.0, min_val=5.0, max_val=20.0)

    @staticmethod
    async def inter_campaign_cooldown() -> float:
        """Cooldown between full pool cycles (5–15 min)."""
        return await GaussianJitter.sleep(base=600.0, sigma=150.0, min_val=300.0, max_val=900.0)


# ============================================================
# 3e. TYPING ACTION SIMULATION
# ============================================================

class TypingSimulator:
    """Simulate human typing behaviour before message dispatch."""

    # ~40-60 WPM on mobile ≈ 4-5 chars/sec → ~0.12-0.18s per char
    CHAR_RATE = 0.15       # seconds per character (base)
    CHAR_RATE_SIGMA = 0.03 # variance

    @staticmethod
    def calculate_typing_duration(message: str) -> float:
        """Calculate realistic typing duration based on message length.

        Factors: character-by-character speed + random thinking pauses.
        """
        char_count = len(message)
        base_time = char_count * TypingSimulator.CHAR_RATE
        noise = float(np.random.normal(0, char_count * TypingSimulator.CHAR_RATE_SIGMA))
        # 1–3 thinking pauses of 0.5–2s each
        num_pauses = secrets.randbelow(3) + 1
        pause_time = sum(float(np.random.uniform(0.5, 2.0)) for _ in range(num_pauses))

        duration = base_time + noise + pause_time
        return max(2.0, min(duration, 30.0))

    @staticmethod
    async def send_typing(client, target, message: str):
        """Send typing action to *target* for a realistic duration.

        Args:
            client:  TelegramClient instance.
            target:  Target user/entity.
            message: The message about to be sent (for length calculation).
        """
        from telethon.tl.functions.messages import SetTypingRequest
        from telethon.tl.types import SendMessageTypingAction

        duration = TypingSimulator.calculate_typing_duration(message)
        logger.debug(f"Typing simulation: {duration:.1f}s for {len(message)} chars")

        try:
            await client(SetTypingRequest(
                peer=target,
                action=SendMessageTypingAction(),
            ))
            await asyncio.sleep(duration)
        except Exception as e:
            logger.warning(f"Typing action failed (non-fatal): {e}")


# ============================================================
# 3f. ENHANCED ERROR HANDLER
# ============================================================

class BurnReason(Enum):
    BATCH_LIMIT = "batch_limit_reached"
    PEER_FLOOD = "PeerFloodError"
    FLOOD_WAIT_HIGH = "FloodWait_gt_60s"
    AUTH_KEY_INVALID = "AUTH_KEY_UNREGISTERED"
    USER_DEACTIVATED = "UserDeactivatedBanError"
    PHONE_BANNED = "PhoneNumberBannedError"
    API_ID_FLOOD = "API_ID_PUBLISHED_FLOOD"
    UNKNOWN = "unknown_error"


@dataclass
class ErrorAction:
    should_burn: bool = False
    should_rest: bool = False
    should_quarantine_api: bool = False
    rest_seconds: int = 0
    burn_reason: BurnReason = BurnReason.UNKNOWN
    should_skip_target: bool = False
    should_retry: bool = False
    retry_after: int = 0
    alert_admin: bool = False
    alert_message: str = ""


class ErrorHandler:
    """Enhanced error handler for Telegram API errors.

    Decides whether to burn, rest, retry, or skip based on error type.
    String-based error name matching is used as a fallback for imports that
    might not exist in all Telethon versions.
    """

    FLOOD_WAIT_BURN_THRESHOLD = 60  # seconds; above this → burn

    @staticmethod
    def handle(error: Exception) -> ErrorAction:
        """Analyse a Telegram error and return the appropriate action."""
        from telethon.errors import FloodWaitError

        error_name = type(error).__name__

        # --- FloodWaitError: check threshold ---
        if isinstance(error, FloodWaitError):
            wait_seconds = error.seconds
            if wait_seconds <= ErrorHandler.FLOOD_WAIT_BURN_THRESHOLD:
                logger.warning(f"FloodWait {wait_seconds}s — sleeping and retrying")
                return ErrorAction(
                    should_retry=True,
                    retry_after=wait_seconds + 5,
                )
            else:
                logger.error(
                    f"FloodWait {wait_seconds}s "
                    f"(>{ErrorHandler.FLOOD_WAIT_BURN_THRESHOLD}s) — BURNING session"
                )
                return ErrorAction(
                    should_burn=True,
                    burn_reason=BurnReason.FLOOD_WAIT_HIGH,
                    alert_admin=True,
                    alert_message=f"Session burned: FloodWait {wait_seconds}s",
                )

        # --- PeerFloodError: instant burn ---
        if error_name == "PeerFloodError":
            logger.error("PeerFloodError — INSTANT BURN + IP rotation required")
            return ErrorAction(
                should_burn=True,
                burn_reason=BurnReason.PEER_FLOOD,
                alert_admin=True,
                alert_message="PeerFloodError — session burned, rotating IP",
            )

        # --- AUTH_KEY_UNREGISTERED: permanent ban ---
        if error_name in ("AuthKeyUnregisteredError", "AuthKeyError"):
            logger.error("AUTH_KEY_UNREGISTERED — session permanently invalid")
            return ErrorAction(
                should_burn=True,
                burn_reason=BurnReason.AUTH_KEY_INVALID,
                alert_admin=True,
                alert_message="Auth key invalid — session permanently dead",
            )

        # --- UserDeactivatedBanError / PhoneNumberBannedError ---
        if error_name in (
            "UserDeactivatedBanError", "UserDeactivatedError",
            "PhoneNumberBannedError",
        ):
            logger.error(f"{error_name} — account terminated")
            reason = (
                BurnReason.USER_DEACTIVATED
                if "Deactivated" in error_name
                else BurnReason.PHONE_BANNED
            )
            return ErrorAction(
                should_burn=True,
                burn_reason=reason,
                alert_admin=True,
                alert_message=f"Account terminated: {error_name}",
            )

        # --- API_ID_PUBLISHED_FLOOD: quarantine entire api_id cluster ---
        if "API_ID_PUBLISHED_FLOOD" in str(error) or error_name == "ApiIdPublishedFloodError":
            logger.critical("API_ID_PUBLISHED_FLOOD — quarantine entire api_id cluster!")
            return ErrorAction(
                should_burn=True,
                should_quarantine_api=True,
                burn_reason=BurnReason.API_ID_FLOOD,
                alert_admin=True,
                alert_message=(
                    "⚠️ CRITICAL: API_ID_PUBLISHED_FLOOD — "
                    "all sessions with this api_id are compromised!"
                ),
            )

        # --- UserPrivacyRestrictedError: skip target, don't burn ---
        if error_name == "UserPrivacyRestrictedError":
            logger.info("Target has privacy restrictions — skipping (not a ban)")
            return ErrorAction(should_skip_target=True)

        # --- InputUserDeactivatedError: target account is dead ---
        if error_name == "InputUserDeactivatedError":
            logger.info("Target account deactivated — skipping")
            return ErrorAction(should_skip_target=True)

        # --- ChatWriteForbiddenError / UserBannedInChannelError: skip ---
        if error_name in ("ChatWriteForbiddenError", "UserBannedInChannelError"):
            logger.info(f"{error_name} — skipping target")
            return ErrorAction(should_skip_target=True)

        # --- Unknown error: rest the session (conservative) ---
        logger.warning(f"Unknown error: {error_name}: {error} — resting session 30min")
        return ErrorAction(
            should_rest=True,
            rest_seconds=1800,
            burn_reason=BurnReason.UNKNOWN,
        )


# ============================================================
# UNIFIED ANTI-BAN ENGINE
# ============================================================

class AntiBanEngine:
    """Unified anti-ban engine combining all sub-components."""

    def __init__(self, config: dict | None = None):
        config = config or {}
        self.micro_batch = MicroBatchController(
            MicroBatchConfig(
                min_messages=config.get("min_batch", 1),
                max_messages=config.get("max_batch", 5),
                default_batch_size=config.get("default_batch", 3),
            )
        )
        self.api_pool = ApiIdPool(
            config.get("api_pool_path", "outreach/data/api_id_pool.json")
        )
        self.device_randomizer = DeviceTelemetryRandomizer()
        self.jitter = GaussianJitter()
        self.typing = TypingSimulator()
        self.error_handler = ErrorHandler()

    def initialize(self):
        """Load persisted state (api_id pool, etc.)."""
        self.api_pool.load()

    def get_batch_size(self) -> int:
        """Start a new micro-batch and return the size."""
        return self.micro_batch.start_batch()

    def get_device_profile(self, country: str = "US") -> DeviceProfile:
        """Generate a device profile for a new session."""
        return self.device_randomizer.generate(country)

    def get_api_credentials(self) -> Optional[ApiIdEntry]:
        """Get available api_id from pool."""
        return self.api_pool.get_available()

    async def pre_message_delay(self, message: str, client, target):
        """Execute typing simulation + jitter before sending."""
        await self.typing.send_typing(client, target, message)

    async def post_message_delay(self):
        """Gaussian delay after message sent."""
        await self.jitter.inter_message_delay()

    async def post_session_delay(self):
        """Delay after session burn before next session."""
        await self.jitter.inter_session_delay()

    def handle_error(self, error: Exception) -> ErrorAction:
        """Process an error and return action."""
        return self.error_handler.handle(error)


# ============================================================
# DEMO / SELF-TEST
# ============================================================

if __name__ == "__main__":
    import sys

    async def _demo():
        logger.remove()
        logger.add(sys.stderr, level="DEBUG")

        # --- MicroBatchController ---
        logger.info("=== MicroBatchController ===")
        mbc = MicroBatchController()
        batch_size = mbc.start_batch()
        logger.info(f"Batch size: {batch_size}")
        for i in range(batch_size):
            mbc.increment()
            logger.info(f"  Message {mbc.count}/{batch_size} — burn={mbc.should_burn(batch_size)}")

        # --- DeviceTelemetryRandomizer ---
        logger.info("\n=== DeviceTelemetryRandomizer ===")
        dtr = DeviceTelemetryRandomizer()
        for country in ("US", "DE", "JP"):
            profile = dtr.generate(country)
            logger.info(f"  [{country}] {profile.device_model} / {profile.system_version} / "
                        f"app={profile.app_version} / lang={profile.lang_code}")

        logger.info("  Batch of 5 unique profiles:")
        batch = dtr.generate_batch(5, "US")
        for p in batch:
            logger.info(f"    {p.device_model} — {p.system_version}")

        # --- GaussianJitter ---
        logger.info("\n=== GaussianJitter ===")
        delay = await GaussianJitter.sleep(base=2.0, sigma=0.5, min_val=0.5, max_val=4.0)
        logger.info(f"  Gaussian sleep returned: {delay:.2f}s")

        # --- TypingSimulator ---
        logger.info("\n=== TypingSimulator ===")
        test_messages = [
            "Hi!",
            "Hey, I noticed your work in crypto trading and wanted to connect.",
            "We run a performance marketing agency specialising in traffic arbitrage.",
        ]
        for msg in test_messages:
            duration = TypingSimulator.calculate_typing_duration(msg)
            logger.info(f"  \"{msg[:40]}…\" ({len(msg)} chars) → {duration:.1f}s typing")

        # --- ApiIdPool ---
        logger.info("\n=== ApiIdPool ===")
        pool = ApiIdPool("outreach/data/api_id_pool.json")
        pool.add(12345, "abc123hash", max_sessions=3)
        pool.add(67890, "def456hash", max_sessions=3)
        logger.info(f"  Stats: {pool.get_stats()}")
        entry = pool.get_available()
        if entry:
            logger.info(f"  Available: api_id={entry.api_id}, bound={entry.sessions_bound}")
            pool.bind_session(entry.api_id)
            logger.info(f"  After bind: {pool.get_stats()}")
            pool.unbind_session(entry.api_id)
            logger.info(f"  After unbind: {pool.get_stats()}")

        # --- ErrorHandler ---
        logger.info("\n=== ErrorHandler ===")
        handler = ErrorHandler()
        # Simulate errors using generic exceptions (Telethon not required for demo)
        for err_name, err_msg in [
            ("PeerFloodError", "Too many requests"),
            ("UserPrivacyRestrictedError", "Privacy settings"),
            ("AuthKeyUnregisteredError", "Auth key dead"),
            ("RuntimeError", "Something unexpected"),
        ]:
            fake_err = type(err_name, (Exception,), {})(err_msg)
            action = handler.handle(fake_err)
            logger.info(
                f"  {err_name}: burn={action.should_burn}, skip={action.should_skip_target}, "
                f"retry={action.should_retry}, rest={action.should_rest}"
            )

        # --- AntiBanEngine (unified) ---
        logger.info("\n=== AntiBanEngine ===")
        engine = AntiBanEngine({"min_batch": 2, "max_batch": 4})
        bs = engine.get_batch_size()
        logger.info(f"  Batch size: {bs}")
        dp = engine.get_device_profile("US")
        logger.info(f"  Device: {dp.device_model} / {dp.system_version}")

        logger.info("\n✅ All anti-ban components verified.")

    asyncio.run(_demo())
