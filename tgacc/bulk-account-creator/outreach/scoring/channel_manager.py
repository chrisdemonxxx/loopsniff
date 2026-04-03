"""Manage the private AdFlux Media leads channel.

The channel is created manually by the admin; this module handles
posting lead cards, daily summaries, and pinning important messages.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import aiohttp

log = logging.getLogger(__name__)

BOT_TOKEN: str = os.getenv(
    "ADFLUX_BOT_TOKEN",
    "",
)

_API_BASE = "https://api.telegram.org/bot{token}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


class ChannelManager:
    """Manage the private AdFlux Media leads channel."""

    def __init__(
        self,
        channel_id: Optional[int] = -1003751157980,
        bot_token: str = BOT_TOKEN,
    ):
        self.channel_id = channel_id
        self.bot_token = bot_token
        self._api = _API_BASE.format(token=self.bot_token)

    # ------------------------------------------------------------------
    # Post lead card
    # ------------------------------------------------------------------

    async def post_lead(self, lead: Dict[str, Any], score: Dict[str, Any]) -> Optional[int]:
        """Post a lead card to the channel. Returns message_id or None."""
        if not self.channel_id:
            log.warning("Channel ID not configured — skipping post_lead")
            return None

        from .hot_lead_router import _format_lead_card
        text = _format_lead_card(lead, score)
        return await self._send(text)

    # ------------------------------------------------------------------
    # Daily summary
    # ------------------------------------------------------------------

    async def post_daily_summary(self, stats: Dict[str, Any]) -> Optional[int]:
        """Post daily outreach summary to the channel.

        Expected *stats* keys: ``dms_sent``, ``replies``, ``hot_leads``,
        ``conversion_rate``, ``new_customers``.
        """
        if not self.channel_id:
            log.warning("Channel ID not configured — skipping daily summary")
            return None

        lines = [
            "📊 DAILY OUTREACH SUMMARY",
            f"🕐 {_now_iso()}",
            "",
            f"📨 DMs sent: {stats.get('dms_sent', 0)}",
            f"💬 Replies received: {stats.get('replies', 0)}",
            f"🔥 Hot leads: {stats.get('hot_leads', 0)}",
            f"🤝 New customers: {stats.get('new_customers', 0)}",
            f"📈 Reply rate: {stats.get('conversion_rate', 0)}%",
            "",
            "— AdFlux Outreach Engine",
        ]
        return await self._send("\n".join(lines))

    # ------------------------------------------------------------------
    # Pin message
    # ------------------------------------------------------------------

    async def pin_message(self, message_id: int) -> bool:
        """Pin an important lead or announcement in the channel."""
        if not self.channel_id:
            log.warning("Channel ID not configured — skipping pin")
            return False

        url = f"{self._api}/pinChatMessage"
        payload = {
            "chat_id": self.channel_id,
            "message_id": message_id,
            "disable_notification": False,
        }
        return await self._post(url, payload)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _send(self, text: str) -> Optional[int]:
        """Send *text* to the channel and return the message_id."""
        url = f"{self._api}/sendMessage"
        payload = {
            "chat_id": self.channel_id,
            "text": text,
            "disable_web_page_preview": True,
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        msg_id = data.get("result", {}).get("message_id")
                        log.info("Posted to channel %s — message_id=%s", self.channel_id, msg_id)
                        return msg_id
                    body = await resp.text()
                    log.warning("sendMessage to channel returned %d: %s", resp.status, body[:200])
                    return None
        except Exception:
            log.exception("Failed to send to channel %s", self.channel_id)
            return None

    async def _post(self, url: str, payload: Dict[str, Any]) -> bool:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status == 200:
                        return True
                    body = await resp.text()
                    log.warning("Telegram API %s returned %d: %s", url, resp.status, body[:200])
                    return False
        except Exception:
            log.exception("Failed to POST %s", url)
            return False
