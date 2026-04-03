#!/usr/bin/env python3
"""Set @usernames on all active Telegram outreach accounts.

Generates usernames from profile first+last names with a random suffix.
Retries with a different suffix if the username is already taken.

Usage:
    python set_usernames.py          # set usernames on all active accounts
    python set_usernames.py --dry    # preview without changes
    python set_usernames.py --check  # just check current usernames
"""

from __future__ import annotations

import asyncio
import logging
import random
import string
import sys

sys.path.insert(0, "/home/cjs/tgacc/adflux-rag")

from telethon.tl.functions.account import UpdateUsernameRequest
from telethon.errors import UsernameOccupiedError, UsernameInvalidError, FloodWaitError

from outreach import db, config
from outreach.session_manager import SessionManager
from telethon import TelegramClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("set_usernames")

# Same profile list as setup_profiles.py — keep in sync
PROFILES = [
    {"first": "Alex", "last": "Rivera"},
    {"first": "Jordan", "last": "Chen"},
    {"first": "Sam", "last": "Patel"},
    {"first": "Taylor", "last": "Brooks"},
    {"first": "Morgan", "last": "Lee"},
    {"first": "Casey", "last": "Kim"},
    {"first": "Riley", "last": "Santos"},
    {"first": "Drew", "last": "Miller"},
    {"first": "Jamie", "last": "Cruz"},
    {"first": "Chris", "last": "Nguyen"},
    {"first": "Dakota", "last": "Park"},
    {"first": "Avery", "last": "Singh"},
    {"first": "Reese", "last": "Torres"},
    {"first": "Quinn", "last": "Adams"},
    {"first": "Blake", "last": "Hernandez"},
    {"first": "Skyler", "last": "Wang"},
    {"first": "Emery", "last": "Morales"},
    {"first": "Finley", "last": "Thompson"},
    {"first": "Hayden", "last": "Garcia"},
    {"first": "Lennox", "last": "Reyes"},
    {"first": "Parker", "last": "Davis"},
    {"first": "Rowan", "last": "Martinez"},
    {"first": "Phoenix", "last": "Clark"},
    {"first": "Sage", "last": "Lopez"},
    {"first": "Harley", "last": "Wright"},
    {"first": "River", "last": "Stone"},
    {"first": "Briar", "last": "James"},
]

MAX_RETRIES = 5


def _get_direct_client(phone: str) -> TelegramClient:
    """Return a TelegramClient WITHOUT proxy for admin operations."""
    safe = phone.replace("+", "").replace(" ", "")
    # Try tg_ prefix first, then plain name
    tg_path = config.SESSIONS_DIR / f"tg_{safe}"
    plain_path = config.SESSIONS_DIR / safe
    if tg_path.with_suffix(".session").exists():
        session_path = str(tg_path)
    elif plain_path.with_suffix(".session").exists():
        session_path = str(plain_path)
    else:
        session_path = str(tg_path)  # fallback
    log.debug("Session path for %s: %s", phone, session_path)
    return TelegramClient(session_path, config.API_ID, config.API_HASH, proxy=None)


def generate_username(first: str, last: str, attempt: int = 0) -> str:
    """Generate a Telegram-valid username from first+last name.

    Telegram usernames: 5-32 chars, a-z/0-9/underscore, must start with letter.
    """
    base = f"{first}_{last}".lower()
    if attempt == 0:
        suffix = str(random.randint(10, 99))
    else:
        suffix = "".join(random.choices(string.digits, k=3 + attempt))
    username = f"{base}_{suffix}"
    # Ensure it's within 5-32 chars
    return username[:32]


