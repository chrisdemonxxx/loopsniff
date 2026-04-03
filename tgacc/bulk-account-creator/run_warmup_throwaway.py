"""Enhanced warm-up engine for throwaway TData sessions (v2).

Based on comprehensive research: 14-day protocol with 3 sessions/day
(morning/afternoon/evening) following circadian patterns.

Key improvements over v1:
  - 3 sessions/day instead of 1 (morning, afternoon, evening)
  - 14-day schedule with gradual escalation
  - 12+ activity types (profile, stickers, media, contacts, @SpamBot, etc.)
  - Circadian jitter (±30 min randomized start)
  - Skip probability (15% chance to skip a session — humans aren't robots)
  - Expanded casual message pool (50+ variants)
  - Health monitoring via @SpamBot every 3 days
  - Auto-graduation after day 14

Usage:
  python run_warmup_throwaway.py --session morning
  python run_warmup_throwaway.py --session afternoon
  python run_warmup_throwaway.py --session evening
  python run_warmup_throwaway.py --status
  python run_warmup_throwaway.py --force-day 3 --session morning  # override day
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import secrets
import sqlite3
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv
from loguru import logger
from telethon import TelegramClient, functions, types
from telethon.errors import (
    FloodWaitError,
    ChannelPrivateError,
    ChatWriteForbiddenError,
    UserBannedInChannelError,
    AuthKeyUnregisteredError,
    UserDeactivatedBanError,
)

load_dotenv()

DB_PATH = Path(__file__).parent / "outreach" / "data" / "outreach.db"
DEVICE_PROFILES_PATH = Path(__file__).parent / "outreach" / "data" / "device_profiles.json"
API_POOL_PATH = Path(__file__).parent / "outreach" / "data" / "api_id_pool.json"

# ── 14-Day Schedule ─────────────────────────────────────────────────────────
# Format per session: {activity: count}
# Activities: join, read, react, msg, sticker, media, forward, search, spambot

SCHEDULE = {
    # Day 1: Ultra-light — profile setup + passive
    1: {
        "morning":   {"profile_setup": 1, "join": 1, "read": 3},
        "afternoon": {"join": 1, "read": 5, "react": 2},
        "evening":   {"read": 3, "react": 2},
    },
    # Day 2: Light passive
    2: {
        "morning":   {"read": 5, "react": 2},
        "afternoon": {"join": 1, "react": 3, "read": 5},
        "evening":   {"msg": 1, "react": 2, "read": 3},
    },
    # Day 3: Start casual messaging
    3: {
        "morning":   {"join": 1, "read": 8, "react": 3},
        "afternoon": {"msg": 2, "react": 3, "sticker": 1},
        "evening":   {"msg": 2, "read": 5, "react": 3},
    },
    # Day 4: More engagement
    4: {
        "morning":   {"bio_update": 1, "read": 8, "react": 3},
        "afternoon": {"join": 1, "msg": 3, "read": 5},
        "evening":   {"msg": 3, "react": 5, "read": 5},
    },
    # Day 5: Medium activity
    5: {
        "morning":   {"read": 10, "react": 3, "search": 2},
        "afternoon": {"msg": 4, "react": 3, "sticker": 1},
        "evening":   {"join": 1, "msg": 3, "read": 5, "react": 3},
    },
    # Day 6: Growing
    6: {
        "morning":   {"join": 1, "read": 10, "react": 5},
        "afternoon": {"msg": 5, "react": 3, "forward": 1},
        "evening":   {"msg": 4, "read": 8, "react": 5},
    },
    # Day 7: @SpamBot check + full engagement
    7: {
        "morning":   {"spambot": 1, "read": 12, "react": 5},
        "afternoon": {"msg": 5, "react": 5, "sticker": 1},
        "evening":   {"join": 1, "msg": 5, "react": 8, "read": 5},
    },
    # Day 8-14: Mature activity + optional cold DM testing
    8: {
        "morning":   {"read": 15, "react": 5, "search": 2},
        "afternoon": {"msg": 6, "react": 5, "media": 1},
        "evening":   {"msg": 5, "react": 5, "read": 8},
    },
    9: {
        "morning":   {"join": 1, "read": 15, "react": 8},
        "afternoon": {"msg": 7, "react": 5, "sticker": 1},
        "evening":   {"msg": 6, "react": 8, "forward": 1},
    },
    10: {
        "morning":   {"spambot": 1, "read": 18, "react": 8},
        "afternoon": {"msg": 8, "react": 8, "sticker": 1},
        "evening":   {"msg": 7, "read": 10, "react": 8},
    },
    11: {
        "morning":   {"read": 20, "react": 8, "forward": 1},
        "afternoon": {"msg": 8, "react": 10, "media": 1},
        "evening":   {"msg": 8, "react": 8, "read": 10},
    },
    12: {
        "morning":   {"join": 1, "read": 20, "react": 10},
        "afternoon": {"msg": 10, "react": 8, "forward": 1},
        "evening":   {"msg": 8, "react": 10, "sticker": 1},
    },
    13: {
        "morning":   {"spambot": 1, "read": 22, "react": 10},
        "afternoon": {"msg": 10, "react": 10, "media": 1},
        "evening":   {"msg": 10, "react": 10, "read": 10},
    },
    14: {
        "morning":   {"read": 25, "react": 10, "forward": 1},
        "afternoon": {"msg": 12, "react": 10, "sticker": 1},
        "evening":   {"msg": 10, "react": 12, "read": 10},
    },
}

# Interpolation: days > 14 use day 14 plan
def get_day_plan(day: int) -> dict:
    if day in SCHEDULE:
        return SCHEDULE[day]
    return SCHEDULE[14]

# ── Expanded casual messages (50+ variants) ─────────────────────────────────

CASUAL_MESSAGES = [
    # Appreciative
    "Thanks for sharing! 🙌", "Really appreciate this breakdown",
    "This is gold, saved it 💾", "Super helpful, thanks!",
    "Great content as always 👏", "Appreciate the detail here",
    # Curious
    "Has anyone tried this approach?", "Interesting, what was the result?",
    "Can you elaborate on that?", "What's the source for this?",
    "Anyone else experiencing this?", "Is this still relevant in 2026?",
    # Opinionated
    "Totally agree with this take", "I think there's another angle here...",
    "Good point, but also consider...", "This mirrors my experience too",
    "Strong take 💯", "Exactly what I was thinking",
    # Supportive
    "Keep up the great content 🔥", "This community is amazing",
    "Love the discussion here", "Solid advice right here",
    "New here and already learning a ton", "Quality content 👌",
    # Contextual
    "Just got into this topic, learning a lot", "Been following this for a while",
    "New here but finding great value", "Thanks for the warm welcome everyone",
    # Short reactions
    "Facts 💯", "Nice one 👏", "Interesting 🤔", "Good point!",
    "Very true", "Agreed 👍", "This ☝️", "Makes sense",
    "Bookmarking this for later", "Love this perspective",
    # Engagement starters
    "What does everyone think about this?", "Any updates on this?",
    "Would love to hear more opinions", "Great question honestly",
    "Following this thread 📌", "Saving this conversation",
    # Slightly longer
    "I was just reading about this yesterday, interesting timing",
    "This reminds me of a similar discussion in another group",
    "Appreciate the admin team keeping this group high quality",
    "One of the better groups I've joined lately",
]

SEARCH_TOPICS = [
    "crypto news", "tech startups", "digital marketing",
    "photography tips", "fitness motivation", "AI news",
    "gaming community", "travel adventures", "cooking recipes",
    "movie reviews", "music production", "design inspiration",
    "programming memes", "stock market", "entrepreneurship",
    "forex trading", "web3", "NFT art", "machine learning",
    "self improvement", "book recommendations", "science facts",
    "space exploration", "mobile development", "cybersecurity",
]

REACTION_EMOJIS = ["👍", "🔥", "❤️", "👏", "💯", "🤝", "⚡", "😂", "🤔", "👀"]

STICKER_SEARCH_TERMS = ["hello", "thanks", "cool", "wow", "funny", "love"]

BIO_POOL = [
    "Just exploring 🌍", "Tech enthusiast | Always learning",
    "Crypto & finance 📈", "Digital nomad life ✈️",
    "Music lover 🎵 | Coffee addict ☕", "Building stuff on the internet",
    "Freelance creative 🎨", "Startups & innovation 🚀",
    "Love good conversations", "Here for the communities",
]

SKIP_PROBABILITY = 0.15  # 15% chance to skip a session
JITTER_MAX_SECONDS = 1800  # ±30 min max jitter

# ── DB Helpers ──────────────────────────────────────────────────────────────

def init_warming_db():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    # Check if table exists and has the v2 schema
    cols = [r[1] for r in conn.execute("PRAGMA table_info(warming_progress)").fetchall()]
    if "session_type" not in cols:
        # Drop old v1 table if it exists, create v2
        conn.execute("DROP TABLE IF EXISTS warming_progress")
        cols = []
    if not cols:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS warming_progress (
                phone TEXT,
                day INTEGER,
                session_type TEXT DEFAULT 'morning',
                activities TEXT,
                status TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (phone, day, session_type)
            )
        """)
    conn.commit()
    conn.close()


