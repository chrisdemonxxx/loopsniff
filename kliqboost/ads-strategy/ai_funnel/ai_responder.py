#!/usr/bin/env python3
"""AI Userbot Responder — Telethon MTProto layer for the TG Ads funnel.

This is the CLOSING layer — a real Telegram account (not a bot) that
DMs qualified leads with human-like AI responses powered by Ollama Cloud.

Architecture:
  1. Polls shared SQLite for new handoffs from qualification bot
  2. Sends opening DM to qualified leads
  3. Handles incoming replies with RAG-augmented LLM responses
  4. Applies rate limiting, typing simulation, and presence management

Integration:
  - Shared DB with qualification_bot.py (lead_db.py)
  - Uses existing RAG system at /home/cjs/kliqboost/rag
  - Uses existing BANT scorer from outreach module
  - LLM: Ollama Cloud (kimi-k2:1t) or local Qwen3.5 fallback

Usage:
    python ai_responder.py              # run daemon
    python ai_responder.py --auth       # authenticate (send OTP)
    python ai_responder.py --test       # connect, verify, exit
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import random
import signal
import sys
from pathlib import Path
from typing import Any, Dict

import aiohttp
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

from telethon import TelegramClient, events

import lead_db
from conversation_manager import ConversationManager, split_message
from rate_limiter import RateLimiter, ConversationThrottler
from presence_manager import PresenceManager
from system_prompts import get_system_prompt, STAGE_INSTRUCTIONS

log = logging.getLogger(__name__)
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# ═══════════════════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════════════════

API_ID = int(os.getenv("TELEGRAM_API_ID", "10840"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "33c45224029d59cb3ad0c16134215aeb")
PHONE = os.getenv("USERBOT_PHONE", "")
SESSION_NAME = os.getenv("USERBOT_SESSION_NAME", "tg_funnel_userbot")

DB_PATH = os.getenv("DB_PATH", str(Path(__file__).parent / "funnel_leads.db"))

# LLM
OLLAMA_URL = os.getenv("OLLAMA_URL", "https://ollama.com/v1/chat/completions")
OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY", "")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "kimi-k2:1t")

# Proxy (residential, required for safety)
PROXY_TYPE = os.getenv("PROXY_TYPE", "http")
PROXY_HOST = os.getenv("PROXY_HOST", "")
PROXY_PORT = int(os.getenv("PROXY_PORT", "10000"))
PROXY_USER = os.getenv("PROXY_USERNAME", "")
PROXY_PASS = os.getenv("PROXY_PASSWORD", "")

# Device fingerprint (iPhone 15 Pro Max, US)
DEVICE_MODEL = "iPhone 15 Pro Max"
SYSTEM_VERSION = "iOS 17.4"
APP_VERSION = "11.8.2"

# Admin notifications
ADMIN_BOT_TOKEN = os.getenv("ADMIN_BOT_TOKEN", "")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "")

# Limits
HOT_LEAD_THRESHOLD = 75
HANDOFF_POLL_INTERVAL = 30  # seconds


# ═══════════════════════════════════════════════════════════════════════════
# Ollama Cloud LLM Client
# ═══════════════════════════════════════════════════════════════════════════

async def ollama_chat(
    messages: list[dict],
    system_prompt: str = "",
    temperature: float = 0.7,
    max_tokens: int = 300,
) -> str:
    """Send a chat completion to Ollama Cloud (OpenAI-compatible API)."""
    sys_msg = {"role": "system", "content": system_prompt} if system_prompt else None
    full_messages = ([sys_msg] + messages) if sys_msg else messages

    payload = {
        "model": OLLAMA_MODEL,
        "messages": full_messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    headers = {
        "Authorization": f"Bearer {OLLAMA_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                OLLAMA_URL,
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=60),
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    log.error("LLM error (%d): %s", resp.status, body[:500])
                    return ""
                data = await resp.json()
                return data["choices"][0]["message"]["content"]
    except Exception as exc:
        log.error("LLM request failed: %s", exc)
        return ""


# ═══════════════════════════════════════════════════════════════════════════
# AI Funnel Responder
# ═══════════════════════════════════════════════════════════════════════════

class AIFunnelResponder:
    """AI-powered userbot for closing leads from the TG ads funnel."""

    def __init__(self):
        self.conv = ConversationManager()
        self.rate_limiter = RateLimiter()
        self.throttler = ConversationThrottler(cooldown=3.0)
        self.presence = PresenceManager()

    async def handle_incoming_dm(
        self, user_id: int, username: str, text: str,
    ) -> Dict[str, Any]:
        """Process an incoming DM and generate an AI response."""

        # Load history from DB if first interaction
        history = self.conv._history.get(user_id)
        if history is None:
            db_history = await lead_db.load_history(DB_PATH, user_id, limit=20)
            self.conv.load_history(user_id, db_history)

            # Restore stage from DB
            lead = await lead_db.get_lead(DB_PATH, user_id)
            if lead and lead.get("sales_stage"):
                self.conv.set_stage(user_id, lead["sales_stage"])

        # Detect language
        lang = self.conv.detect_and_store_language(user_id, text)

        # Record inbound message
        self.conv.add_message(user_id, "user", text)

        # BANT score
        bant = self.conv.score_conversation(user_id)

        # Advance stage
        stage = self.conv.advance_stage(user_id, bant)

        # Negative intent → stop
        if bant.get("negative"):
            log.info("Negative intent from @%s — pausing auto-reply", username)
            return {
                "response": "",
                "auto_respond": False,
                "bant": bant,
                "stage": stage,
            }

        # Hot lead logging
        if bant["total"] >= HOT_LEAD_THRESHOLD:
            log.info("🔥 HOT LEAD @%s (score=%d, stage=%s)", username, bant["total"], stage)
            await self._notify_admin(username, text, bant, stage)

        # Build LLM prompt
        system_prompt = get_system_prompt(
            language=lang,
            stage=stage,
            bant_score=bant["total"],
            bant_tier=bant.get("tier", "cold"),
        )
        llm_messages = self.conv.build_llm_messages(user_id, username, text)

        # Generate response
        ai_reply = await ollama_chat(llm_messages, system_prompt=system_prompt)
        if not ai_reply:
            ai_reply = "hey sorry was afk for a sec! what were you saying?"

        # Record outbound
        self.conv.add_message(user_id, "assistant", ai_reply)

        # Persist to DB
        await lead_db.save_message(
            DB_PATH, user_id, "inbound", text,
            source="userbot", bant_score=bant["total"], stage=stage,
        )
        await lead_db.save_message(
            DB_PATH, user_id, "outbound", ai_reply,
            source="userbot", bant_score=bant["total"], stage=stage,
        )

        # Update lead record
        extracted = bant.get("extracted", {})
        await lead_db.upsert_lead(
            DB_PATH, user_id,
            userbot_active=1,
            bant_score=bant["total"],
            bant_tier=bant.get("tier", "cold"),
            sales_stage=stage,
        )
        await lead_db.save_lead_memory(DB_PATH, user_id, {
            "platform_interest": str(extracted.get("platform", "")),
            "niche": str(extracted.get("niche", "")),
            "budget_range": str(extracted.get("budget", "")),
            "timeline": str(extracted.get("timeline", "")),
        })

        return {
            "response": ai_reply,
            "auto_respond": True,
            "bant": bant,
            "stage": stage,
        }

    async def generate_opener(self, user_id: int, username: str, summary: str) -> str:
        """Generate a natural opening message for a handoff lead."""
        system_prompt = get_system_prompt(
            language="en",
            stage="opener",
            bant_score=0,
            bant_tier="cold",
        )

        messages = [
            {
                "role": "user",
                "content": (
                    "[CONTEXT — this lead was just qualified by our bot]\n"
                    f"{summary}\n\n"
                    "Write a natural opening DM. Keep it short — 1-2 sentences. "
                    "Don't repeat what the bot already told them. "
                    "Reference that they were chatting with our bot if natural. "
                    "Make it feel like a real person following up."
                ),
            }
        ]

        reply = await ollama_chat(messages, system_prompt=system_prompt)
        return reply or f"hey @{username}! saw you were checking us out — what platform are you running on?"

    async def _notify_admin(
        self, username: str, message: str, bant: dict, stage: str,
    ) -> None:
        """Send hot lead alert to admin via Bot API."""
        if not ADMIN_BOT_TOKEN or not ADMIN_CHAT_ID:
            return

        breakdown = bant.get("breakdown", {})
        text = (
            f"🔥 <b>HOT LEAD (Funnel)</b>: @{username}\n"
            f"BANT Score: {bant['total']} ({bant.get('tier', '?')})\n"
            f"Stage: {stage.upper()}\n"
            f"Budget: {breakdown.get('budget', {}).get('value', '?')}\n"
            f"Platform: {breakdown.get('platform', {}).get('value', '?')}\n"
            f"───────────────\n"
            f"Last message: {message[:500]}"
        )

        url = f"https://api.telegram.org/bot{ADMIN_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": ADMIN_CHAT_ID, "text": text, "parse_mode": "HTML"}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url, json=payload, timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status == 200:
                        log.info("Admin notified about hot lead @%s", username)
                    else:
                        body = await resp.text()
                        log.warning("Admin notify failed (%d): %s", resp.status, body)
        except Exception as exc:
            log.error("Failed to notify admin: %s", exc)


# ═══════════════════════════════════════════════════════════════════════════
# Telethon Client Setup
# ═══════════════════════════════════════════════════════════════════════════

def _build_proxy() -> dict | None:
    """Build proxy config from env vars."""
    if not PROXY_HOST:
        return None
    return {
        "proxy_type": PROXY_TYPE,
        "addr": PROXY_HOST,
        "port": PROXY_PORT,
        "username": PROXY_USER,
        "password": PROXY_PASS,
    }


def _build_client() -> TelegramClient:
    """Create a Telethon client with device fingerprint and proxy."""
    session_dir = Path(__file__).parent / "sessions"
    session_dir.mkdir(parents=True, exist_ok=True)
    session_path = str(session_dir / SESSION_NAME)

    proxy = _build_proxy()
    return TelegramClient(
        session_path,
        API_ID,
        API_HASH,
        proxy=proxy,
        device_model=DEVICE_MODEL,
        system_version=SYSTEM_VERSION,
        app_version=APP_VERSION,
        lang_code="en",
        system_lang_code="en-US",
    )


# ═══════════════════════════════════════════════════════════════════════════
# Authentication
# ═══════════════════════════════════════════════════════════════════════════

async def authenticate() -> None:
    """Interactive authentication — sends OTP to phone."""
    client = _build_client()
    try:
        await client.connect()
        if await client.is_user_authorized():
            me = await client.get_me()
            log.info("Already authorised as %s (id=%s)", me.first_name, me.id)
            return

        if not PHONE:
            log.error("USERBOT_PHONE not set — cannot authenticate")
            return

        log.info("Sending login code to %s...", PHONE)
        await client.send_code_request(PHONE)
        code = input(f"Enter the code sent to {PHONE}: ").strip()
        await client.sign_in(PHONE, code)

        me = await client.get_me()
        log.info("✅ Authenticated as %s (id=%s)", me.first_name, me.id)
    finally:
        await client.disconnect()


# ═══════════════════════════════════════════════════════════════════════════
# Main Daemon
# ═══════════════════════════════════════════════════════════════════════════

async def main(test: bool = False) -> None:
    await lead_db.init_db(DB_PATH)

    client = _build_client()
    responder = AIFunnelResponder()

    await client.connect()
    if not await client.is_user_authorized():
        log.error("Session not authorised. Run with --auth first.")
        await client.disconnect()
        return

    me = await client.get_me()
    log.info("✅ Connected as %s (@%s, id=%s)", me.first_name, me.username, me.id)

    if test:
        log.info("Test mode — verifying connections...")
        log.info("RAG: %s", responder.conv.stats)
        log.info("Rate limiter: %s", responder.rate_limiter.stats)
        log.info("Presence: %s", responder.presence.status)
        log.info("Test complete — disconnecting")
        await client.disconnect()
        return

    # ── Register inbound DM handler ──────────────────────────────────────

    @client.on(events.NewMessage(incoming=True))
    async def _on_message(event):
        sender = await event.get_sender()
        if sender is None or getattr(sender, "bot", False):
            return

        username = getattr(sender, "username", None)
        if username:
            username = username.lower()
        else:
            username = f"id_{sender.id}"

        text = event.message.text or ""
        if not text.strip():
            return

        log.info("📩 DM from @%s: %s", username, text[:120])

        # Check presence
        if not responder.presence.should_respond():
            away_msg = responder.presence.get_away_message()
            log.info("Outside hours — sending away message to @%s", username)
            delay = random.uniform(30, 120)
            await asyncio.sleep(delay)
            await client.send_message(sender, away_msg)
            return

        # Rate limiting
        if not responder.rate_limiter.can_send():
            wait = responder.rate_limiter.time_until_available()
            log.warning("Rate limited — @%s must wait %.0fs", username, wait)
            return

        # Conversation throttle (wait if they're still typing)
        await responder.throttler.wait_for_user(sender.id)

        try:
            result = await responder.handle_incoming_dm(sender.id, username, text)

            if result["auto_respond"] and result["response"]:
                # Split into multiple messages if needed
                chunks = split_message(result["response"])

                for i, chunk in enumerate(chunks):
                    # Human-like delay
                    await responder.rate_limiter.wait_before_reply(chunk)

                    # Send with typing action
                    async with client.action(sender, "typing"):
                        typing_time = responder.rate_limiter.typing_duration(chunk)
                        await asyncio.sleep(min(typing_time, 15))

                    await client.send_message(sender, chunk)

                    # Small pause between multi-messages
                    if i < len(chunks) - 1:
                        await asyncio.sleep(random.uniform(1.5, 4.0))

                responder.rate_limiter.record_send()

                log.info(
                    "✅ Replied to @%s (stage=%s, bant=%d, chunks=%d)",
                    username, result["stage"],
                    result["bant"].get("total", 0),
                    len(chunks),
                )

            elif not result["auto_respond"]:
                log.info("⏸ Skipped reply to @%s (negative intent)", username)

        except Exception as exc:
            log.error("Error handling DM from @%s: %s", username, exc, exc_info=True)

    # ── Handoff poller (picks up leads from qualification bot) ────────────

    async def _poll_handoffs():
        """Periodically check for new handoffs and initiate contact."""
        while True:
            try:
                handoffs = await lead_db.get_pending_handoffs(DB_PATH, limit=5)
                for h in handoffs:
                    if not responder.rate_limiter.can_send():
                        log.info("Rate limited — deferring handoff processing")
                        break

                    user_id = h["user_id"]
                    username = h.get("username", "")

                    log.info(
                        "📬 Processing handoff #%d for @%s (reason=%s, bant=%d)",
                        h["id"], username, h["reason"], h["bant_score"],
                    )

                    # Generate opener
                    opener = await responder.generate_opener(
                        user_id, username, h.get("bot_summary", ""),
                    )

                    # Wait for natural timing
                    delay = random.uniform(60, 300)  # 1-5 min after bot handoff
                    log.debug("Waiting %.0fs before opening DM to @%s", delay, username)
                    await asyncio.sleep(delay)

                    # Send DM
                    try:
                        target = username if username and not username.startswith("id_") else user_id
                        await client.send_message(target, opener)
                        log.info("📤 Opener sent to @%s: %s", username, opener[:80])

                        # Record
                        await lead_db.save_message(
                            DB_PATH, user_id, "outbound", opener,
                            source="userbot", stage="opener",
                        )
                        await lead_db.mark_handoff_picked(DB_PATH, h["id"])
                        await lead_db.upsert_lead(DB_PATH, user_id, userbot_active=1)
                        responder.rate_limiter.record_send()

                    except Exception as exc:
                        log.error("Failed to DM @%s: %s", username, exc)

            except Exception as exc:
                log.error("Handoff polling error: %s", exc)

            await asyncio.sleep(HANDOFF_POLL_INTERVAL)

    # Start handoff poller as background task
    asyncio.create_task(_poll_handoffs())

    # Start presence cycling
    asyncio.create_task(responder.presence.simulate_online_cycle(client))

    # Print status
    log.info(
        "🤖 AI Funnel Responder LIVE\n"
        "   Account: %s (@%s)\n"
        "   LLM: %s (%s)\n"
        "   RAG: %s\n"
        "   Rate limits: %s\n"
        "   DB: %s",
        me.first_name, me.username,
        OLLAMA_MODEL, OLLAMA_URL,
        responder.conv.stats,
        responder.rate_limiter.stats,
        DB_PATH,
    )

    # Keep alive
    stop_event = asyncio.Event()

    def _signal_handler():
        log.info("Shutdown signal received")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _signal_handler)

    await stop_event.wait()

    log.info("Disconnecting...")
    await client.disconnect()
    log.info("AI Funnel Responder stopped")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Funnel Userbot Responder")
    parser.add_argument("--auth", action="store_true", help="Authenticate session (send OTP)")
    parser.add_argument("--test", action="store_true", help="Connect, verify, exit")
    args = parser.parse_args()

    if args.auth:
        asyncio.run(authenticate())
    else:
        asyncio.run(main(test=args.test))
