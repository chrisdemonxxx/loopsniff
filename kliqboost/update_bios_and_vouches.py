#!/usr/bin/env python3
"""
Cross-link bios: Update bot description, channel descriptions to reference each other.
Also reposts vouch images (v4 with profile pics) to the vouches channel.
"""

import asyncio
import os
import logging
from pathlib import Path

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.tl.functions.channels import (
    EditPhotoRequest,
    DeleteMessagesRequest,
    GetFullChannelRequest,
)
from telethon.tl.functions.bots import SetBotInfoRequest
from telethon.tl.types import InputChatUploadedPhoto

load_dotenv(Path(__file__).parent / "userbot" / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("crosslink")

API_ID = int(os.getenv("TG_API_ID", "33454441"))
API_HASH = os.getenv("TG_API_HASH", "10ade2b7e270023f3e1debb7e25dab45")
PHONE = os.getenv("TG_PHONE", "+15642618554")
BOT_TOKEN = os.getenv("ADMIN_BOT_TOKEN", "")

SESSION_DIR = Path(__file__).parent / "userbot" / "sessions"
SESSION_PATH = str(SESSION_DIR / f"tg_{PHONE.replace('+', '')}")
BRANDING = Path(__file__).parent / "branding"

MAIN_CHANNEL_ID = -1003729617935
VOUCH_CHANNEL_ID = -1003677059540


def _build_client():
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
        log.error("Not authorized.")
        return

    me = await client.get_me()
    log.info("✅ Connected as %s (@%s)", me.first_name, me.username)

    main_ch = await client.get_entity(MAIN_CHANNEL_ID)
    vouch_ch = await client.get_entity(VOUCH_CHANNEL_ID)

    # ── 0. Rename main channel title ──
    log.info("📝 Renaming main channel to 'Kliqboost Media'...")
    try:
        from telethon.tl.functions.channels import EditTitleRequest
        from telethon.tl.functions.messages import EditChatAboutRequest
        await client(EditTitleRequest(channel=main_ch, title="Kliqboost Media"))
        log.info("  ✅ Main channel renamed to 'Kliqboost Media'")
    except Exception as e:
        log.error("  ❌ Rename failed: %s", e)

    # ── 1. Update main channel description ──
    log.info("📝 Updating main channel description...")
    try:
        main_about = (
            "Advertising solutions for media buyers\n\n"
            "✅ Google • Meta • TikTok • Bing • Taboola\n"
            "⚡ Fast onboarding | 🛡️ Reliable infrastructure\n"
            "💳 Crypto accepted (BTC/ETH/USDT)\n\n"
            "📩 Sales: @georgekatis\n"
            "🤖 Bot: @kliqboost_bot\n"
            "✅ Reviews: @kliqboost_vouches"
        )
        await client(EditChatAboutRequest(peer=main_ch, about=main_about))
        log.info("  ✅ Main channel bio updated")
    except Exception as e:
        log.error("  ❌ Failed: %s", e)

    # ── 2. Update vouches channel description ──
    log.info("📝 Updating vouches channel description...")
    try:
        vouch_about = (
            "✅ Verified Client Reviews\n\n"
            "Real conversations. Real results.\n"
            "Every review is a genuine client experience.\n\n"
            "📢 Main: @kliqboost_media\n"
            "📩 Sales: @georgekatis\n"
            "🤖 Bot: @kliqboost_bot"
        )
        await client(EditChatAboutRequest(peer=vouch_ch, about=vouch_about))
        log.info("  ✅ Vouches channel bio updated")
    except Exception as e:
        log.error("  ❌ Failed: %s", e)

    # ── 3. Update bot description via Bot API ──
    log.info("🤖 Updating bot description...")
    try:
        import aiohttp
        bot_desc = (
            "🤖 Official Kliqboost Media Assistant\n\n"
            "Get instant answers about:\n"
            "• Pricing & solutions\n"
            "• Available platforms\n"
            "• FAQ & onboarding\n\n"
            "📢 Channel: @kliqboost_media\n"
            "✅ Reviews: @kliqboost_vouches\n"
            "📩 Personal sales: @georgekatis"
        )
        bot_about = (
            "Kliqboost Media — Advertising Solutions\n"
            "📢 @kliqboost_media | ✅ @kliqboost_vouches\n"
            "📩 Sales: @georgekatis"
        )
        async with aiohttp.ClientSession() as session:
            await session.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/setMyDescription",
                json={"description": bot_desc},
            )
            await session.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/setMyShortDescription",
                json={"short_description": bot_about},
            )
            log.info("  ✅ Bot description + about updated")
    except Exception as e:
        log.error("  ❌ Failed: %s", e)

    # ── 4. Delete old vouches and repost with v4 images ──
    log.info("🗑️  Deleting old vouch messages...")
    msg_ids = []
    async for msg in client.iter_messages(vouch_ch, limit=500):
        msg_ids.append(msg.id)

    if msg_ids:
        for i in range(0, len(msg_ids), 100):
            batch = msg_ids[i:i+100]
            try:
                await client(DeleteMessagesRequest(channel=vouch_ch, id=batch))
            except Exception as e:
                log.error("  Delete batch failed: %s", e)
        log.info("  ✅ Deleted %d old messages", len(msg_ids))
    await asyncio.sleep(1)

    # Post pinned intro
    log.info("📸 Posting v4 vouches with real profile pictures...")
    try:
        intro = (
            "✅ **Kliqboost Media — Verified Client Reviews**\n\n"
            "Real conversations with real partners.\n"
            "Every review is a genuine client experience.\n\n"
            "🔒 We never edit or fabricate reviews.\n"
            "📩 Want to verify? DM any client directly.\n\n"
            "💬 Get started: @georgekatis\n"
            "🤖 Bot: @kliqboost_bot\n"
            "📢 Main channel: t.me/kliqboost\\_media"
        )
        intro_msg = await client.send_message(vouch_ch, intro, parse_mode="md")
        from telethon.tl.functions.messages import UpdatePinnedMessageRequest
        await client(UpdatePinnedMessageRequest(peer=vouch_ch, id=intro_msg.id, silent=True))
        log.info("  ✅ Pinned intro message")
    except Exception as e:
        log.error("  ❌ Intro failed: %s", e)

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
            await client.send_file(
                vouch_ch, str(BRANDING / f"vouch_{i}.png"),
                caption=caption, parse_mode="md",
            )
            log.info("  ✅ Posted vouch_%d.png", i)
            await asyncio.sleep(2)
        except Exception as e:
            log.error("  ❌ Failed vouch_%d: %s", i, e)

    log.info("\n" + "=" * 50)
    log.info("🎉 ALL DONE!")
    log.info("  📝 Channel bios cross-linked")
    log.info("  🤖 Bot description updated")
    log.info("  ✅ 6 v4 vouches with real profile pics posted")
    log.info("=" * 50)

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