def get_current_warming_day(phone: str) -> int:
    """Determine current warming day for a phone based on completed sessions."""
    conn = sqlite3.connect(DB_PATH, timeout=30)
    rows = conn.execute(
        "SELECT DISTINCT day FROM warming_progress WHERE phone = ? AND status = 'ok' ORDER BY day DESC LIMIT 1",
        (phone,)
    ).fetchall()
    conn.close()
    if not rows:
        return 1
    last_day = rows[0][0]
    # Check if all 3 sessions for last_day are done
    conn = sqlite3.connect(DB_PATH, timeout=30)
    done = conn.execute(
        "SELECT COUNT(*) FROM warming_progress WHERE phone = ? AND day = ? AND status = 'ok'",
        (phone, last_day)
    ).fetchone()[0]
    conn.close()
    if done >= 3:  # All 3 sessions done, advance to next day
        return last_day + 1
    return last_day


def session_already_done(phone: str, day: int, session_type: str) -> bool:
    conn = sqlite3.connect(DB_PATH, timeout=30)
    row = conn.execute(
        "SELECT 1 FROM warming_progress WHERE phone = ? AND day = ? AND session_type = ?",
        (phone, day, session_type)
    ).fetchone()
    conn.close()
    return row is not None


def log_warming(phone: str, day: int, session_type: str, activities: dict, status: str):
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute(
        """INSERT OR REPLACE INTO warming_progress
           (phone, day, session_type, activities, status)
           VALUES (?, ?, ?, ?, ?)""",
        (phone, day, session_type, json.dumps(activities), status),
    )
    conn.commit()
    conn.close()


