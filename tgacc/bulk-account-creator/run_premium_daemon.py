#!/usr/bin/env python3
"""Unified Premium TG Daemon — outreach + AI auto-responder in one process.

Maintains a SINGLE persistent connection to the premium TG account and handles:
  1. Outreach DMs via sandwich pattern (organic → DMs → organic)
  2. AI auto-responder for incoming messages (RAG + Ollama Cloud)
  3. Organic human-mimicking activity between sessions
  4. SpamBot health checks

Why unified?  Telegram kills older sessions when a new connection opens with
the same .session file.  Running outreach and autoresponder as separate
processes causes "Cannot send requests while disconnected" errors.

Usage:
  python run_premium_daemon.py                # continuous daemon (outreach + responder)
  python run_premium_daemon.py --once morning # run one outreach session then exit
  python run_premium_daemon.py --status       # show stats
  python run_premium_daemon.py --test         # test 2 DMs + AI responder, then exit
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import signal
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger
from telethon import TelegramClient, events, functions, types
from telethon.errors import (
    FloodWaitError,
    PeerFloodError,
    ChannelPrivateError,
    ChatWriteForbiddenError,
    UserBannedInChannelError,
    UserPrivacyRestrictedError,
    UsernameNotOccupiedError,
    UsernameInvalidError,
    InputUserDeactivatedError,
    AuthKeyUnregisteredError,
    UserDeactivatedBanError,
    SlowModeWaitError,
)

load_dotenv()

import python_socks

# ── Wire up sibling projects ────────────────────────────────────────────────
sys.path.insert(0, "/home/cjs/tgacc/adflux-rag")
sys.path.insert(0, "/home/cjs/tgacc/bulk-account-creator")

from outreach import config as outreach_config
from outreach import db
from outreach.models import Lead
from outreach.ai_responder import AIResponder
from outreach.escalation import EscalationManager

# ── Paths ────────────────────────────────────────────────────────────────────
DB_PATH = Path(__file__).parent / "outreach" / "data" / "outreach.db"
DEVICE_PROFILES_PATH = Path(__file__).parent / "outreach" / "data" / "device_profiles.json"
LOG_PATH = Path(__file__).parent / "outreach" / "data" / "premium_daemon.log"

logger.add(str(LOG_PATH), rotation="5 MB", retention="7 days", level="DEBUG")

# ── Premium Account Config ──────────────────────────────────────────────────
PREMIUM_PHONE = "16562292535"
PREMIUM_SESSION = "outreach/sessions/telethon/tg_16562292535"

# ── Escalation Schedule (DMs per session by week) ───────────────────────────
ESCALATION = {
    1: {"morning": 5,  "afternoon": 8,  "evening": 5},    # 18/day
    2: {"morning": 10, "afternoon": 15, "evening": 10},   # 35/day
    3: {"morning": 15, "afternoon": 20, "evening": 15},   # 50/day
    4: {"morning": 20, "afternoon": 30, "evening": 20},   # 70/day
}

# ── Outreach session windows (hour ranges in UTC) ───────────────────────────
SESSION_WINDOWS = {
    "morning":   (11, 14),   # 11:00-14:00 UTC
    "afternoon": (17, 20),   # 17:00-20:00 UTC
    "evening":   (23, 2),    # 23:00-02:00 UTC (wraps midnight)
}

# ── Organic Activity Pools ──────────────────────────────────────────────────
CASUAL_GROUP_MESSAGES = [
    "Thanks for sharing! 🙌", "Really appreciate this breakdown",
    "This is gold, saved it 💾", "Super helpful, thanks!",
    "Great content as always 👏", "Appreciate the detail here",
    "Has anyone tried this approach?", "Interesting, what was the result?",
    "Can you elaborate on that?", "Anyone else experiencing this?",
    "Totally agree with this take", "Good point, but also consider...",
    "Keep up the great content 🔥", "This community is amazing",
    "Solid advice right here", "Quality content 👌",
    "Facts 💯", "Nice one 👏", "Interesting 🤔", "Good point!",
    "Very true", "Agreed 👍", "Makes sense",
    "Bookmarking this for later", "Love this perspective",
    "Following this thread 📌", "Saving this conversation",
    "This reminds me of a similar discussion in another group",
    "One of the better groups I've joined lately",
]

REACTION_EMOJIS = ["👍", "🔥", "❤️", "👏", "💯", "🤝", "⚡", "😂", "🤔", "👀"]

SEARCH_TOPICS = [
    "crypto news", "digital marketing", "ad accounts",
    "media buying", "affiliate marketing", "google ads tips",
    "facebook ads", "programmatic", "performance marketing",
    "saas marketing", "growth hacking", "conversion optimization",
]

# ── Personalized DM Templates ───────────────────────────────────────────────
DM_TEMPLATES = [
    "Hey {name} 👋 saw you around some marketing groups. We help media buyers get whitelisted ad accounts that don't get banned. Figured it might be useful for you — lmk if you wanna chat!",
    "Yo {name}, noticed you're into the ad game. Quick q — you ever deal with ad account bans? We might have exactly what you need 🤙",
    "Hey {name}! Came across your profile and thought we might be a good fit. We set up whitelisted ad accounts (Google, FB, Bing) — the ones that actually stick. Interested?",
    "What's up {name} — I'm Roger from AdFlux. We help advertisers stop losing accounts to bans. If you run paid traffic, happy to show you what we've got 🔥",
    "{name} hey! Quick one — do you run Google or Facebook ads? We've got whitelisted agency accounts that won't get shut down. Hit me up if you wanna know more",
    "Hey {name} 👊 saw we're in some of the same circles. I help media buyers get reliable ad accounts. No bans, replacements included. Worth a chat?",
    "Yo {name} — been seeing your name around. Quick pitch: we do whitelisted ad accounts for Google/FB/Bing that actually last. Want the details? 💪",
    "Hey {name}, hope you don't mind me reaching out! We're AdFlux Media — we help people who run ads get accounts that don't randomly get nuked. Sound familiar? 😅",
    "{name} what's good! I run an ad account service — whitelisted stuff for Google, Meta, Bing, Taboola. If you spend on ads and hate dealing with bans, we should talk 🤝",
    "Hey {name} — random but are you still active with paid advertising? Got something that might save you a lot of headaches with account bans 👀",
    "Hi {name}! I'm Roger with AdFlux Media. We specialize in whitelisted ad accounts — Google, Facebook, Bing, Taboola. No bans, free replacements. Worth 2 min of your time? 🙏",
    "{name} — quick one. We set up ad accounts that don't get banned. Google, FB, Bing. If you're tired of the ban cycle, lmk and I'll break it down for you real quick",
    "Hey {name} ✌️ we help advertisers with whitelisted accounts — the kind that actually stay up. Running any paid traffic rn?",
    "Yo {name}! Saw your profile and figured you might need reliable ad accounts. We do whitelisted setups with free replacements. Want to hear more?",
    "Hey {name} — I'll keep it short. We do whitelisted ad accounts (Google/FB/Bing/Taboola). If ad bans are killing your ROI, we're the fix. Wanna chat? 🤙",
    "{name} hey 👋 do you deal with Google or Facebook ads? We've been helping media buyers with whitelisted accounts that don't get flagged. Might be up your alley",
    "Hi {name}, this is Roger from AdFlux. We provide whitelisted ad accounts for all major platforms. If you're spending on ads and tired of bans, we should connect 💯",
    "Hey {name}! Not sure if this is relevant for you but — we help advertisers with accounts that don't get banned. Google, FB, the whole stack. Worth checking out?",
    "{name} what's up! I'm in the ad account space — we do whitelisted setups that actually survive. If you're a media buyer or run paid traffic, hmu 🔥",
    "Hey {name} — straight up, we solve the #1 problem for media buyers: account bans. Whitelisted accounts with free replacements across all platforms. Interested?",
]


# ═══════════════════════════════════════════════════════════════════════════
#  UTILITIES
# ═══════════════════════════════════════════════════════════════════════════

def build_proxy(tag: str = "pm01") -> tuple:
    host = os.getenv("PROXY_SELLER_HOST", os.getenv("PROXY_HOST", "res.proxy-seller.com"))
    port = int(os.getenv("PROXY_SELLER_PORT", os.getenv("PROXY_PORT", "10000")))
    user = os.getenv("PROXY_SELLER_USER", os.getenv("PROXY_USER", ""))
    passwd = os.getenv("PROXY_SELLER_PASS", os.getenv("PROXY_PASS", ""))
    sticky = f"{user}_c_US_s_{tag}_ttl_1440m"
    return (python_socks.ProxyType.SOCKS5, host, port, True, sticky, passwd)


def get_device_profile() -> dict:
    try:
        with open(DEVICE_PROFILES_PATH) as f:
            profiles = json.load(f)
        return profiles.get(f"tg_{PREMIUM_PHONE}", {})
    except Exception:
        return {}


def gaussian_delay(base: float, sigma: float, minimum: float = 5.0) -> float:
    return max(minimum, random.gauss(base, sigma))


async def typing_simulation(client, entity, message_len: int):
    typing_time = min(message_len * 0.12 + random.uniform(0, 3), 15)
    try:
        async with client.action(entity, "typing"):
            await asyncio.sleep(typing_time)
    except Exception:
        await asyncio.sleep(typing_time)


def get_personalized_dm(name: str) -> str:
    template = random.choice(DM_TEMPLATES)
    clean_name = name.strip()
    if len(clean_name) > 20:
        clean_name = clean_name.split()[0] if clean_name.split() else clean_name[:15]
    return template.format(name=clean_name)


def get_dm_quota(session_type: str) -> int:
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    days = conn.execute(
        "SELECT COUNT(DISTINCT session_date) FROM premium_outreach_log WHERE phone=?",
        (PREMIUM_PHONE,)
    ).fetchone()[0] or 0
    conn.close()
    week = min((days // 7) + 1, 4)
    return ESCALATION.get(week, ESCALATION[4]).get(session_type, 10)


# ═══════════════════════════════════════════════════════════════════════════
#  ORGANIC ACTIVITY (human mimicry)
# ═══════════════════════════════════════════════════════════════════════════

async def organic_read_messages(client, count: int = 5) -> int:
    done = 0
    try:
        dialogs = await client.get_dialogs(limit=15)
        groups = [d for d in dialogs if d.is_group or d.is_channel]
        random.shuffle(groups)
        for g in groups[:count]:
            try:
                await client.get_messages(g, limit=random.randint(3, 8))
                done += 1
                await asyncio.sleep(random.uniform(2, 6))
            except Exception:
                pass
    except Exception:
        pass
    return done


async def organic_react(client, count: int = 3) -> int:
    done = 0
    try:
        dialogs = await client.get_dialogs(limit=15)
        groups = [d for d in dialogs if d.is_group]
        random.shuffle(groups)
        for g in groups[:count * 2]:
            try:
                msgs = await client.get_messages(g, limit=5)
                for msg in msgs:
                    if msg and msg.id and not msg.out:
                        emoji = random.choice(REACTION_EMOJIS)
                        await client(functions.messages.SendReactionRequest(
                            peer=g, msg_id=msg.id,
                            reaction=[types.ReactionEmoji(emoticon=emoji)]
                        ))
                        done += 1
                        await asyncio.sleep(random.uniform(2, 5))
                        if done >= count:
                            return done
                        break
            except Exception:
                pass
    except Exception:
        pass
    return done


async def organic_group_message(client) -> bool:
    try:
        dialogs = await client.get_dialogs(limit=20)
        groups = [d for d in dialogs if d.is_group]
        random.shuffle(groups)
        for g in groups[:5]:
            try:
                msg = random.choice(CASUAL_GROUP_MESSAGES)
                await client.send_message(g, msg)
                return True
            except Exception:
                continue
    except Exception:
        pass
    return False


async def organic_search(client) -> bool:
    try:
        topic = random.choice(SEARCH_TOPICS)
        await client(functions.contacts.SearchRequest(q=topic, limit=5))
        await asyncio.sleep(random.uniform(2, 4))
        return True
    except Exception:
        return False


async def organic_browse_profiles(client, count: int = 2) -> int:
    done = 0
    try:
        dialogs = await client.get_dialogs(limit=10)
        for d in dialogs[:count]:
            try:
                if d.entity and hasattr(d.entity, "id"):
                    await client.get_entity(d.entity.id)
                    done += 1
                    await asyncio.sleep(random.uniform(2, 5))
            except Exception:
                pass
    except Exception:
        pass
    return done


async def organic_forward(client) -> bool:
    try:
        dialogs = await client.get_dialogs(limit=15)
        groups = [d for d in dialogs if d.is_group or d.is_channel]
        random.shuffle(groups)
        for g in groups[:3]:
            try:
                msgs = await client.get_messages(g, limit=10)
                for msg in msgs:
                    if msg and msg.text and len(msg.text) > 50 and not msg.out:
                        await client.forward_messages("me", msg, g)
                        return True
            except Exception:
                continue
    except Exception:
        pass
    return False


async def check_spambot(client) -> str:
    try:
        spambot = await client.get_entity("SpamBot")
        await client.send_message(spambot, "/start")
        await asyncio.sleep(4)
        msgs = await client.get_messages(spambot, limit=3)
        for m in reversed(msgs):
            if m.text and m.sender_id != (await client.get_me()).id:
                text = m.text.lower()
                if "no limits" in text or "good news" in text or "free" in text:
                    return "clean"
                elif "limited" in text or "restrict" in text:
                    return "restricted"
                elif "blocked" in text or "frozen" in text:
                    return "blocked"
                return "unknown"
    except Exception as e:
        logger.debug("SpamBot check failed: {}", e)
    return "error"


async def run_organic_block(client, intensity: str = "medium") -> int:
    actions_done = 0
    if intensity == "light":
        plan = [("read", 3), ("react", 1)]
    elif intensity == "heavy":
        plan = [("read", 8), ("react", 4), ("group_msg", 1), ("search", 1),
                ("browse", 2), ("forward", 1)]
    else:
        plan = [("read", 5), ("react", 2), ("group_msg", 1), ("search", 1)]

    random.shuffle(plan)
    for action, count in plan:
        await asyncio.sleep(random.uniform(3, 10))
        try:
            if action == "read":
                actions_done += await organic_read_messages(client, count)
            elif action == "react":
                actions_done += await organic_react(client, count)
            elif action == "group_msg":
                if await organic_group_message(client):
                    actions_done += 1
            elif action == "search":
                if await organic_search(client):
                    actions_done += 1
            elif action == "browse":
                actions_done += await organic_browse_profiles(client, count)
            elif action == "forward":
                if await organic_forward(client):
                    actions_done += 1
        except Exception as e:
            logger.debug("Organic action {} failed: {}", action, e)
    return actions_done


# ═══════════════════════════════════════════════════════════════════════════
#  DM SENDING
# ═══════════════════════════════════════════════════════════════════════════

def get_pending_targets(limit: int = 50) -> list[dict]:
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute(
        "SELECT username, first_name FROM targets WHERE status='pending' ORDER BY RANDOM() LIMIT ?",
        (limit,)
    ).fetchall()]
    conn.close()
    return rows


def mark_target_messaged(username: str, phone: str, message: str):
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    conn.execute(
        "UPDATE targets SET status='messaged', messaged_at=datetime('now'), messaged_by=? WHERE username=?",
        (phone, username)
    )
    conn.commit()
    conn.close()


def mark_target_status(username: str, status: str):
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    conn.execute("UPDATE targets SET status=? WHERE username=?", (status, username))
    conn.commit()
    conn.close()


def log_session_result(phone, session_type, dms_sent, dms_failed,
                       organic_actions, flood_waits, spambot_status,
                       duration, targets_list=""):
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    conn.execute("""
        INSERT INTO premium_outreach_log 
        (phone, session_date, session_type, dms_sent, dms_failed, organic_actions,
         flood_waits, spambot_status, duration_seconds, targets_list)
        VALUES (?, date('now'), ?, ?, ?, ?, ?, ?, ?, ?)
    """, (phone, session_type, dms_sent, dms_failed, organic_actions,
          flood_waits, spambot_status, duration, targets_list))
    conn.commit()
    conn.close()


async def send_dm_batch(client, targets: list[dict], batch_size: int) -> dict:
    sent = 0
    failed = 0
    flood_hit = False
    targets_used = []

    for i, target in enumerate(targets[:batch_size]):
        username = target["username"]
        first_name = target["first_name"] or username
        message = get_personalized_dm(first_name)

        try:
            entity = await client.get_entity(username)
            await asyncio.sleep(random.uniform(1, 3))
            await typing_simulation(client, entity, len(message))
            await client.send_message(entity, message)
            sent += 1
            targets_used.append({"username": username, "status": "sent"})
            logger.info("✅ DM sent to @{} ({}/{})", username, i + 1, batch_size)
            mark_target_messaged(username, PREMIUM_PHONE, message)

        except FloodWaitError as e:
            logger.warning("⚠️ FloodWait {}s on @{}", e.seconds, username)
            if e.seconds > 30:
                logger.error("🛑 FloodWait >30s — STOPPING batch")
                flood_hit = True
                break
            else:
                await asyncio.sleep(e.seconds + random.uniform(5, 15))
                failed += 1
                targets_used.append({"username": username, "status": "flood_wait"})

        except PeerFloodError:
            logger.error("🛑 PeerFloodError — STOPPING immediately")
            flood_hit = True
            break

        except (UserPrivacyRestrictedError, ChatWriteForbiddenError):
            logger.info("🔒 @{} has privacy restrictions — skipping", username)
            mark_target_status(username, "blocked")
            targets_used.append({"username": username, "status": "privacy"})

        except (UsernameNotOccupiedError, UsernameInvalidError, InputUserDeactivatedError):
            logger.info("💀 @{} invalid/deactivated — marking dead", username)
            mark_target_status(username, "dead")
            targets_used.append({"username": username, "status": "dead"})

        except Exception as e:
            logger.warning("❌ DM to @{} failed: {}", username, str(e)[:80])
            failed += 1
            targets_used.append({"username": username, "status": f"error: {str(e)[:50]}"})

        if i < batch_size - 1 and not flood_hit:
            delay = gaussian_delay(45, 15, minimum=20)
            logger.debug("⏳ Inter-DM delay: {:.1f}s", delay)
            await asyncio.sleep(delay)

    return {"sent": sent, "failed": failed, "flood": flood_hit, "targets": targets_used}


# ═══════════════════════════════════════════════════════════════════════════
#  AI AUTO-RESPONDER HANDLER (inline — same client)
# ═══════════════════════════════════════════════════════════════════════════

def register_ai_responder(client: TelegramClient, ai: AIResponder):
    """Register incoming-message handler on the existing client."""

    @client.on(events.NewMessage(incoming=True))
    async def _on_incoming(event):
        sender = await event.get_sender()
        if sender is None or getattr(sender, "bot", False):
            return

        username = getattr(sender, "username", None)
        if username:
            username = username.lower()
        else:
            username = f"id_{sender.id}"
        sender_name = getattr(sender, "first_name", "") or username

        text = event.message.text or ""
        if not text.strip():
            return

        logger.info("📩 Incoming DM from @{} ({}): {}", username, sender_name, text[:120])

        # Ensure lead exists in DB
        lead = await db.get_lead_by_username(username)
        if lead is None:
            lead = Lead(
                username=username,
                source="inbound_dm",
                status="replied",
                language="en",
            )
            await db.add_lead(lead)
            lead = await db.get_lead_by_username(username)
            if lead is None:
                logger.error("Failed to create lead for @{}", username)
                return
            logger.info("Auto-created lead for inbound DM from @{}", username)

        # Log inbound
        from outreach.models import Message as MsgModel
        await db.add_message(MsgModel(
            lead_username=username,
            account_phone=PREMIUM_PHONE,
            direction="inbound",
            text=text,
            sent_at=datetime.utcnow(),
        ))
        await db.update_lead(
            username, status="replied",
            reply_count=lead.reply_count + 1,
        )

        # Generate AI response
        try:
            result = await ai.handle_reply(lead, text)

            if result["auto_respond"] and result["response"]:
                delay = random.uniform(5, 25)
                logger.debug("⏳ AI typing delay {:.0f}s for @{}", delay, username)
                await asyncio.sleep(delay)

                try:
                    await client.send_message(sender, result["response"])
                    logger.info(
                        "🤖 AI replied to @{} (stage={}, bant={})",
                        username, result["stage"], result["bant"].get("total", 0),
                    )
                    await db.add_message(MsgModel(
                        lead_username=username,
                        account_phone=PREMIUM_PHONE,
                        direction="outbound",
                        text=result["response"],
                        sent_at=datetime.utcnow(),
                        template_id="ai_auto",
                    ))
                except Exception as send_exc:
                    logger.error("Failed to send AI reply to @{}: {}", username, send_exc)

            elif not result["auto_respond"]:
                logger.info("AI opted out for @{} (negative intent)", username)

        except Exception as exc:
            logger.error("AI responder error for @{}: {}", username, exc)

    logger.info("🧠 AI auto-responder registered on client")


# ═══════════════════════════════════════════════════════════════════════════
#  OUTREACH SESSION (sandwich pattern)
# ═══════════════════════════════════════════════════════════════════════════

async def run_outreach_session(client, session_type: str, test_mode: bool = False):
    """Run one outreach session on an already-connected client."""
    start_time = time.time()
    dm_quota = 2 if test_mode else get_dm_quota(session_type)
    logger.info("🚀 Starting {} session — DM quota: {}{}", 
                session_type.upper(), dm_quota, " (TEST)" if test_mode else "")

    total_organic = 0
    total_sent = 0
    total_failed = 0
    total_floods = 0
    spambot = "skipped"

    # Phase 1: Opening organic (heavy)
    logger.info("📖 Phase 1: Opening organic activity...")
    total_organic += await run_organic_block(client, "heavy")
    await asyncio.sleep(random.uniform(10, 25))

    # Phase 2: First DM batch (40%)
    batch1_size = max(2, int(dm_quota * 0.4))
    targets = get_pending_targets(dm_quota + 20)

    if targets:
        logger.info("📨 Phase 2: Sending DM batch 1 ({} DMs)...", batch1_size)
        result1 = await send_dm_batch(client, targets[:batch1_size], batch1_size)
        total_sent += result1["sent"]
        total_failed += result1["failed"]
        if result1["flood"]:
            total_floods += 1
            logger.warning("⚠️ Flood in batch 1 — organic only from here")
    else:
        logger.warning("No pending targets!")
        result1 = {"sent": 0, "failed": 0, "flood": False, "targets": []}

    # Phase 3: Mid organic
    if not result1.get("flood"):
        logger.info("📖 Phase 3: Mid-session organic activity...")
        await asyncio.sleep(random.uniform(15, 40))
        total_organic += await run_organic_block(client, "medium")
        await asyncio.sleep(random.uniform(10, 25))

        # Phase 4: Second DM batch (remaining)
        batch2_size = dm_quota - total_sent
        if batch2_size > 0 and len(targets) > batch1_size:
            logger.info("📨 Phase 4: Sending DM batch 2 ({} DMs)...", batch2_size)
            result2 = await send_dm_batch(client, targets[batch1_size:], batch2_size)
            total_sent += result2["sent"]
            total_failed += result2["failed"]
            if result2["flood"]:
                total_floods += 1

    # Phase 5: Closing organic + SpamBot
    logger.info("📖 Phase 5: Closing organic activity...")
    await asyncio.sleep(random.uniform(10, 20))
    total_organic += await run_organic_block(client, "medium")

    # SpamBot check every 2-3 sessions
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    last_check = conn.execute(
        "SELECT MAX(session_date) FROM premium_outreach_log WHERE phone=? AND spambot_status != 'skipped'",
        (PREMIUM_PHONE,)
    ).fetchone()[0]
    sessions_since = 0
    if last_check:
        sessions_since = conn.execute(
            "SELECT COUNT(*) FROM premium_outreach_log WHERE phone=? AND session_date > ?",
            (PREMIUM_PHONE, last_check)
        ).fetchone()[0]
    conn.close()

    if sessions_since >= 2 or not last_check:
        logger.info("🤖 Checking @SpamBot...")
        spambot = await check_spambot(client)
        logger.info("SpamBot status: {}", spambot)
        if spambot == "restricted":
            logger.error("🛑 ACCOUNT RESTRICTED — pausing outreach!")

    duration = int(time.time() - start_time)
    log_session_result(PREMIUM_PHONE, session_type, total_sent, total_failed,
                       total_organic, total_floods, spambot, duration)

    logger.info("\n" + "=" * 50)
    logger.info("📊 {} SESSION SUMMARY", session_type.upper())
    logger.info("=" * 50)
    logger.info("  ✅ DMs sent: {}", total_sent)
    logger.info("  ❌ DMs failed: {}", total_failed)
    logger.info("  📖 Organic actions: {}", total_organic)
    logger.info("  ⚠️ Flood waits: {}", total_floods)
    logger.info("  🤖 SpamBot: {}", spambot)
    logger.info("  ⏱️ Duration: {}m {}s", duration // 60, duration % 60)
    logger.info("=" * 50)

    return {"sent": total_sent, "failed": total_failed, "floods": total_floods,
            "spambot": spambot}


# ═══════════════════════════════════════════════════════════════════════════
#  SESSION SCHEDULER (picks when to run outreach)
# ═══════════════════════════════════════════════════════════════════════════

def _current_session_type() -> str | None:
    """Return 'morning'/'afternoon'/'evening' if we're in a session window, else None."""
    now_utc = datetime.now(timezone.utc).hour
    for stype, (start, end) in SESSION_WINDOWS.items():
        if start <= end:
            if start <= now_utc < end:
                return stype
        else:  # wraps midnight
            if now_utc >= start or now_utc < end:
                return stype
    return None


