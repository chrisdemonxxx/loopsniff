"""Safe warm-up for throwaway TData sessions.

Connects each fresh session via SOCKS5 proxy with matching device
telemetry and performs gentle organic activities:
  - Join a few public groups/channels
  - Read channel messages (mark as read)
  - React to posts with emojis
  - Send casual messages in group chats

NEVER sends DMs to strangers.  Each session gets its own sticky proxy IP.
Sessions are spaced 30-120s apart to avoid pattern detection.

Usage:
  python run_warmup_throwaway.py --day 1
  python run_warmup_throwaway.py --day 2 --sessions 3  # limit to N sessions
  python run_warmup_throwaway.py --status              # show warming progress
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

# Gentle warming schedule: (join_groups, casual_msgs, read_channels, reactions)
WARMING_SCHEDULE = {
    1:  (2,  2,  5,  3),   # very light
    2:  (2,  3,  8,  5),
    3:  (3,  5,  10, 8),
    4:  (3,  5,  12, 10),
    5:  (3,  8,  15, 12),
}

# Safe public groups/channels to join (large, won't flag for joining)
SEARCH_TOPICS = [
    "crypto news", "tech startups", "digital marketing",
    "photography tips", "fitness motivation", "AI news",
    "gaming community", "travel adventures", "cooking recipes",
    "movie reviews", "music production", "design inspiration",
    "programming memes", "stock market", "entrepreneurship",
]

CASUAL_MESSAGES = [
    "Thanks for sharing! 🙌",
    "Great insight, appreciate it.",
    "Interesting perspective 👍",
    "Good point!",
    "Very helpful, thanks!",
    "Love this community 🔥",
    "Solid advice right here.",
    "Bookmarking this for later.",
    "Facts 💯",
    "Nice one 👏",
]

REACTION_EMOJIS = ["👍", "🔥", "❤️", "👏", "💯"]


def get_fresh_sessions() -> list[dict]:
    """Read fresh sessions from session_pool DB."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM session_pool WHERE state = 'fresh' ORDER BY rowid"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_device_profile(session_phone: str) -> dict | None:
    """Match a device profile for this session."""
    if not DEVICE_PROFILES_PATH.exists():
        return None
    with open(DEVICE_PROFILES_PATH) as f:
        profiles = json.load(f)
    # profiles is a dict keyed by tg_{phone}
    key = f"tg_{session_phone}"
    if key in profiles:
        return profiles[key]
    # Try partial match
    for k, v in profiles.items():
        if session_phone in k:
            return v
    return None


def get_api_credentials() -> tuple[int, str]:
    """Get API credentials from pool."""
    if API_POOL_PATH.exists():
        with open(API_POOL_PATH) as f:
            pool = json.load(f)
        if pool:
            entry = random.choice(pool)
            return entry["api_id"], entry["api_hash"]
    return int(os.getenv("TELEGRAM_API_ID", "2040")), os.getenv(
        "TELEGRAM_API_HASH", "b18441a1ff607e10a989891a5462e627"
    )


def build_socks5_proxy(session_id: str) -> tuple:
    """Build SOCKS5 proxy tuple for Telethon (matching throwaway engine)."""
    import python_socks
    host = os.getenv("PROXY_SELLER_HOST", "res.proxy-seller.com")
    port = int(os.getenv("PROXY_SELLER_PORT", "10000"))
    user_base = os.getenv("PROXY_SELLER_USER", "api004e59f1d44c9a00")
    password = os.getenv("PROXY_SELLER_PASS", os.getenv("PROXY_PASSWORD", ""))
    country = "US"

    # Sticky session: each session gets its own residential IP
    username = f"{user_base}_c_{country}_s_{session_id}_ttl_1440m"

    return (python_socks.ProxyType.SOCKS5, host, port, True, username, password)


async def join_groups(client, count: int) -> int:
    """Join public groups by searching — safe, organic activity."""
    joined = 0
    topics = random.sample(SEARCH_TOPICS, min(count + 3, len(SEARCH_TOPICS)))

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
                    title = getattr(chat, "title", "?")
                    logger.info("  Joined: '{}'", title)
                    # Gentle delay between joins
                    await asyncio.sleep(random.uniform(15, 40))
                except FloodWaitError as e:
                    logger.warning("  FloodWait {}s on join — sleeping", e.seconds)
                    await asyncio.sleep(e.seconds + 5)
                except Exception as exc:
                    logger.debug("  Could not join: {}", exc)
            await asyncio.sleep(random.uniform(5, 12))
        except FloodWaitError as e:
            logger.warning("  FloodWait {}s on search — sleeping", e.seconds)
            await asyncio.sleep(e.seconds + 5)
        except Exception as exc:
            logger.debug("  Search '{}' failed: {}", topic, exc)
    return joined