def get_fresh_sessions() -> list[dict]:
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM session_pool WHERE state = 'fresh' ORDER BY rowid"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_device_profile(session_phone: str) -> dict | None:
    if not DEVICE_PROFILES_PATH.exists():
        return None
    with open(DEVICE_PROFILES_PATH) as f:
        profiles = json.load(f)
    key = f"tg_{session_phone}"
    if key in profiles:
        return profiles[key]
    for k, v in profiles.items():
        if session_phone in k:
            return v
    return None


def build_socks5_proxy(session_tag: str) -> tuple:
    import python_socks
    host = os.getenv("PROXY_SELLER_HOST", os.getenv("PROXY_HOST", "res.proxy-seller.com"))
    port = int(os.getenv("PROXY_SELLER_PORT", os.getenv("PROXY_PORT", "10000")))
    user_base = os.getenv("PROXY_SELLER_USER", "api004e59f1d44c9a00")
    password = os.getenv("PROXY_SELLER_PASS", os.getenv("PROXY_PASSWORD", "avTItX8z32si7P6p"))
    # Short sticky tag — proxy-seller rejects long session IDs
    username = f"{user_base}_c_US_s_{session_tag}_ttl_1440m"
    return (python_socks.ProxyType.SOCKS5, host, port, True, username, password)


def mark_session_state(session_path: str, state: str, reason: str):
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute(
        "UPDATE session_pool SET state = ?, burn_reason = ? WHERE session_path = ?",
        (state, reason, session_path),
    )
    conn.commit()
    conn.close()


# ── Activity Functions ──────────────────────────────────────────────────────