def _already_ran_today(session_type: str) -> bool:
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    count = conn.execute(
        "SELECT COUNT(*) FROM premium_outreach_log WHERE phone=? AND session_date=date('now') AND session_type=?",
        (PREMIUM_PHONE, session_type)
    ).fetchone()[0]
    conn.close()
    return count > 0


# ═══════════════════════════════════════════════════════════════════════════
#  CONTINUOUS DAEMON
# ═══════════════════════════════════════════════════════════════════════════

async def run_daemon(test_mode: bool = False):
    """Main daemon loop: connect once, listen forever, run outreach on schedule."""
    await db.init_db()

    device = get_device_profile()
    proxy = build_proxy("pm01")

    client = TelegramClient(
        session=PREMIUM_SESSION,
        api_id=int(device.get("api_id", 2040)),
        api_hash=device.get("api_hash", "b18441a1ff607e10a989891a5462e627"),
        proxy=proxy,
        device_model=device.get("device_model", "iPhone 15 Pro"),
        system_version=device.get("system_version", "iOS 18.2"),
        app_version=device.get("app_version", "11.5.4"),
        lang_code=device.get("lang_code", "en"),
        system_lang_code=device.get("system_lang_code", "en-US"),
    )

    await client.connect()
    me = await client.get_me()
    if not me:
        logger.error("❌ Session invalid — exiting")
        return
    logger.info("✅ Connected as {} (@{}) | Premium: {}", me.first_name, me.username, me.premium)

    # Register AI auto-responder
    ai = AIResponder()
    register_ai_responder(client, ai)
    logger.info("🧠 AI brain active — RAG + Ollama Cloud ready")

    if test_mode:
        logger.info("=== TEST MODE ===")
        # Run a quick 2-DM outreach
        result = await run_outreach_session(client, "morning", test_mode=True)
        logger.info("Test complete. Sent: {}, Failed: {}", result["sent"], result["failed"])
        # Wait 30s for any incoming DMs to test auto-responder
        logger.info("Listening for incoming DMs for 60s to test AI responder...")
        await asyncio.sleep(60)
        await client.disconnect()
        return

    # Graceful shutdown
    stop_event = asyncio.Event()
    def _signal_handler():
        logger.info("Shutdown signal received")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _signal_handler)

    logger.info("🟢 Premium daemon LIVE — outreach + AI responder running")
    logger.info("   Session windows: morning(11-14 UTC), afternoon(17-20 UTC), evening(23-02 UTC)")

    # Main loop: check for outreach windows + idle organic activity + follow-up queue
    last_organic = time.time()
    organic_interval = random.uniform(1200, 2400)  # 20-40 min between idle organic

    while not stop_event.is_set():
        try:
            # ── Process follow-up queue (high priority) ──
            try:
                conn = sqlite3.connect(str(DB_PATH), timeout=30)
                pending = conn.execute(
                    "SELECT id, username, message FROM followup_queue WHERE status='pending' LIMIT 5"
                ).fetchall()
                conn.close()

                for fid, fusername, fmsg in pending:
                    try:
                        # Support both @username and numeric user IDs
                        try:
                            entity = await client.get_entity(int(fusername))
                        except (ValueError, TypeError):
                            entity = await client.get_entity(fusername)
                        await typing_simulation(client, entity, len(fmsg))
                        await client.send_message(entity, fmsg)
                        conn = sqlite3.connect(str(DB_PATH), timeout=30)
                        conn.execute("UPDATE followup_queue SET status='sent' WHERE id=?", (fid,))
                        conn.commit()
                        conn.close()
                        logger.info("📤 Follow-up sent to @{}", fusername)
                        await asyncio.sleep(random.uniform(10, 25))
                    except Exception as fe:
                        logger.error("Follow-up to @{} failed: {}", fusername, fe)
                        conn = sqlite3.connect(str(DB_PATH), timeout=30)
                        conn.execute("UPDATE followup_queue SET status='failed' WHERE id=?", (fid,))
                        conn.commit()
                        conn.close()
            except Exception:
                pass

            # ── Check if we're in an outreach window ──
            stype = _current_session_type()
            if stype and not _already_ran_today(stype):
                # Random jitter 0-10 min before starting
                jitter = random.randint(0, 600)
                logger.info("⏰ Outreach window '{}' active — starting in {}s", stype, jitter)
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=jitter)
                    break
                except asyncio.TimeoutError:
                    pass

                if not stop_event.is_set():
                    await run_outreach_session(client, stype)

            # Idle organic activity (human presence signals)
            if time.time() - last_organic > organic_interval:
                logger.info("🌿 Idle organic activity (human presence)...")
                await run_organic_block(client, "light")
                last_organic = time.time()
                organic_interval = random.uniform(1200, 2400)

            # Sleep 60s between checks (still listening for DMs via event handler)
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=60)
                break
            except asyncio.TimeoutError:
                pass

        except Exception as e:
            logger.error("Daemon loop error: {}", e)
            await asyncio.sleep(30)

    logger.info("Shutting down...")
    await client.disconnect()
    logger.info("Premium daemon stopped")