async def check_usernames() -> None:
    """Just print current usernames for all active accounts."""
    await db.init_db()
    sm = SessionManager()
    accounts = await db.get_accounts()
    active = [a for a in accounts if a.status == "active"]

    log.info("Checking usernames for %d active accounts...", len(active))

    for i, account in enumerate(active):
        try:
            client = _get_direct_client(account.phone)
            try:
                await asyncio.wait_for(client.connect(), timeout=15)
            except (asyncio.TimeoutError, Exception) as ce:
                log.error("[%d] %s — connect failed: %s", i + 1, account.phone, ce)
                continue
            try:
                if not await asyncio.wait_for(client.is_user_authorized(), timeout=10):
                    log.warning("[%d] %s — NOT authorized", i + 1, account.phone)
                    continue
                me = await asyncio.wait_for(client.get_me(), timeout=10)
                uname = f"@{me.username}" if me.username else "(no username)"
                log.info(
                    "[%d/%d] %s → %s %s  username=%s",
                    i + 1, len(active), account.phone,
                    me.first_name or "", me.last_name or "", uname,
                )
            finally:
                await client.disconnect()
        except asyncio.TimeoutError:
            log.error("[%d] %s — timeout", i + 1, account.phone)
        except Exception as exc:
            log.error("[%d] %s — error: %s", i + 1, account.phone, exc)
        await asyncio.sleep(1)


async def set_usernames(dry_run: bool = False) -> None:
    """Set @usernames on all active accounts."""
    await db.init_db()
    sm = SessionManager()

    accounts = await db.get_accounts()
    active = [a for a in accounts if a.status == "active"]

    log.info("Setting usernames for %d active accounts...", len(active))

    success = 0
    skipped = 0
    failed = 0

    for i, account in enumerate(active):
        profile = PROFILES[i % len(PROFILES)]
        first = profile["first"]
        last = profile["last"]

        log.info("[%d/%d] %s (%s %s)", i + 1, len(active), account.phone, first, last)

        if dry_run:
            sample = generate_username(first, last)
            log.info("  DRY RUN: would set username like @%s", sample)
            success += 1
            continue

        try:
            client = _get_direct_client(account.phone)
            try:
                await asyncio.wait_for(client.connect(), timeout=15)
            except (asyncio.TimeoutError, Exception) as ce:
                log.error("  %s connect failed: %s", account.phone, ce)
                failed += 1
                continue
            try:
                if not await asyncio.wait_for(client.is_user_authorized(), timeout=10):
                    log.warning("  %s not authorized — skipping", account.phone)
                    skipped += 1
                    continue

                # Check if already has a username
                me = await asyncio.wait_for(client.get_me(), timeout=10)
                if me.username:
                    log.info("  ✅ Already has username: @%s — skipping", me.username)
                    skipped += 1
                    continue

                # Use the actual first/last name from the account
                actual_first = (me.first_name or first).split()[0]
                actual_last = (me.last_name or last).split()[0] if (me.last_name or last) else last

                # Try setting username with retries for taken names
                set_ok = False
                for attempt in range(MAX_RETRIES):
                    username = generate_username(actual_first, actual_last, attempt)
                    try:
                        await client(UpdateUsernameRequest(username=username))
                        log.info("  ✅ Username set: @%s", username)
                        set_ok = True
                        success += 1
                        break
                    except UsernameOccupiedError:
                        log.info("  ⚠️  @%s taken, retrying...", username)
                        continue
                    except UsernameInvalidError:
                        log.warning("  ⚠️  @%s invalid, retrying...", username)
                        continue
                    except FloodWaitError as e:
                        log.warning("  ⏳ Flood wait %ds — sleeping...", e.seconds)
                        await asyncio.sleep(e.seconds + 2)
                        continue

                if not set_ok:
                    log.error("  ❌ Could not set username after %d attempts", MAX_RETRIES)
                    failed += 1

                # Delay between accounts to avoid rate limits
                await asyncio.sleep(random.uniform(3, 7))

            finally:
                await client.disconnect()

        except Exception as exc:
            log.error("  ❌ Failed for %s: %s", account.phone, exc)
            failed += 1

    log.info(
        "Username setup complete: %d set, %d skipped, %d failed (of %d total)",
        success, skipped, failed, len(active),
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Set @usernames for TG accounts")
    parser.add_argument("--dry", action="store_true", help="Preview without changes")
    parser.add_argument("--check", action="store_true", help="Just check current usernames")
    args = parser.parse_args()

    if args.check:
        asyncio.run(check_usernames())
    else:
        asyncio.run(set_usernames(dry_run=args.dry))