async def act_join(client, count: int) -> int:
    joined = 0
    topics = random.sample(SEARCH_TOPICS, min(count + 4, len(SEARCH_TOPICS)))
    for topic in topics:
        if joined >= count:
            break
        try:
            result = await client(functions.contacts.SearchRequest(q=topic, limit=5))
            for chat in result.chats:
                if joined >= count:
                    break
                if getattr(chat, "left", True) is False:
                    continue
                try:
                    await client(functions.channels.JoinChannelRequest(chat))
                    joined += 1
                    logger.info("  📥 Joined: '{}'", getattr(chat, "title", "?"))
                    await asyncio.sleep(random.uniform(15, 40))
                except FloodWaitError as e:
                    logger.warning("  FloodWait {}s on join", e.seconds)
                    await asyncio.sleep(e.seconds + 5)
                except Exception:
                    continue
            await asyncio.sleep(random.uniform(5, 12))
        except Exception:
            continue
    return joined


async def act_read(client, count: int) -> int:
    read = 0
    try:
        dialogs = await client.get_dialogs(limit=50)
        channels = [d for d in dialogs if d.is_channel or d.is_group]
    except Exception:
        return 0
    random.shuffle(channels)
    for dialog in channels[:count]:
        try:
            async for _ in client.iter_messages(dialog.entity, limit=random.randint(5, 15)):
                pass
            await client.send_read_acknowledge(dialog.entity)
            read += 1
            await asyncio.sleep(random.uniform(2, 8))
        except Exception:
            continue
    return read


async def act_react(client, count: int) -> int:
    reacted = 0
    try:
        dialogs = await client.get_dialogs(limit=40)
        candidates = [d for d in dialogs if d.is_channel or d.is_group]
    except Exception:
        return 0
    random.shuffle(candidates)
    for dialog in candidates:
        if reacted >= count:
            break
        try:
            msgs = await client.get_messages(dialog.entity, limit=5)
            for m in msgs:
                if reacted >= count:
                    break
                emoji = random.choice(REACTION_EMOJIS)
                try:
                    await client(functions.messages.SendReactionRequest(
                        peer=dialog.entity, msg_id=m.id,
                        reaction=[types.ReactionEmoji(emoticon=emoji)],
                    ))
                    reacted += 1
                    await asyncio.sleep(random.uniform(3, 12))
                except Exception:
                    continue
        except Exception:
            continue
    return reacted


async def act_msg(client, count: int) -> int:
    sent = 0
    try:
        dialogs = await client.get_dialogs(limit=30)
        groups = [d for d in dialogs if d.is_group]
    except Exception:
        return 0
    random.shuffle(groups)
    for dialog in groups[:count + 2]:
        if sent >= count:
            break
        try:
            msg = random.choice(CASUAL_MESSAGES)
            await client.send_message(dialog.entity, msg)
            sent += 1
            logger.info("  💬 Msg in '{}'", dialog.name)
            await asyncio.sleep(random.uniform(15, 45))
        except (ChatWriteForbiddenError, UserBannedInChannelError):
            continue
        except FloodWaitError as e:
            await asyncio.sleep(e.seconds + 5)
        except Exception:
            continue
    return sent


async def act_sticker(client, count: int) -> int:
    """Send a sticker in a group — diversity signal."""
    sent = 0
    try:
        dialogs = await client.get_dialogs(limit=20)
        groups = [d for d in dialogs if d.is_group]
    except Exception:
        return 0
    if not groups:
        return 0
    random.shuffle(groups)
    for dialog in groups[:count]:
        try:
            # Search for a sticker set
            term = random.choice(STICKER_SEARCH_TERMS)
            result = await client(functions.messages.SearchStickerSetsRequest(
                q=term, exclude_featured=False, hash=0
            ))
            if result.sets:
                sticker_set = random.choice(result.sets)
                full_set = await client(functions.messages.GetStickerSetRequest(
                    stickerset=types.InputStickerSetID(
                        id=sticker_set.id, access_hash=sticker_set.access_hash
                    ), hash=0
                ))
                if full_set.documents:
                    sticker = random.choice(full_set.documents)
                    await client.send_file(dialog.entity, sticker)
                    sent += 1
                    logger.info("  🎭 Sticker in '{}'", dialog.name)
                    await asyncio.sleep(random.uniform(10, 30))
        except Exception:
            continue
    return sent