async def read_channels(client, count: int) -> int:
    """Read and mark-as-read channel messages — builds organic footprint."""
    read = 0
    try:
        dialogs = await client.get_dialogs(limit=50)
        channels = [d for d in dialogs if d.is_channel]
    except Exception:
        channels = []

    random.shuffle(channels)
    for dialog in channels[:count]:
        try:
            async for _ in client.iter_messages(dialog.entity, limit=10):
                pass
            await client.send_read_acknowledge(dialog.entity)
            read += 1
            await asyncio.sleep(random.uniform(3, 10))
        except Exception:
            continue
    return read


async def react_to_posts(client, count: int) -> int:
    """React to posts with emojis — organic engagement signal."""
    reacted = 0
    try:
        dialogs = await client.get_dialogs(limit=40)
        candidates = [d for d in dialogs if d.is_channel or d.is_group]
    except Exception:
        candidates = []

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
                    await client(
                        functions.messages.SendReactionRequest(
                            peer=dialog.entity,
                            msg_id=m.id,
                            reaction=[types.ReactionEmoji(emoticon=emoji)],
                        )
                    )
                    reacted += 1
                    await asyncio.sleep(random.uniform(5, 15))
                except Exception:
                    continue
        except Exception:
            continue
    return reacted


async def send_casual_in_groups(client, count: int) -> int:
    """Send casual messages IN groups (NOT DMs to strangers)."""
    sent = 0
    try:
        dialogs = await client.get_dialogs(limit=30)
        groups = [d for d in dialogs if d.is_group]
    except Exception:
        groups = []

    random.shuffle(groups)
    for dialog in groups[:count]:
        try:
            msg = random.choice(CASUAL_MESSAGES)
            await client.send_message(dialog.entity, msg)
            sent += 1
            logger.info("  Casual msg in '{}'", dialog.name)
            await asyncio.sleep(random.uniform(20, 60))
        except (ChatWriteForbiddenError, UserBannedInChannelError):
            continue
        except FloodWaitError as e:
            logger.warning("  FloodWait {}s — sleeping", e.seconds)
            await asyncio.sleep(e.seconds + 5)
        except Exception as exc:
            logger.debug("  Could not message in '{}': {}", dialog.name, exc)
    return sent


async def warm_session(session: dict, day: int) -> dict:
    """Execute warming for a single session — fully proxied."""
    phone = session["phone"]
    session_path = session["session_path"]
    plan = WARMING_SCHEDULE.get(day, WARMING_SCHEDULE[5])
    join_target, msg_target, read_target, react_target = plan

    logger.info(
        "=== Warming {} (day {}) — join={}, msg={}, read={}, react={} ===",
        phone, day, *plan,
    )

    # Build proxy with unique sticky session
    sticky_id = f"warm_{phone}_{day}"
    proxy = build_socks5_proxy(sticky_id)

    # Get device profile first, then extract API credentials from it
    device = get_device_profile(phone)
    api_id = device.get("api_id", int(os.getenv("TELEGRAM_API_ID", "2040"))) if device else int(os.getenv("TELEGRAM_API_ID", "2040"))
    api_hash = device.get("api_hash", os.getenv("TELEGRAM_API_HASH", "b18441a1ff607e10a989891a5462e627")) if device else os.getenv("TELEGRAM_API_HASH", "b18441a1ff607e10a989891a5462e627")

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

    result = {
        "phone": phone,
        "day": day,
        "joined": 0, "msgs": 0, "read": 0, "reacted": 0,
        "status": "ok",
    }

    try:
        await client.connect()
        me = await client.get_me()
        if not me:
            logger.error("Session {} invalid — get_me() returned None", phone)
            result["status"] = "invalid"
            return result

        logger.info("Connected as: {} (@{})", me.first_name, me.username)

        # Execute warming activities with generous delays
        result["joined"] = await join_groups(client, join_target)
        await asyncio.sleep(random.uniform(10, 25))

        result["read"] = await read_channels(client, read_target)
        await asyncio.sleep(random.uniform(10, 25))

        result["reacted"] = await react_to_posts(client, react_target)
        await asyncio.sleep(random.uniform(10, 25))

        # Only send casual group msgs if we've joined enough groups
        if result["joined"] >= 1:
            result["msgs"] = await send_casual_in_groups(client, msg_target)

        logger.info(
            "Warming complete for {}: joined={}, read={}, reacted={}, msgs={}",
            phone, result["joined"], result["read"], result["reacted"], result["msgs"],
        )

    except AuthKeyUnregisteredError:
        logger.error("Session {} — AUTH_KEY_UNREGISTERED (dead session)", phone)
        result["status"] = "dead"
        mark_session_state(session_path, "banned", "AuthKeyUnregisteredError")
    except UserDeactivatedBanError:
        logger.error("Session {} — BANNED", phone)
        result["status"] = "banned"
        mark_session_state(session_path, "banned", "UserDeactivatedBanError")
    except FloodWaitError as e:
        logger.warning("Session {} — FloodWait {}s, stopping warmup early", phone, e.seconds)
        result["status"] = f"flood_{e.seconds}s"
    except Exception as e:
        logger.error("Session {} — Error: {}", phone, e)
        result["status"] = f"error: {e}"
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass

    return result


