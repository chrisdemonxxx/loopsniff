#!/usr/bin/env python3
"""Set up realistic Telegram profiles on all active outreach accounts.

Sets: first name, last name, bio (with AdFlux links), and profile picture.

Usage:
    python setup_profiles.py          # set up all active accounts
    python setup_profiles.py --dry    # preview without changes
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
import sys

sys.path.insert(0, "/home/cjs/tgacc/adflux-rag")

from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.functions.photos import UploadProfilePhotoRequest

from outreach import db
from outreach.session_manager import SessionManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("profile_setup")

# ── Profile data ────────────────────────────────────────────────────────────

ADFLUX_WEBSITE = "adflux.store"
ADFLUX_CHANNEL = "t.me/+J2wvrrrgV8ozMDFh"
ADFLUX_BOT = "t.me/addfluxmedia_bot"

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
]

BIOS = [
    f"AdFlux Media | Ad Accounts\n{ADFLUX_WEBSITE} | {ADFLUX_BOT}",
    f"Media Buyer @ AdFlux\n{ADFLUX_WEBSITE} | {ADFLUX_BOT}",
    f"Account Manager | AdFlux\n{ADFLUX_WEBSITE} | {ADFLUX_BOT}",
    f"Ad Accounts | AdFlux Media\n{ADFLUX_WEBSITE} | {ADFLUX_BOT}",
    f"Performance Marketing | AdFlux\n{ADFLUX_WEBSITE} | {ADFLUX_BOT}",
]

PICS_DIR = os.path.join(
    os.path.dirname(__file__), "outreach", "data", "profile_pics"
)


async def setup_profiles(dry_run: bool = False) -> None:
    await db.init_db()
    sm = SessionManager()

    accounts = await db.get_accounts()
    active = [a for a in accounts if a.status == "active"]

    log.info("Setting up profiles for %d active accounts...", len(active))

    pic_files = sorted(
        [f for f in os.listdir(PICS_DIR) if f.endswith(".jpg")],
    )

    success = 0
    for i, account in enumerate(active):
        profile = PROFILES[i % len(PROFILES)]
        bio = BIOS[i % len(BIOS)]
        pic_file = os.path.join(PICS_DIR, pic_files[i % len(pic_files)])

        first_name = profile["first"]
        last_name = profile["last"]

        log.info(
            "[%d/%d] %s → %s %s",
            i + 1, len(active), account.phone, first_name, last_name,
        )

        if dry_run:
            log.info("  DRY RUN: would set name=%s %s, bio=%s..., pic=%s",
                     first_name, last_name, bio[:40], pic_file)
            success += 1
            continue

        try:
            client = await sm.get_client(account.phone)
            try:
                if not await client.is_user_authorized():
                    log.warning("  %s not authorized — skipping", account.phone)
                    continue

                # Set name and bio
                try:
                    await client(UpdateProfileRequest(
                        first_name=first_name,
                        last_name=last_name,
                        about=bio,
                    ))
                    log.info("  ✅ Name & bio set: %s %s", first_name, last_name)
                except Exception as profile_exc:
                    err_msg = str(profile_exc)
                    if "frozen" in err_msg.lower():
                        log.warning("  ⚠️  Account %s is frozen — skipping profile update", account.phone)
                        continue
                    # Try just the name without bio
                    try:
                        await client(UpdateProfileRequest(
                            first_name=first_name,
                            last_name=last_name,
                        ))
                        log.info("  ✅ Name set (bio skipped): %s %s", first_name, last_name)
                    except Exception:
                        log.error("  ❌ Cannot set name for %s: %s", account.phone, profile_exc)
                        continue

                # Set profile picture
                if os.path.exists(pic_file):
                    try:
                        photo = await client.upload_file(pic_file)
                        await client(UploadProfilePhotoRequest(file=photo))
                        log.info("  ✅ Profile picture set: %s", os.path.basename(pic_file))
                    except Exception as pic_exc:
                        log.warning("  ⚠️  Photo upload failed for %s: %s", account.phone, pic_exc)

                success += 1

                # Brief delay between accounts to avoid rate limits
                await asyncio.sleep(random.uniform(2, 5))

            finally:
                await client.disconnect()

        except Exception as exc:
            log.error("  ❌ Failed for %s: %s", account.phone, exc)

    log.info("Profile setup complete: %d/%d accounts configured", success, len(active))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Set up TG profiles for AdFlux accounts")
    parser.add_argument("--dry", action="store_true", help="Preview without making changes")
    args = parser.parse_args()
    asyncio.run(setup_profiles(dry_run=args.dry))
