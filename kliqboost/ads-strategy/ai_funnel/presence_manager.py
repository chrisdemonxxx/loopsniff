"""Online/offline presence simulator — makes the userbot look human.

Simulates realistic online/offline patterns so Telegram's systems
(and users) see a natural activity profile, not a 24/7 bot.

Features:
  - Business hours scheduling (configurable timezone)
  - Random online/offline cycling during active hours
  - Gradual session start/end (not instant on/off)
  - Sleep hours enforcement (no replies at 3 AM)
  - Weekend reduced activity
"""

from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime, time, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

log = logging.getLogger(__name__)


class PresenceManager:
    """Manage online/offline state for the userbot."""

    def __init__(
        self,
        timezone: str = "America/Los_Angeles",
        work_start: int = 9,     # 9 AM
        work_end: int = 23,      # 11 PM
        weekend_start: int = 11, # later start on weekends
        weekend_end: int = 21,   # earlier end on weekends
    ):
        self.tz = ZoneInfo(timezone)
        self.work_start = work_start
        self.work_end = work_end
        self.weekend_start = weekend_start
        self.weekend_end = weekend_end
        self._is_online = False
        self._session_start: Optional[datetime] = None

    @property
    def now(self) -> datetime:
        return datetime.now(self.tz)

    @property
    def is_weekend(self) -> bool:
        return self.now.weekday() >= 5  # Saturday=5, Sunday=6

    def is_active_hours(self) -> bool:
        """Check if current time is within work hours."""
        hour = self.now.hour
        if self.is_weekend:
            return self.weekend_start <= hour < self.weekend_end
        return self.work_start <= hour < self.work_end

    def should_respond(self) -> bool:
        """Whether the bot should respond right now."""
        if not self.is_active_hours():
            log.debug("Outside active hours — not responding")
            return False
        return True

    def time_until_active(self) -> float:
        """Seconds until the next active period starts."""
        if self.is_active_hours():
            return 0.0

        now = self.now
        start_hour = self.weekend_start if self.is_weekend else self.work_start

        # If past work_end today, next active is tomorrow
        if now.hour >= (self.weekend_end if self.is_weekend else self.work_end):
            tomorrow = now + timedelta(days=1)
            is_weekend_tomorrow = tomorrow.weekday() >= 5
            start = self.weekend_start if is_weekend_tomorrow else self.work_start
            next_active = tomorrow.replace(hour=start, minute=0, second=0, microsecond=0)
        else:
            # Before work_start today
            next_active = now.replace(hour=start_hour, minute=0, second=0, microsecond=0)

        return max(0, (next_active - now).total_seconds())

    async def simulate_online_cycle(self, client) -> None:
        """Run continuous online/offline cycling.

        Call this as a background task. The client should be a Telethon
        TelegramClient with update_status support.
        """
        while True:
            if not self.is_active_hours():
                # Go offline during off-hours
                if self._is_online:
                    try:
                        from telethon.tl.functions.account import UpdateStatusRequest
                        await client(UpdateStatusRequest(offline=True))
                    except Exception:
                        pass
                    self._is_online = False
                    log.debug("Going offline (outside active hours)")

                wait = self.time_until_active()
                # Add some randomness so we don't come online at exactly 9:00
                jitter = random.uniform(0, 15 * 60)  # 0-15 min
                await asyncio.sleep(wait + jitter)
                continue

            # During active hours: cycle between online and offline
            if not self._is_online:
                try:
                    from telethon.tl.functions.account import UpdateStatusRequest
                    await client(UpdateStatusRequest(offline=False))
                except Exception:
                    pass
                self._is_online = True
                self._session_start = self.now
                log.debug("Going online")

            # Stay online for 15-45 minutes
            online_duration = random.uniform(15 * 60, 45 * 60)
            await asyncio.sleep(online_duration)

            # Go offline for 5-20 minutes
            try:
                from telethon.tl.functions.account import UpdateStatusRequest
                await client(UpdateStatusRequest(offline=True))
            except Exception:
                pass
            self._is_online = False
            log.debug("Brief offline break")

            offline_duration = random.uniform(5 * 60, 20 * 60)
            await asyncio.sleep(offline_duration)

    def get_away_message(self) -> str:
        """Generate a natural 'away' message for off-hours DMs."""
        hour = self.now.hour
        messages_late = [
            "hey! catching this late, gonna reply properly in the morning 👋",
            "saw this — heading to bed but I'll get back to you first thing tmrw",
            "yo just saw this, let me circle back in the AM when I'm at my desk",
        ]
        messages_early = [
            "morning! just getting to my desk — saw your message, one sec",
            "hey just woke up, give me a min to catch up",
        ]
        messages_weekend = [
            "hey! it's the weekend so I might be a bit slower to respond but I'm here",
            "yo catching up on messages — weekend vibes but I got you",
        ]

        if self.is_weekend:
            return random.choice(messages_weekend)
        if hour < self.work_start:
            return random.choice(messages_early)
        return random.choice(messages_late)

    @property
    def status(self) -> dict:
        return {
            "is_online": self._is_online,
            "is_active_hours": self.is_active_hours(),
            "is_weekend": self.is_weekend,
            "current_time": self.now.strftime("%H:%M %Z"),
            "session_start": self._session_start.isoformat() if self._session_start else None,
        }