def mark_session_state(session_path: str, state: str, reason: str):
    """Update session state in DB if it's dead/banned."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE session_pool SET state = ?, burn_reason = ? WHERE session_path = ?",
        (state, reason, session_path),
    )
    conn.commit()
    conn.close()


def log_warming_result(result: dict):
    """Log warming result to DB for tracking."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS warming_progress (
            phone TEXT,
            day INTEGER,
            joined INTEGER,
            msgs INTEGER,
            read_ch INTEGER,
            reacted INTEGER,
            status TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (phone, day)
        )
    """)
    conn.execute(
        """INSERT OR REPLACE INTO warming_progress
           (phone, day, joined, msgs, read_ch, reacted, status)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (result["phone"], result["day"], result["joined"],
         result["msgs"], result["read"], result["reacted"], result["status"]),
    )
    conn.commit()
    conn.close()


async def show_status():
    """Show warming progress for all sessions."""
    conn = sqlite3.connect(DB_PATH)

    fresh = conn.execute(
        "SELECT phone, session_path FROM session_pool WHERE state = 'fresh'"
    ).fetchall()
    print(f"\n📱 Fresh sessions ready for warming: {len(fresh)}")
    for phone, path in fresh:
        name = path.split("/")[-1]
        print(f"  {name} ({phone})")

    # Check warming progress table
    try:
        progress = conn.execute(
            "SELECT phone, day, joined, msgs, read_ch, reacted, status, timestamp "
            "FROM warming_progress ORDER BY phone, day"
        ).fetchall()
        if progress:
            print(f"\n📊 Warming Progress:")
            for phone, day, joined, msgs, read_ch, reacted, status, ts in progress:
                total = joined + msgs + read_ch + reacted
                print(f"  {phone} day {day}: {total} activities ({status}) [{ts}]")
    except sqlite3.OperationalError:
        print("\n📊 No warming history yet")

    conn.close()


async def main():
    parser = argparse.ArgumentParser(description="Safe warm-up for throwaway sessions")
    parser.add_argument("--day", type=int, default=1, help="Warming day (1-5)")
    parser.add_argument("--sessions", type=int, default=0, help="Limit to N sessions (0=all)")
    parser.add_argument("--status", action="store_true", help="Show warming progress")
    args = parser.parse_args()

    if args.status:
        await show_status()
        return

    sessions = get_fresh_sessions()
    if not sessions:
        logger.error("No fresh sessions available for warming")
        return

    if args.sessions > 0:
        sessions = sessions[:args.sessions]

    logger.info(
        "Starting warm-up: {} sessions, day {}, schedule={}",
        len(sessions), args.day, WARMING_SCHEDULE.get(args.day, WARMING_SCHEDULE[5]),
    )

    results = []
    for i, session in enumerate(sessions):
        result = await warm_session(session, args.day)
        results.append(result)
        log_warming_result(result)

        # Inter-session spacing: 30-120s
        if i < len(sessions) - 1:
            gap = random.uniform(30, 120)
            logger.info("Inter-session gap: {:.0f}s before next session", gap)
            await asyncio.sleep(gap)

    # Summary
    ok = sum(1 for r in results if r["status"] == "ok")
    dead = sum(1 for r in results if r["status"] in ("dead", "banned"))
    total_activities = sum(
        r["joined"] + r["msgs"] + r["read"] + r["reacted"]
        for r in results
    )

    print(f"\n{'='*40}")
    print(f"🌡️ Warm-up Summary (Day {args.day})")
    print(f"{'='*40}")
    print(f"✅ Successful: {ok}/{len(results)}")
    if dead:
        print(f"💀 Dead/Banned: {dead}")
    print(f"📊 Total activities: {total_activities}")
    for r in results:
        emoji = "✅" if r["status"] == "ok" else "❌"
        print(
            f"  {emoji} {r['phone']}: "
            f"join={r['joined']} msg={r['msgs']} "
            f"read={r['read']} react={r['reacted']} ({r['status']})"
        )
    print()
    if ok > 0:
        print(f"Run again tomorrow: python run_warmup_throwaway.py --day {args.day + 1}")


if __name__ == "__main__":
    asyncio.run(main())