async def act_forward(client, count: int) -> int:
    """Forward a message from one group to another — content sharing signal."""
    forwarded = 0
    try:
        dialogs = await client.get_dialogs(limit=30)
        groups = [d for d in dialogs if d.is_group]
    except Exception:
        return 0
    if len(groups) < 2:
        return 0
    random.shuffle(groups)
    for _ in range(count):
        try:
            source = random.choice(groups)
            msgs = await client.get_messages(source.entity, limit=10)
            suitable = [m for m in msgs if m.text and len(m.text) > 10]
            if suitable:
                msg = random.choice(suitable)
                target = random.choice([g for g in groups if g.id != source.id])
                await client.forward_messages(target.entity, msg)
                forwarded += 1
                logger.info("  ↗️ Forwarded to '{}'", target.name)
                await asyncio.sleep(random.uniform(15, 40))
        except Exception:
            continue
    return forwarded


async def act_search(client, count: int) -> int:
    """Perform search queries — browsing signal."""
    searched = 0
    terms = random.sample(SEARCH_TOPICS, min(count, len(SEARCH_TOPICS)))
    for term in terms:
        try:
            await client(functions.contacts.SearchRequest(q=term, limit=3))
            searched += 1
            await asyncio.sleep(random.uniform(5, 15))
        except Exception:
            continue
    return searched


async def act_media(client, count: int) -> int:
    """React to media/photos in groups — engagement signal."""
    reacted = 0
    try:
        dialogs = await client.get_dialogs(limit=30)
        groups = [d for d in dialogs if d.is_group or d.is_channel]
    except Exception:
        return 0
    random.shuffle(groups)
    for dialog in groups:
        if reacted >= count:
            break
        try:
            msgs = await client.get_messages(dialog.entity, limit=10)
            for m in msgs:
                if reacted >= count:
                    break
                if m.media:
                    emoji = random.choice(["🔥", "❤️", "👏", "💯"])
                    try:
                        await client(functions.messages.SendReactionRequest(
                            peer=dialog.entity, msg_id=m.id,
                            reaction=[types.ReactionEmoji(emoticon=emoji)],
                        ))
                        reacted += 1
                        await asyncio.sleep(random.uniform(5, 15))
                    except Exception:
                        continue
        except Exception:
            continue
    return reacted


async def act_spambot(client) -> str:
    """Check @SpamBot for account health status."""
    try:
        await client.send_message("SpamBot", "/start")
        await asyncio.sleep(5)
        msgs = await client.get_messages("SpamBot", limit=1)
        if msgs:
            text = msgs[0].text or ""
            logger.info("  🤖 @SpamBot: {}", text[:100])
            if "no limits" in text.lower() or "free" in text.lower():
                return "clean"
            elif "limit" in text.lower() or "restrict" in text.lower():
                return "restricted"
            return "unknown"
    except Exception as e:
        logger.debug("  @SpamBot check failed: {}", e)
        return "error"


async def act_profile_setup(client) -> bool:
    """Set profile photo and bio on day 1."""
    try:
        bio = random.choice(BIO_POOL)
        await client(functions.account.UpdateProfileRequest(about=bio))
        logger.info("  👤 Set bio: '{}'", bio)
        await asyncio.sleep(random.uniform(5, 15))
        return True
    except Exception as e:
        logger.debug("  Profile setup failed: {}", e)
        return False


async def act_bio_update(client) -> bool:
    """Update bio — profile evolution signal."""
    try:
        bio = random.choice(BIO_POOL)
        await client(functions.account.UpdateProfileRequest(about=bio))
        logger.info("  ✏️ Updated bio: '{}'", bio)
        return True
    except Exception:
        return False


# ── Session Executor ────────────────────────────────────────────────────────

ACTIVITY_MAP = {
    "join": act_join,
    "read": act_read,
    "react": act_react,
    "msg": act_msg,
    "sticker": act_sticker,
    "forward": act_forward,
    "search": act_search,
    "media": act_media,
}


