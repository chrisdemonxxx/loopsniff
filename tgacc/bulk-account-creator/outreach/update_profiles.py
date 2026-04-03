#!/usr/bin/env python3
"""Update bios and profile photos for all outreach TG accounts."""

import asyncio
import glob
import logging
import os
import random
import sys

from telethon import TelegramClient, functions
from telethon.tl.types import InputChatUploadedPhoto

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger(__name__)

SESSIONS_DIR = os.path.join(os.path.dirname(__file__), "data", "sessions")
PHOTO_PATH = "/tmp/adflux_logo_v2_512.png"

# API credentials (official Telegram Desktop)
API_ID = 2040
API_HASH = "b18441a1ff607e10a989891a5462e627"

BIOS = [
    "Digital media buyer | @addfluxmedia_bot 🚀 | adflux.store",
    "Ad accounts specialist | AdFlux Media team | adflux.store",
    "Media buyer & account manager 📊 | @addfluxmedia_bot | adflux.store",
    "Running ads since '22 | Agency accounts via @addfluxmedia_bot 🔥",
    "PPC specialist | Ad accounts & scaling 🎯 | adflux.store",
    "Performance marketer | Google, Meta, Bing | @addfluxmedia_bot",
    "Ad ops at AdFlux Media | adflux.store | Whitelisted accounts 🔥",
    "Helping media buyers scale 📈 | @addfluxmedia_bot | adflux.store",
    "Agency ad accounts for any niche | @addfluxmedia_bot 🚀",
    "Digital ads expert | Unlimited spend | adflux.store",
    "Paid traffic specialist 🎯 | @addfluxmedia_bot | adflux.store",
    "Ad account solutions | No bans, no limits | @addfluxmedia_bot",
    "Media buying pro | AdFlux Media 🚀 | adflux.store",
    "Scaling campaigns daily | @addfluxmedia_bot | adflux.store",
    "Performance marketing | Google/Meta/Bing accounts | adflux.store 📈",
]


async def update_account(session_path: str, dry_run: bool = False):
    """Update bio and photo for a single account."""
    phone = os.path.basename(session_path).replace(".session", "")
    bio = random.choice(BIOS)

    if dry_run:
        log.info("[DRY RUN] %s → bio: %s", phone, bio)
        return True

    try:
        client = TelegramClient(
            session_path.replace(".session", ""),
            API_ID, API_HASH,
            device_model="Samsung Galaxy S24",
            system_version="Android 14",
            app_version="10.14.5",
        )
        await client.connect()

        if not await client.is_user_authorized():
            log.warning("❌ %s — not authorized, skipping", phone)
            await client.disconnect()
            return False

        me = await client.get_me()
        log.info("✅ %s — connected as %s", phone, me.first_name)

        # Update bio
        await client(functions.account.UpdateProfileRequest(about=bio))
        log.info("   Bio updated: %s", bio[:50])

        # Update photo if exists
        if os.path.exists(PHOTO_PATH):
            photo = await client.upload_file(PHOTO_PATH)
            await client(functions.photos.UploadProfilePhotoRequest(file=photo))
            log.info("   Photo updated")

        await client.disconnect()
        return True

    except Exception as exc:
        log.error("❌ %s — error: %s", phone, exc)
        try:
            await client.disconnect()
        except:
            pass
        return False


async def main():
    dry_run = "--dry-run" in sys.argv
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None

    sessions = sorted(glob.glob(os.path.join(SESSIONS_DIR, "*.session")))
    if limit:
        sessions = sessions[:limit]

    log.info("Found %d sessions%s", len(sessions), " (DRY RUN)" if dry_run else "")

    success = 0
    failed = 0
    for i, session in enumerate(sessions):
        log.info("--- [%d/%d] ---", i + 1, len(sessions))
        ok = await update_account(session, dry_run=dry_run)
        if ok:
            success += 1
        else:
            failed += 1
        # Small delay between accounts
        if not dry_run and i < len(sessions) - 1:
            await asyncio.sleep(random.uniform(2, 5))

    log.info("Done: %d success, %d failed out of %d", success, failed, len(sessions))


if __name__ == "__main__":
    asyncio.run(main())