# ═══════════════════════════════════════════════════════════════════════════
#  STATUS DISPLAY
# ═══════════════════════════════════════════════════════════════════════════

def show_status():
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    cur = conn.cursor()

    cur.execute("""
        SELECT session_date, session_type, dms_sent, dms_failed, organic_actions, 
               flood_waits, spambot_status, duration_seconds
        FROM premium_outreach_log WHERE phone=?
        ORDER BY created_at DESC LIMIT 15
    """, (PREMIUM_PHONE,))
    sessions = cur.fetchall()

    cur.execute("""
        SELECT COALESCE(SUM(dms_sent),0), COALESCE(SUM(dms_failed),0), 
               COALESCE(SUM(organic_actions),0), COALESCE(SUM(flood_waits),0),
               COUNT(*)
        FROM premium_outreach_log WHERE phone=?
    """, (PREMIUM_PHONE,))
    totals = cur.fetchone()

    cur.execute("SELECT status, COUNT(*) FROM targets GROUP BY status")
    target_stats = dict(cur.fetchall())
    conn.close()

    print(f"\n📊 PREMIUM DAEMON STATUS — @Roger_Adflux (+{PREMIUM_PHONE})")
    print("=" * 60)
    dm_quota = get_dm_quota("afternoon")
    days = totals[4] if totals else 0
    week = min((days // 3) + 1, 4)
    print(f"  Current week: {week} | DM quota/session: {dm_quota}")
    print(f"  Total sessions: {totals[4]}")
    print(f"  Total DMs sent: {totals[0]} | Failed: {totals[1]}")
    print(f"  Total organic actions: {totals[2]}")
    print(f"  Total flood waits: {totals[3]}")

    print(f"\n🎯 Targets:")
    for status, count in sorted(target_stats.items()):
        print(f"  {status}: {count}")

    if sessions:
        print(f"\n📋 Recent sessions:")
        for s in sessions:
            print(f"  {s[0]} {s[1]:>10} | sent:{s[2]} fail:{s[3]} organic:{s[4]} floods:{s[5]} spam:{s[6]} {s[7]//60}m")


# ═══════════════════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Premium TG Daemon — outreach + AI responder")
    parser.add_argument("--once", choices=["morning", "afternoon", "evening"],
                        help="Run one outreach session then exit")
    parser.add_argument("--status", action="store_true", help="Show status")
    parser.add_argument("--test", action="store_true", help="Test mode (2 DMs + AI)")
    args = parser.parse_args()

    if args.status:
        show_status()
    elif args.once:
        async def _run_once():
            await db.init_db()
            device = get_device_profile()
            proxy = build_proxy("pm01")
            client = TelegramClient(
                session=PREMIUM_SESSION,
                api_id=int(device.get("api_id", 2040)),
                api_hash=device.get("api_hash", "b18441a1ff607e10a989891a5462e627"),
                proxy=proxy,
                device_model=device.get("device_model", "iPhone 15 Pro"),
                system_version=device.get("system_version", "iOS 18.2"),
                app_version=device.get("app_version", "11.5.4"),
                lang_code=device.get("lang_code", "en"),
                system_lang_code=device.get("system_lang_code", "en-US"),
            )
            await client.connect()
            me = await client.get_me()
            if not me:
                logger.error("Session invalid")
                return
            logger.info("Connected as {} (@{})", me.first_name, me.username)
            ai = AIResponder()
            register_ai_responder(client, ai)
            await run_outreach_session(client, args.once)
            await client.disconnect()
        asyncio.run(_run_once())
    elif args.test:
        asyncio.run(run_daemon(test_mode=True))
    else:
        asyncio.run(run_daemon())
