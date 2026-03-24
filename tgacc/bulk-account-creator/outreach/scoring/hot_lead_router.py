"""Route hot leads to admin DM and the private AdFlux channel."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import aiohttp

log = logging.getLogger(__name__)

BOT_TOKEN: str = os.getenv(
    "ADFLUX_BOT_TOKEN",
    "8707230750:AAHkEFpQIxk1H9JsHu8IQ6jagWp8Qlh8-G4",
)
ADMIN_CHAT_ID: int = int(os.getenv("ADFLUX_ADMIN_CHAT_ID", "8365840792"))

_API_BASE = "https://api.telegram.org/bot{token}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


# ---------------------------------------------------------------------------
# Lead-card formatting
# ---------------------------------------------------------------------------

def _format_lead_card(lead: Dict[str, Any], score: Dict[str, Any], conversation: Optional[List[str]] = None) -> str:
    """Build a Telegram-friendly lead card (MarkdownV2-safe plain text)."""
    breakdown = score.get("breakdown", {})
    total = score.get("total", 0)
    tier = score.get("tier", "unknown")

    username = lead.get("username", "unknown")
    source = lead.get("source", "DM outreach")

    budget_val = breakdown.get("budget", {}).get("value", "unknown")
    platform_val = breakdown.get("platform", {}).get("value", "unknown")
    niche_val = breakdown.get("niche", {}).get("value", "unknown")
    timeline_val = breakdown.get("timeline", {}).get("value", "unknown")

    lines = [
        "🔥 HOT LEAD ALERT",
        "",
        f"👤 @{username}",
        f"📊 BANT Score: {total}/100 ({tier})",
        f"💰 Budget: {budget_val}",
        f"🎯 Platform: {platform_val}",
        f"🏷 Niche: {niche_val}",
        f"⏰ Timeline: {timeline_val}",
        f"📝 Source: {source}",
    ]

    if conversation:
        recent = conversation[-3:]
        lines.append("")
        lines.append("💬 Recent messages:")
        for msg in recent:
            short = (msg[:120] + "…") if len(msg) > 120 else msg
            lines.append(f"  ▸ {short}")

    lines.append("")
    lines.append(f"🕐 {_now_iso()}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# HotLeadRouter
# ---------------------------------------------------------------------------

class HotLeadRouter:
    """Route qualified leads to admin and private channel."""

    def __init__(
        self,
        bot_token: str = BOT_TOKEN,
        admin_chat_id: int = ADMIN_CHAT_ID,
        channel_id: Optional[int] = None,
    ):
        self.bot_token = bot_token
        self.admin_chat_id = admin_chat_id
        self.channel_id = channel_id
        self._api = _API_BASE.format(token=self.bot_token)

    # ------------------------------------------------------------------
    # Main routing entry point
    # ------------------------------------------------------------------

    async def route_hot_lead(
        self,
        lead: Dict[str, Any],
        score: Dict[str, Any],
        conversation: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Route a hot lead.

        1. Send detailed lead card to admin via bot.
        2. Forward to private channel (if configured).
        3. Return routing result.
        """
        card_text = _format_lead_card(lead, score, conversation)

        admin_ok = await self.send_lead_card(self.admin_chat_id, card_text)

        channel_ok = False
        if self.channel_id:
            channel_ok = await self.forward_to_channel(self.channel_id, card_text)

        log.info(
            "Routed hot lead @%s — admin=%s channel=%s",
            lead.get("username", "?"),
            admin_ok,
            channel_ok,
        )
        return {
            "routed": True,
            "admin_notified": admin_ok,
            "channel_posted": channel_ok,
            "score": score.get("total", 0),
        }

    # ------------------------------------------------------------------
    # Telegram helpers
    # ------------------------------------------------------------------

    async def send_lead_card(self, chat_id: int, text: str) -> bool:
        """Send a formatted lead card via Bot API ``sendMessage``."""
        url = f"{self._api}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }
        return await self._post(url, payload)

    async def forward_to_channel(self, channel_id: int, card_text: str) -> bool:
        """Forward lead card to the private channel."""
        url = f"{self._api}/sendMessage"
        payload = {
            "chat_id": channel_id,
            "text": card_text,
            "disable_web_page_preview": True,
        }
        return await self._post(url, payload)

    async def daily_digest(self, hot_leads: List[Dict[str, Any]], stats: Optional[Dict[str, Any]] = None) -> bool:
        """Send a daily summary of new hot leads to admin."""
        lines = [
            "📋 DAILY HOT LEAD DIGEST",
            f"🕐 {_now_iso()}",
            "",
        ]

        if stats:
            lines.append(f"📨 DMs sent: {stats.get('dms_sent', 0)}")
            lines.append(f"💬 Replies: {stats.get('replies', 0)}")
            lines.append(f"🔥 Hot leads: {stats.get('hot_leads', 0)}")
            lines.append(f"📈 Conversion: {stats.get('conversion_rate', 0)}%")
            lines.append("")

        if hot_leads:
            lines.append(f"🔥 {len(hot_leads)} new hot lead(s):")
            for ld in hot_leads[:10]:
                username = ld.get("username", "?")
                score = ld.get("score", 0)
                lines.append(f"  • @{username} — score {score}")
        else:
            lines.append("No new hot leads today.")

        text = "\n".join(lines)
        return await self.send_lead_card(self.admin_chat_id, text)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _post(self, url: str, payload: Dict[str, Any]) -> bool:
        """Fire-and-forget POST to Telegram Bot API."""
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
