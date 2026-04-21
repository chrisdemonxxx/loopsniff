"""Rate limiter — anti-ban protection for the AI userbot.

Telegram aggressively rate-limits and bans accounts that send too many
messages.  This module enforces conservative limits that keep the account
safe while still handling meaningful conversation volume.

Default limits (conservative, tunable via .env):
  - 8 replies per hour  (avg 1 every 7.5 min)
  - 50 replies per day  (business hours only)
  - 5-25 second delay before each reply (randomised)
  - Typing speed simulation (3-6 chars/sec)
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
import time
from collections import deque
from datetime import datetime

log = logging.getLogger(__name__)


class RateLimiter:
    """Sliding-window rate limiter with typing simulation."""

    def __init__(
        self,
        max_per_hour: int = int(os.getenv("MAX_REPLIES_PER_HOUR", "8")),
        max_per_day: int = int(os.getenv("MAX_REPLIES_PER_DAY", "50")),
        min_delay: float = float(os.getenv("MIN_REPLY_DELAY", "5")),
        max_delay: float = float(os.getenv("MAX_REPLY_DELAY", "25")),
        typing_speed_min: float = float(os.getenv("TYPING_SPEED_MIN", "3.0")),
        typing_speed_max: float = float(os.getenv("TYPING_SPEED_MAX", "6.0")),
        think_delay_min: float = float(os.getenv("THINK_DELAY_MIN", "1.0")),
        think_delay_max: float = float(os.getenv("THINK_DELAY_MAX", "5.0")),
    ):
        self.max_per_hour = max_per_hour
        self.max_per_day = max_per_day
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.typing_speed_min = typing_speed_min
        self.typing_speed_max = typing_speed_max
        self.think_delay_min = think_delay_min
        self.think_delay_max = think_delay_max

        # Sliding windows
        self._hourly: deque[float] = deque()   # timestamps of sends in last hour
        self._daily: deque[float] = deque()    # timestamps of sends today
        self._last_send: float = 0.0

    def _prune(self) -> None:
        """Remove expired entries from sliding windows."""
        now = time.time()
        hour_ago = now - 3600
        while self._hourly and self._hourly[0] < hour_ago:
            self._hourly.popleft()

        today_start = datetime.utcnow().replace(
            hour=0, minute=0, second=0, microsecond=0
        ).timestamp()
        while self._daily and self._daily[0] < today_start:
            self._daily.popleft()

    def can_send(self) -> bool:
        """Check if we're within rate limits."""
        self._prune()
        if len(self._hourly) >= self.max_per_hour:
            log.warning(
                "Rate limit: %d/%d hourly sends — pausing",
                len(self._hourly), self.max_per_hour,
            )
            return False
        if len(self._daily) >= self.max_per_day:
            log.warning(
                "Rate limit: %d/%d daily sends — pausing until tomorrow",
                len(self._daily), self.max_per_day,
            )
            return False
        return True

    def record_send(self) -> None:
        """Record a successful send."""
        now = time.time()
        self._hourly.append(now)
        self._daily.append(now)
        self._last_send = now

    def time_until_available(self) -> float:
        """Seconds until we can send again (0 if ready now)."""
        self._prune()
        if len(self._hourly) >= self.max_per_hour and self._hourly:
            return (self._hourly[0] + 3600) - time.time()
        if len(self._daily) >= self.max_per_day:
            tomorrow = datetime.utcnow().replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            return (tomorrow.timestamp() + 86400) - time.time()
        return 0.0

    @property
    def stats(self) -> dict:
        """Current usage stats."""
        self._prune()
        return {
            "hourly": f"{len(self._hourly)}/{self.max_per_hour}",
            "daily": f"{len(self._daily)}/{self.max_per_day}",
            "can_send": self.can_send(),
        }

    # ── Human-like delays ────────────────────────────────────────────────

    def random_reply_delay(self) -> float:
        """Random delay before starting to type (simulates reading + thinking)."""
        return random.uniform(self.min_delay, self.max_delay)

    def typing_duration(self, text: str) -> float:
        """How long it takes to 'type' a message at human speed.

        Returns seconds, based on text length and random typing speed.
        """
        chars = len(text)
        speed = random.uniform(self.typing_speed_min, self.typing_speed_max)
        base = chars / speed

        # Add think pauses (like re-reading what you typed)
        think_pause = random.uniform(self.think_delay_min, self.think_delay_max)
        return base + think_pause

    async def wait_before_reply(self, text: str) -> float:
        """Full pre-reply delay: read → think → type.

        Call this before sending each message. Returns total wait time.
        """
        read_delay = self.random_reply_delay()
        type_time = self.typing_duration(text)
        total = read_delay + type_time

        # Cap at 60 seconds — anything more feels unresponsive
        total = min(total, 60.0)

        log.debug(
            "Delay: %.1fs read + %.1fs type = %.1fs total",
            read_delay, type_time, total,
        )
        await asyncio.sleep(total)
        return total


class ConversationThrottler:
    """Per-user cooldown to avoid rapid-fire exchanges.

    Prevents the bot from responding to multiple messages from the same
    user within a short window (they might still be typing).
    """

    def __init__(self, cooldown: float = 3.0):
        self.cooldown = cooldown
        self._last_activity: dict[int, float] = {}

    def should_wait(self, user_id: int) -> bool:
        """True if the user sent a message too recently."""
        last = self._last_activity.get(user_id, 0)
        return (time.time() - last) < self.cooldown

    def record(self, user_id: int) -> None:
        self._last_activity[user_id] = time.time()

    async def wait_for_user(self, user_id: int) -> None:
        """Wait until the user's cooldown expires."""
        while self.should_wait(user_id):
            await asyncio.sleep(0.5)
        self.record(user_id)