async def execute_session(session: dict, day: int, session_type: str) -> dict:
    """Execute a single warming session for one account."""
    phone = session["phone"]
    session_path = session["session_path"]

    # Check if already done
    if session_already_done(phone, day, session_type):
        logger.info("Session {}/{} day {} already done, skipping", phone, session_type, day)
        return {"phone": phone, "day": day, "session": session_type, "status": "already_done"}

    plan = get_day_plan(day)
    if session_type not in plan:
        return {"phone": phone, "day": day, "session": session_type, "status": "no_plan"}

    activities_plan = plan[session_type]

    # Apply activity variance (±30%)
    varied_plan = {}
    for act, count in activities_plan.items():
        if act in ("profile_setup", "bio_update", "spambot"):
            varied_plan[act] = count
        else:
            variance = max(1, int(count * random.uniform(0.7, 1.3)))
            varied_plan[act] = variance

    logger.info(
        "=== {} session for {} (day {}) — {} ===",
        session_type.upper(), phone, day, varied_plan,
    )

    # Short sticky tag: w{index} — same IP across all 3 daily sessions per phone
    fresh_sessions = get_fresh_sessions()
    session_idx = next((i for i, s in enumerate(fresh_sessions) if s["phone"] == phone), 0)
    sticky_tag = f"w{session_idx:02d}"
    proxy = build_socks5_proxy(sticky_tag)

    device = get_device_profile(phone)
    api_id = device.get("api_id", 2040) if device else 2040
    api_hash = device.get("api_hash", "b18441a1ff607e10a989891a5462e627") if device else "b18441a1ff607e10a989891a5462e627"

    client_kwargs = {
        "session": session_path,
        "api_id": api_id,
        "api_hash": api_hash,
        "proxy": proxy,
    }
    if device:
        client_kwargs["device_model"] = device.get("device_model", "Samsung SM-G998B")
        client_kwargs["system_version"] = device.get("system_version", "SDK 31")
        client_kwargs["app_version"] = device.get("app_version", "9.7.6")
        client_kwargs["lang_code"] = device.get("lang_code", "en")
        client_kwargs["system_lang_code"] = device.get("system_lang_code", "en-US")

    client = TelegramClient(**client_kwargs)
    results = {"phone": phone, "day": day, "session": session_type}
    status = "ok"

    try:
        await client.connect()
        me = await client.get_me()
        if not me:
            logger.error("Session {} invalid", phone)
            results["status"] = "invalid"
            return results

        logger.info("Connected as: {} (@{})", me.first_name, me.username)

        # Execute each activity with random ordering for naturalness
        activity_items = list(varied_plan.items())
        random.shuffle(activity_items)

        for act_name, count in activity_items:
            # Inter-activity delay (humans pause between actions)
            await asyncio.sleep(random.uniform(5, 20))

            if act_name == "profile_setup":
                ok = await act_profile_setup(client)
                results["profile_setup"] = 1 if ok else 0
            elif act_name == "bio_update":
                ok = await act_bio_update(client)
                results["bio_update"] = 1 if ok else 0
            elif act_name == "spambot":
                health = await act_spambot(client)
                results["spambot"] = health
                if health == "restricted":
                    logger.warning("⚠️ {} is RESTRICTED — pausing warmup", phone)
                    status = "restricted"
                    break
            elif act_name in ACTIVITY_MAP:
                done = await ACTIVITY_MAP[act_name](client, count)
                results[act_name] = done
            else:
                logger.debug("Unknown activity: {}", act_name)

        logger.info("Session complete for {}: {}", phone, {k: v for k, v in results.items() if k not in ("phone", "day", "session")})

    except AuthKeyUnregisteredError:
        logger.error("💀 {} — AUTH_KEY_UNREGISTERED (dead)", phone)
        status = "dead"
        mark_session_state(session_path, "banned", "AuthKeyUnregisteredError")
    except UserDeactivatedBanError:
        logger.error("💀 {} — BANNED", phone)
        status = "banned"
        mark_session_state(session_path, "banned", "UserDeactivatedBanError")
    except FloodWaitError as e:
        logger.warning("⚠️ {} — FloodWait {}s, stopping early", phone, e.seconds)
        status = f"flood_{e.seconds}s"
    except Exception as e:
        logger.error("❌ {} — Error: {}", phone, e)
        status = f"error"
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass

    results["status"] = status
    log_warming(phone, day, session_type, results, status)
    return results


# ── Main Orchestrator ───────────────────────────────────────────────────────

