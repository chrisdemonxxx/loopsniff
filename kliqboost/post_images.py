#!/usr/bin/env python3
"""Post images, set profile pics, update profile, add admins to Kliqboost channels."""

import asyncio
import os
import logging
from pathlib import Path

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.tl.functions.channels import (
    EditPhotoRequest,
    EditAdminRequest,
    InviteToChannelRequest,
)
from telethon.tl.functions.photos import UploadProfilePhotoRequest
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.types import (
    InputChatUploadedPhoto,
    ChatAdminRights,
)

load_dotenv(Path(__file__).parent / "userbot" / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("post_images")

API_ID = int(os.getenv("TG_API_ID", "33454441"))
API_HASH = os.getenv("TG_API_HASH", "10ade2b7e270023f3e1debb7e25dab45")
PHONE = os.getenv("TG_PHONE", "+15642618554")

SESSION_DIR = Path(__file__).parent / "userbot" / "sessions"
SESSION_PATH = str(SESSION_DIR / f"tg_{PHONE.replace('+', '')}")
BRANDING = Path(__file__).parent / "branding"

MAIN_CHANNEL_ID = 3729617935
VOUCH_CHANNEL_ID = 3677059540
BOT_TOKEN = os.getenv("ADMIN_BOT_TOKEN", "")

# Human admins
BIGBUNNN_ID = 6136131094
DAVID_ID = 8756787507

ADMIN_RIGHTS = ChatAdminRights(
    change_info=True,
    post_messages=True,
    edit_messages=True,
    delete_messages=True,
    ban_users=True,
    invite_users=True,
    pin_messages=True,
    add_admins=False,
    manage_call=True,
)


def _build_client() -> TelegramClient:
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    return TelegramClient(
        SESSION_PATH, API_ID, API_HASH,
        device_model="iPhone 15 Pro Max",
        system_version="iOS 17.4",
        app_version="11.8.2",
    )


async def main():
    client = _build_client()
    await client.connect()

    if not await client.is_user_authorized():
        log.error("Not authorized. Run auto_setup.py --auth first.")
        return

    me = await client.get_me()
    log.info("✅ Connected as %s (@%s)", me.first_name, me.username)

    # ── 1. Update main account profile ──
    log.info("👤 Updating main account profile...")
    try:
        await client(UpdateProfileRequest(
            first_name="George",
            last_name="| Kliqboost",
            about="Head of Sales @ Kliqboost Media | Advertising Solutions | DM for pricing",
        ))
        log.info("✅ Profile updated: George | Kliqboost — Head of Sales")
    except Exception as e:
        log.error("Failed to update profile: %s", e)

    # ── 2. Set main account profile photo ──
    log.info("📷 Setting main account profile photo...")
    try:
        logo = await client.upload_file(str(BRANDING / "logo_800.png"))
        await client(UploadProfilePhotoRequest(file=logo))
        log.info("✅ Main account profile photo set")
    except Exception as e:
        log.error("Failed to set account photo: %s", e)

    # ── 3. Set channel profile photos ──
    for channel_id, name in [(MAIN_CHANNEL_ID, "main"), (VOUCH_CHANNEL_ID, "vouches")]:
        log.info("📷 Setting %s channel profile photo...", name)
        try:
            channel = await client.get_entity(channel_id)
            logo = await client.upload_file(str(BRANDING / "logo_800.png"))
            await client(EditPhotoRequest(
                channel=channel,
                photo=InputChatUploadedPhoto(file=logo),
            ))
            log.info("✅ %s channel photo set", name.capitalize())
        except Exception as e:
            log.error("Failed to set %s channel photo: %s", name, e)

    # ── 4. Set bot profile photo via Bot API ──
    if BOT_TOKEN:
        log.info("🤖 Setting bot profile photo...")
        try:
            import aiohttp
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/setMyPhoto"
            async with aiohttp.ClientSession() as session:
                with open(BRANDING / "logo_400.png", "rb") as f:
                    form = aiohttp.FormData()
                    form.add_field("photo", f, filename="logo.png", content_type="image/png")
                    async with session.post(url, data=form) as resp:
                        result = await resp.json()
                        if result.get("ok"):
                            log.info("✅ Bot profile photo set")
                        else:
                            log.warning("Bot photo API: %s", result)
        except Exception as e:
            log.error("Failed to set bot photo: %s", e)

    # ── 5. Post banners to main channel ──
    log.info("📸 Posting banners to main channel...")
    main_ch = await client.get_entity(MAIN_CHANNEL_ID)
    banners = [
        ("banner_welcome.png", "🚀 Kliqboost Media — Advertising Solutions for Serious Media Buyers"),
        ("banner_pricing.png", "💰 Transparent pricing. No hidden fees. Crypto accepted."),
        ("banner_platforms.png", "🌐 Google • Meta • TikTok • Bing • Taboola • Outbrain"),
        ("banner_stats.png", "📊 500+ active partners. $2M+ monthly ad spend. 99.5% uptime."),
        ("banner_cta.png", "⚡ Ready to scale? DM @georgekatis to get started"),
    ]
    for fname, caption in banners:
        try:
            await client.send_file(main_ch, str(BRANDING / fname), caption=caption)
            log.info("  ✅ Posted %s", fname)
            await asyncio.sleep(1)
        except Exception as e:
            log.error("  ❌ Failed %s: %s", fname, e)

    # ── 6. Post vouch cards to vouches channel ──
    log.info("📸 Posting vouch cards to vouches channel...")
    vouch_ch = await client.get_entity(VOUCH_CHANNEL_ID)
    vouch_captions = [
        "✅ @crypto_scalr — Google Ads, 3 months, consistently stable. $150K+ spent.",
        "✅ @mediabuyer_rx — Meta Ads, 6 months. 20 setups, $50K/day capacity.",
        "✅ @scale_ninja — Google + Bing, 4 months. Finance vertical, rock solid.",
        "✅ @affking_eu — TikTok + Meta, 5 months. Same-day onboarding.",
        "✅ @ppc_trader — Google Ads, 2 months. Verified setup, fast onboarding.",
        "✅ @content_arb — Taboola + Google, 1 month. Running campaigns in 24 hours.",
    ]
    for i, caption in enumerate(vouch_captions, 1):
        try:
            await client.send_file(vouch_ch, str(BRANDING / f"vouch_{i}.png"), caption=caption)
            log.info("  ✅ Posted vouch_%d.png", i)
            await asyncio.sleep(1)
        except Exception as e:
            log.error("  ❌ Failed vouch_%d: %s", i, e)

    # ── 7. Add human admins to channels ──
    admins = [
        (BIGBUNNN_ID, "Bigbunnn", "Account Manager"),
        (DAVID_ID, "David_Bazzana", "Senior Partner"),
    ]
    for admin_id, admin_name, title in admins:
        for channel_id, ch_name in [(MAIN_CHANNEL_ID, "main"), (VOUCH_CHANNEL_ID, "vouches")]:
            log.info("👑 Adding @%s to %s channel as %s...", admin_name, ch_name, title)
            try:
                channel = await client.get_entity(channel_id)
                admin_user = await client.get_entity(admin_id)
                # First invite
                try:
                    await client(InviteToChannelRequest(channel=channel, users=[admin_user]))
                except Exception:
                    pass  # Already in channel
                # Then promote
                await client(EditAdminRequest(
                    channel=channel,
                    user_id=admin_user,
                    admin_rights=ADMIN_RIGHTS,
                    rank=title,
                ))
                log.info("  ✅ @%s promoted as %s in %s", admin_name, title, ch_name)
            except Exception as e:
                log.error("  ❌ Failed to add @%s to %s: %s", admin_name, ch_name, e)

    # ── Done ──
    log.info("\n🎉 ALL DONE!")
    log.info("  Profile: George | Kliqboost — Head of Sales")
    log.info("  Photos: set on account, main channel, vouches channel, bot")
    log.info("  Banners: 5 posted to main channel")
    log.info("  Vouches: 6 cards posted to vouches channel")
    log.info("  Admins: @Bigbunnn (Account Manager) + @David_Bazzana (Senior Partner)")

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
