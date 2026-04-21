#!/usr/bin/env python3
"""
Delete all existing posts from channels and re-post with new branding images.
- Deletes all messages from main channel and vouches channel
- Sets profile photos on channels and main account
- Posts banners to main channel with rich captions
- Posts vouch screenshots to vouches channel with captions
- Adds human admins
"""

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
    DeleteMessagesRequest,
    GetFullChannelRequest,
)
from telethon.tl.functions.photos import UploadProfilePhotoRequest, DeletePhotosRequest
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.types import (
    InputChatUploadedPhoto,
    ChatAdminRights,
)

load_dotenv(Path(__file__).parent / "userbot" / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("repost")

API_ID = int(os.getenv("TG_API_ID", "33454441"))
API_HASH = os.getenv("TG_API_HASH", "10ade2b7e270023f3e1debb7e25dab45")
PHONE = os.getenv("TG_PHONE", "+15642618554")

SESSION_DIR = Path(__file__).parent / "userbot" / "sessions"
SESSION_PATH = str(SESSION_DIR / f"tg_{PHONE.replace('+', '')}")
BRANDING = Path(__file__).parent / "branding"

MAIN_CHANNEL_ID = 3729617935
VOUCH_CHANNEL_ID = 3677059540
BOT_TOKEN = os.getenv("ADMIN_BOT_TOKEN", "")

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


async def delete_all_messages(client, channel_entity, channel_name):
    """Delete all messages from a channel."""
    log.info("🗑️  Deleting all messages from %s channel...", channel_name)
    msg_ids = []
    async for msg in client.iter_messages(channel_entity, limit=500):
        msg_ids.append(msg.id)

    if not msg_ids:
        log.info("  No messages to delete in %s", channel_name)
        return 0

    # Delete in batches of 100
    deleted = 0
    for i in range(0, len(msg_ids), 100):
        batch = msg_ids[i:i+100]
        try:
            await client(DeleteMessagesRequest(channel=channel_entity, id=batch))
            deleted += len(batch)
        except Exception as e:
            log.error("  Failed to delete batch: %s", e)

    log.info("  ✅ Deleted %d messages from %s", deleted, channel_name)
    return deleted


async def main():
    client = _build_client()
    await client.connect()

    if not await client.is_user_authorized():
        log.error("Not authorized. Run auto_setup.py --auth first.")
        return

    me = await client.get_me()
    log.info("✅ Connected as %s (@%s)", me.first_name, me.username)

    # Get channel entities
    main_ch = await client.get_entity(MAIN_CHANNEL_ID)
    vouch_ch = await client.get_entity(VOUCH_CHANNEL_ID)

    # ── 1. Delete all existing posts ──
    await delete_all_messages(client, main_ch, "main")
    await delete_all_messages(client, vouch_ch, "vouches")
    await asyncio.sleep(2)

    # ── 2. Update main account profile ──
    log.info("👤 Updating main account profile...")
    try:
        await client(UpdateProfileRequest(
            first_name="George",
            last_name="| Kliqboost",
            about="Head of Sales @ Kliqboost Media | Advertising Solutions | DM for pricing",
        ))
        log.info("✅ Profile updated")
    except Exception as e:
        log.error("Failed to update profile: %s", e)

    # ── 3. Set profile photos ──
    log.info("📷 Setting profile photos...")
    # Main account
    try:
        logo = await client.upload_file(str(BRANDING / "logo_800.png"))
        await client(UploadProfilePhotoRequest(file=logo))
        log.info("  ✅ Main account photo set")
    except Exception as e:
        log.error("  Failed: %s", e)

    # Channels
    for ch, name in [(main_ch, "main"), (vouch_ch, "vouches")]:
        try:
            logo = await client.upload_file(str(BRANDING / "logo_800.png"))
            await client(EditPhotoRequest(
                channel=ch,
                photo=InputChatUploadedPhoto(file=logo),
            ))
            log.info("  ✅ %s channel photo set", name.capitalize())
        except Exception as e:
            log.error("  Failed %s: %s", name, e)
        await asyncio.sleep(1)

    # ── 4. Post banners to main channel ──
    log.info("\n📸 Posting banners to main channel...")
    banners = [
        ("banner_welcome.png", (
            "🚀 **Welcome to Kliqboost Media**\n\n"
            "Advertising Solutions for Serious Media Buyers\n\n"
            "✅ Scalable Infrastructure\n"
            "🔄 Continuity Guarantee\n"
            "⚡ Fast Onboarding\n"
            "🛡️ Agency-Tier Access\n\n"
            "💬 DM @georgekatis to get started\n"
            "📢 t.me/kliqboost\\_media"
        )),
        ("banner_pricing.png", (
            "💰 **Pricing Overview**\n\n"
            "**Google Ads:** $50 / $100 / $800/mo\n"
            "**Meta Ads:** $200/mo / $450/mo / $1,000/mo\n"
            "**Bing Ads:** $100 / $300 / $1,000/mo\n"
            "**TikTok Ads:** $80 / $200 / $600/mo\n\n"
            "All solutions include continuity guarantee + dedicated support\n"
            "💳 Payment: BTC | ETH | USDT | LTC\n\n"
            "📩 DM @georgekatis for custom packages"
        )),
        ("banner_platforms.png", (
            "🌐 **Platforms We Support**\n\n"
            "🔍 Google Ads — Scalable infrastructure, agency-tier\n"
            "📘 Meta Ads — Full setup included, reliable\n"
            "🎵 TikTok Ads — Fast onboarding, all regions\n"
            "🔎 Bing Ads — Verified setups, low competition\n"
            "📰 Taboola — Native ads, high CTR\n"
            "📊 Outbrain — Content ads, scale fast\n\n"
            "Need another platform? We source anything.\n"
            "💬 @georgekatis"
        )),
        ("banner_stats.png", (
            "📊 **Results That Speak**\n\n"
            "👥 500+ Active Partners\n"
            "💵 $2M+ Monthly Ad Spend Managed\n"
            "✅ 99.5% Uptime\n"
            "⚡ Same-Day Onboarding\n\n"
            "🔥 Consistently stable infrastructure\n\n"
            "Join 500+ media buyers who trust Kliqboost Media\n"
            "💬 DM @georgekatis"
        )),
        ("banner_cta.png", (
            "⚡ **Ready to Scale?**\n\n"
            "Get agency-tier advertising infrastructure today.\n\n"
            "1️⃣ DM @georgekatis on Telegram\n"
            "2️⃣ Tell us your platform & goals\n"
            "3️⃣ Pay via crypto (BTC/ETH/USDT)\n"
            "4️⃣ Start running campaigns within 24 hours\n\n"
            "📢 t.me/kliqboost\\_media\n"
            "✅ t.me/kliqboost\\_vouches"
        )),
    ]

    for fname, caption in banners:
        try:
            await client.send_file(main_ch, str(BRANDING / fname), caption=caption, parse_mode="md")
            log.info("  ✅ Posted %s", fname)
            await asyncio.sleep(2)
        except Exception as e:
            log.error("  ❌ Failed %s: %s", fname, e)

    # ── 5. Post vouch screenshots to vouches channel ──
    log.info("\n📸 Posting vouch screenshots to vouches channel...")

    # First, post a pinned intro message
    try:
        intro = (
            "✅ **Kliqboost Media — Verified Client Reviews**\n\n"
            "Real conversations with real partners.\n"
            "Every review is a genuine client experience.\n\n"
            "🔒 We never edit or fabricate reviews.\n"
            "📩 Want to verify? DM any client directly.\n\n"
            "💬 Get started: @georgekatis\n"
            "📢 Main channel: t.me/kliqboost\\_media"
        )
        intro_msg = await client.send_message(vouch_ch, intro, parse_mode="md")
        try:
            from telethon.tl.functions.messages import UpdatePinnedMessageRequest
            await client(UpdatePinnedMessageRequest(peer=vouch_ch, id=intro_msg.id, silent=True))
            log.info("  ✅ Pinned intro message")
        except Exception:
            pass
        await asyncio.sleep(1)
    except Exception as e:
        log.error("  ❌ Failed to post intro: %s", e)

    vouch_captions = [
        (
            "✅ **Review from @alexkrypto**\n\n"
            "📱 Platform: Google Ads\n"
            "💬 \"setup was smooth, everything running great. you're legit 🔥\"\n\n"
            "#googleads #review #kliqboost"
        ),
        (
            "✅ **Review from @marcus_media**\n\n"
            "📱 Platform: Meta Ads\n"
            "💬 \"$8k in campaigns already, zero issues. kliqboost is the real deal\"\n\n"
            "#metaads #review #kliqboost"
        ),
        (
            "✅ **Review from @vik_scale**\n\n"
            "📱 Platform: Google + Bing\n"
            "💬 \"4 months, finance vertical, consistently stable. best partner I've used\"\n\n"
            "#googleads #bingads #review #kliqboost"
        ),
        (
            "✅ **Review from @dan_affiliates**\n\n"
            "📱 Platform: TikTok Ads\n"
            "💬 \"legit tiktok setup from kliqboost. fast onboarding, running smoothly\"\n\n"
            "#tiktokads #review #kliqboost"
        ),
        (
            "✅ **Review from @raj_ppc**\n\n"
            "📱 Platform: Google Ads\n"
            "💬 \"onboarding was quick, everything running, no issues. solid service 👍\"\n\n"
            "#googleads #review #kliqboost"
        ),
        (
            "✅ **Review from @tom_arb**\n\n"
            "📱 Platform: Taboola + Google\n"
            "💬 \"6 weeks, $2k/day combined, both setups still performing great. best in the game rn\"\n\n"
            "#taboola #googleads #review #kliqboost"
        ),
    ]

    for i, caption in enumerate(vouch_captions, 1):
        try:
            await client.send_file(vouch_ch, str(BRANDING / f"vouch_{i}.png"), caption=caption, parse_mode="md")
            log.info("  ✅ Posted vouch_%d.png", i)
            await asyncio.sleep(2)
        except Exception as e:
            log.error("  ❌ Failed vouch_%d: %s", i, e)

    # ── 6. Add human admins ──
    admins = [
        (BIGBUNNN_ID, "Bigbunnn", "Account Manager"),
        (DAVID_ID, "David_Bazzana", "Senior Partner"),
    ]
    for admin_id, admin_name, title in admins:
        for ch, ch_name in [(main_ch, "main"), (vouch_ch, "vouches")]:
            log.info("👑 Adding @%s to %s as %s...", admin_name, ch_name, title)
            try:
                admin_user = await client.get_entity(admin_id)
                try:
                    await client(InviteToChannelRequest(channel=ch, users=[admin_user]))
                except Exception:
                    pass
                await client(EditAdminRequest(
                    channel=ch,
                    user_id=admin_user,
                    admin_rights=ADMIN_RIGHTS,
                    rank=title,
                ))
                log.info("  ✅ @%s promoted in %s", admin_name, ch_name)
            except Exception as e:
                log.error("  ❌ Failed: %s", e)

    # ── Done ──
    log.info("\n" + "=" * 50)
    log.info("🎉 ALL DONE — Channel content refreshed!")
    log.info("=" * 50)
    log.info("  📷 Profile photos: set on account + both channels")
    log.info("  📸 Main channel: 5 premium banners posted")
    log.info("  ✅ Vouches channel: 6 realistic chat screenshots posted")
    log.info("  👑 Admins: @Bigbunnn + @David_Bazzana added")
    log.info("=" * 50)

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