async def run_session(session_type: str, force_day: int = 0):
    """Run a specific session (morning/afternoon/evening) for all fresh sessions."""
    init_warming_db()

    sessions = get_fresh_sessions()
    if not sessions:
        logger.error("No fresh sessions for warming")
        return

    # Apply circadian jitter (0-30 min random delay)
    jitter = random.randint(0, JITTER_MAX_SECONDS)
    logger.info("⏰ Circadian jitter: {}s ({:.0f} min) before starting", jitter, jitter / 60)
    await asyncio.sleep(jitter)

    results = []
    for i, session in enumerate(sessions):
        phone = session["phone"]

        # Determine current day
        day = force_day if force_day > 0 else get_current_warming_day(phone)

        if day > 14:
            logger.info("✅ {} completed 14-day warmup — ready for outreach!", phone)
            # Mark as warmed (don't change state, but log graduation)
            log_warming(phone, day, session_type, {"graduated": True}, "graduated")
            continue

        # Skip probability (15% chance)
        if random.random() < SKIP_PROBABILITY:
            logger.info("⏭️ Skipping {} {} session (random skip)", phone, session_type)
            log_warming(phone, day, session_type, {"skipped": True}, "skipped")
            continue

        result = await execute_session(session, day, session_type)
        results.append(result)

        # Inter-session gap (30-120s between accounts)
        if i < len(sessions) - 1:
            gap = random.uniform(30, 120)
            logger.info("Inter-session gap: {:.0f}s", gap)
            await asyncio.sleep(gap)

    # Summary
    ok = sum(1 for r in results if r.get("status") == "ok")
    dead = sum(1 for r in results if r.get("status") in ("dead", "banned"))
    skipped = sum(1 for r in results if r.get("status") in ("skipped", "already_done"))

    print(f"\n{'='*45}")
    print(f"🌡️ {session_type.upper()} Session Summary")
    print(f"{'='*45}")
    print(f"✅ Successful: {ok}/{len(results)}")
    if dead:
        print(f"💀 Dead/Banned: {dead}")
    for r in results:
        emoji = "✅" if r.get("status") == "ok" else "❌" if r.get("status") in ("dead", "banned") else "⏭️"
        acts = {k: v for k, v in r.items() if k not in ("phone", "day", "session", "status")}
        print(f"  {emoji} {r['phone']} (day {r.get('day', '?')}): {acts} [{r.get('status')}]")
    print()


async def show_status():
    """Show warming progress for all sessions."""
    init_warming_db()
    conn = sqlite3.connect(DB_PATH, timeout=30)

    fresh = conn.execute(
        "SELECT phone, session_path FROM session_pool WHERE state = 'fresh'"
    ).fetchall()
    print(f"\n📱 Fresh sessions: {len(fresh)}")

    for phone, path in fresh:
        day = get_current_warming_day(phone)
        sessions_today = conn.execute(
            "SELECT session_type, status FROM warming_progress WHERE phone = ? AND day = ? ORDER BY session_type",
            (phone, day)
        ).fetchall()

        done_sessions = [s[0] for s in sessions_today if s[1] == "ok"]
        progress = f"day {day}/14"
        if day > 14:
            progress = "✅ GRADUATED"

        sessions_str = ", ".join(done_sessions) if done_sessions else "none yet"
        print(f"  {phone}: {progress} | today: [{sessions_str}]")

    # Overall stats
    total_activities = conn.execute(
        "SELECT COUNT(*) FROM warming_progress WHERE status = 'ok'"
    ).fetchone()[0]
    print(f"\n📊 Total completed sessions: {total_activities}")

    conn.close()


async def main():
    parser = argparse.ArgumentParser(description="Enhanced warm-up (v2): 14-day, 3x/day")
    parser.add_argument("--session", choices=["morning", "afternoon", "evening"],
                        help="Which session to run")
    parser.add_argument("--force-day", type=int, default=0,
                        help="Override warming day (for testing)")
    parser.add_argument("--status", action="store_true", help="Show warming progress")
    args = parser.parse_args()

    if args.status:
        await show_status()
        return

    if not args.session:
        print("Usage: python run_warmup_throwaway.py --session morning|afternoon|evening")
        print("       python run_warmup_throwaway.py --status")
        return

    await run_session(args.session, args.force_day)


if __name__ == "__main__":
    asyncio.run(main())
