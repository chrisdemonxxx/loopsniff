"""Incoming reply handler with BANT scoring stub."""

from __future__ import annotations

import logging
import re
from typing import Optional

import aiohttp

from . import config, db
from .models import Lead

log = logging.getLogger(__name__)


class ResponseHandler:
    """Score inbound replies and route hot leads to admin."""

    BANT_KEYWORDS: dict[str, list[str]] = {
        "budget_high": [
            "$10k", "$50k", "10k", "50k", "unlimited", "scale", "big budget",
            "$100k", "100k",
        ],
        "budget_medium": [
            "$1k", "$5k", "1k", "5k", "moderate", "$2k", "$3k",
        ],
        "urgency_high": [
            "asap", "urgent", "today", "now", "immediately", "ready",
            "right now", "this moment",
        ],
        "urgency_medium": [
            "this week", "soon", "interested", "next week",
        ],
        "positive": [
            "yes", "interested", "tell me more", "how much", "pricing",
            "details", "sure", "let's talk", "dm me", "send info",
            "sounds good", "go ahead",
        ],
        "negative": [
            "no", "not interested", "stop", "spam", "block", "unsubscribe",
            "don't message", "leave me alone", "reported",
        ],
    }

    def _score(self, text: str) -> dict:
        """Compute a simple BANT score from keyword matching."""
        lower = text.lower()
        result = {
            "budget": 0,
            "urgency": 0,
            "intent": "neutral",
            "matched_keywords": [],
            "total_score": 0,
        }

        for kw in self.BANT_KEYWORDS["budget_high"]:
            if kw in lower:
                result["budget"] = 3
                result["matched_keywords"].append(kw)
        if result["budget"] == 0:
            for kw in self.BANT_KEYWORDS["budget_medium"]:
                if kw in lower:
                    result["budget"] = 2
                    result["matched_keywords"].append(kw)

        for kw in self.BANT_KEYWORDS["urgency_high"]:
            if kw in lower:
                result["urgency"] = 3
                result["matched_keywords"].append(kw)
        if result["urgency"] == 0:
            for kw in self.BANT_KEYWORDS["urgency_medium"]:
                if kw in lower:
                    result["urgency"] = 2
                    result["matched_keywords"].append(kw)

        for kw in self.BANT_KEYWORDS["negative"]:
            if kw in lower:
                result["intent"] = "negative"
                result["matched_keywords"].append(kw)
                break

        if result["intent"] != "negative":
            for kw in self.BANT_KEYWORDS["positive"]:
                if kw in lower:
                    result["intent"] = "positive"
                    result["matched_keywords"].append(kw)
                    break

        result["total_score"] = result["budget"] + result["urgency"]
        if result["intent"] == "positive":
            result["total_score"] += 2
        elif result["intent"] == "negative":
            result["total_score"] = -5

        return result

    async def process_reply(self, lead: Lead, message_text: str) -> dict:
        """Score a reply and update the lead accordingly."""
        score = self._score(message_text)
        log.info("BANT score for @%s: %s", lead.username, score)

        if score["intent"] == "negative":
            await db.update_lead(lead.username, status="dead", bant_score=score["total_score"])
            log.info("Lead @%s marked dead (negative reply)", lead.username)
        elif score["total_score"] >= 5:
            await db.update_lead(lead.username, status="hot", bant_score=score["total_score"])
            log.info("🔥 HOT LEAD: @%s (score=%d)", lead.username, score["total_score"])
            await self.notify_admin(lead, message_text, score)
        elif score["intent"] == "positive":
            await db.update_lead(lead.username, status="qualified", bant_score=score["total_score"])
        else:
            await db.update_lead(lead.username, bant_score=score["total_score"])

        return score

    async def notify_admin(self, lead: Lead, message: str, score: dict) -> None:
        """Send a lead card to the admin Telegram bot."""
        text = (
            f"🔥 HOT LEAD: @{lead.username}\n"
            f"Source: {lead.source}\n"
            f"Language: {lead.language}\n"
            f"BANT Score: {score['total_score']}\n"
            f"Budget: {score['budget']}  Urgency: {score['urgency']}\n"
            f"Intent: {score['intent']}\n"
            f"Keywords: {', '.join(score['matched_keywords'])}\n"
            f"───────────────\n"
            f"Message: {message[:500]}"
        )
        url = f"https://api.telegram.org/bot{config.ADMIN_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": config.ADMIN_CHAT_ID, "text": text}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        log.info("Admin notified about hot lead @%s", lead.username)
                    else:
                        body = await resp.text()
                        log.warning("Admin notify failed (%d): %s", resp.status, body)
        except Exception as exc:
            log.error("Failed to notify admin: %s", exc)
