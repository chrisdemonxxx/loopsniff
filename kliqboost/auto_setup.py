#!/usr/bin/env python3
"""Kliqboost Auto Setup — creates channels, bot, posts content.

Usage:
    python auto_setup.py --auth       # Authenticate (paste OTP)
    python auto_setup.py --setup      # Run full setup
    python auto_setup.py --test       # Verify connection only
"""

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.tl.functions.channels import (
    CreateChannelRequest,
    EditPhotoRequest,
    EditTitleRequest,
)
from telethon.tl.functions.messages import (
    ExportChatInviteRequest,
    UpdatePinnedMessageRequest,
)
from telethon.tl.types import (
    InputChatUploadedPhoto,
    ChatAdminRights,
)

load_dotenv(Path(__file__).parent / "userbot" / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("setup")

# ── Config ──────────────────────────────────────────────────────────────────

API_ID = int(os.getenv("TG_API_ID", "33454441"))
API_HASH = os.getenv("TG_API_HASH", "10ade2b7e270023f3e1debb7e25dab45")
PHONE = os.getenv("TG_PHONE", "+15642618554")

BRAND = "Kliqboost"
BRAND_LOWER = "kliqboost"

SESSION_DIR = Path(__file__).parent / "userbot" / "sessions"
SESSION_PATH = str(SESSION_DIR / f"tg_{PHONE.replace('+', '')}")


def _build_client() -> TelegramClient:
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    return TelegramClient(
        SESSION_PATH,
        API_ID,
        API_HASH,
        device_model="iPhone 15 Pro Max",
        system_version="iOS 17.4",
        app_version="11.8.2",
        lang_code="en",
        system_lang_code="en-US",
    )


# ── Channel Content ────────────────────────────────────────────────────────

MAIN_CHANNEL_POSTS = [
    (
        f"🚀 Welcome to {BRAND}!\n\n"
        f"Premium ad accounts for serious media buyers.\n"
        f"Google • Meta • TikTok • Taboola • Outbrain\n\n"
        f"✅ Whitelisted agency accounts\n"
        f"✅ No spend limits\n"
        f"✅ Free replacements\n"
        f"✅ 24/7 dedicated support\n\n"
        f"DM us to get started → @{BRAND_LOWER}"
    ),
    (
        f"💰 {BRAND} Pricing Overview\n\n"
        f"🔹 Google Ads\n"
        f"  Basic: $50/acct | Pro: $100/acct | Enterprise: $800/mo\n\n"
        f"🔹 Meta Ads\n"
        f"  Basic: $200/mo | Pro: $450/mo | Enterprise: $1000/mo\n\n"
        f"🔹 Bing Ads\n"
        f"  Basic: $100/acct | Pro: $300/acct | Enterprise: $1000/mo\n\n"
        f"🔹 Taboola/Outbrain\n"
        f"  Basic: $50/acct | Pro: $100/acct | Enterprise: $800/mo\n\n"
        f"All plans include dedicated support + free replacements 🔥"
    ),
    (
        f"🏆 Why choose {BRAND}?\n\n"
        f"1. Agency-level accounts — not personal throwaway accounts\n"
        f"2. Verified BMs with spending history\n"
        f"3. Same-day replacement if anything goes wrong\n"
        f"4. Works for all verticals: crypto, nutra, finance, sweeps\n"
        f"5. Accept crypto payments (BTC, ETH, USDT)\n\n"
        f"We've helped 500+ media buyers scale without interruption."
    ),
    (
        f"📊 Case Study: Crypto Advertiser\n\n"
        f"Client: Mid-size crypto exchange\n"
        f"Challenge: Getting banned every 3 days on personal accounts\n"
        f"Solution: {BRAND} Pro Google Ads accounts\n\n"
        f"Results:\n"
        f"• 0 bans in 90 days\n"
        f"• $150K+ monthly spend maintained\n"
        f"• 40% lower CPA vs. rotating personal accounts\n"
        f"• ROI: 12x on ad account investment"
    ),
    (
        f"📊 Case Study: Nutra/Health Affiliate\n\n"
        f"Client: Solo affiliate, health supplements\n"
        f"Challenge: Meta keeps rejecting ads, 4 BMs disabled\n"
        f"Solution: {BRAND} Enterprise Meta package\n\n"
        f"Results:\n"
        f"• 3 BMs with 20+ ad accounts each\n"
        f"• $50K/day spend capacity\n"
        f"• Approval rate jumped from 30% to 85%\n"
        f"• 6 months, zero account shutdowns"
    ),
    (
        f"❓ FAQ\n\n"
        f"Q: How fast do I get my accounts?\n"
        f"A: 24-48 hours after payment.\n\n"
        f"Q: What if my account gets banned?\n"
        f"A: Free replacement, same day. That's the whole point.\n\n"
        f"Q: Do you accept crypto?\n"
        f"A: Yes — BTC, ETH, USDT, other major coins.\n\n"
        f"Q: Can I see references?\n"
        f"A: Check our vouches channel → @{BRAND_LOWER}_vouches"
    ),
    (
        f"🌐 Platforms We Support\n\n"
        f"✅ Google Ads — Search, Display, YouTube, Shopping\n"
        f"✅ Meta Ads — Facebook, Instagram\n"
        f"✅ TikTok Ads — Full funnel campaigns\n"
        f"✅ Bing/Microsoft Ads — Search, Shopping\n"
        f"✅ Taboola — Native advertising\n"
        f"✅ Outbrain — Content discovery\n"
        f"✅ Mediago — Cross-platform native\n\n"
        f"Need something else? DM us, we'll figure it out."
    ),
    (
        f"🔐 How {BRAND} Works\n\n"
        f"1️⃣ DM us your requirements (platform, budget, niche)\n"
        f"2️⃣ We match you with the right account tier\n"
        f"3️⃣ Pay via crypto (BTC/ETH/USDT)\n"
        f"4️⃣ Receive your account access within 24-48h\n"
        f"5️⃣ Start running ads immediately\n"
        f"6️⃣ If any issues → free replacement, same day\n\n"
        f"Simple. Fast. Reliable. 💪"
    ),
]

VOUCH_POSTS = [
    (
        f"✅ Vouch from @crypto_whale_23\n\n"
        f"\"Been using {BRAND} for 3 months now. Google Ads Pro plan. "
        f"Zero bans, zero downtime. Best provider I've worked with.\"\n\n"
        f"Platform: Google Ads | Plan: Pro | Duration: 3 months"
    ),
    (
        f"✅ Vouch from @media_buyer_king\n\n"
        f"\"Switched from my old provider after getting burned twice. "
        f"{BRAND} delivered same day. Accounts are legit, support is fast.\"\n\n"
        f"Platform: Meta Ads | Plan: Enterprise | Duration: 2 months"
    ),
    (
        f"✅ Vouch from @affiliate_pro_rx\n\n"
        f"\"Running nutra offers on Meta. {BRAND} Enterprise plan. "
        f"20 ad accounts across 3 BMs, $50K/day spend. No issues.\"\n\n"
        f"Platform: Meta Ads | Plan: Enterprise | Duration: 6 months"
    ),
    (
        f"✅ Vouch from @scale_master_44\n\n"
        f"\"Google Ads for finance niche. Got banned on personal accts weekly. "
        f"With {BRAND} Pro — zero bans in 4 months. Worth every penny.\"\n\n"
        f"Platform: Google Ads | Plan: Pro | Duration: 4 months"
    ),
    (
        f"✅ Vouch from @digital_nomad_ua\n\n"
        f"\"Needed Taboola + Google combo for content arbitrage. "
        f"{BRAND} set me up in 24 hours. Great communication via TG.\"\n\n"
        f"Platform: Google + Taboola | Plan: Basic | Duration: 1 month"
    ),
    (
        f"✅ Vouch from @sweep_runner_88\n\n"
        f"\"Running sweepstakes on TikTok + Meta. {BRAND} handles replacements "
        f"same day. Support DMs back within minutes. Solid team.\"\n\n"
        f"Platform: TikTok + Meta | Plan: Pro | Duration: 5 months"
    ),
]


# ── BotFather Interaction ──────────────────────────────────────────────────

async def _create_bot_via_botfather(client: TelegramClient) -> str | None:
    """Create a bot via @BotFather and return the token."""
    import re

    botfather = await client.get_entity("@BotFather")

    # Send /newbot
    await client.send_message(botfather, "/newbot")
    await asyncio.sleep(3)

    # Get response asking for name
    msgs = await client.get_messages(botfather, limit=1)
    log.info("BotFather: %s", msgs[0].text[:100] if msgs else "no response")

    # Send bot display name
    await client.send_message(botfather, f"{BRAND} Manager")
    await asyncio.sleep(3)

    # Get response asking for username
    msgs = await client.get_messages(botfather, limit=1)
    log.info("BotFather: %s", msgs[0].text[:100] if msgs else "no response")

    # Send bot username
    await client.send_message(botfather, f"{BRAND_LOWER}_bot")
    await asyncio.sleep(3)

    # Get response with token
    msgs = await client.get_messages(botfather, limit=1)
    response = msgs[0].text if msgs else ""
    log.info("BotFather: %s", response[:200])

    # Extract token
    token_match = re.search(r"(\d+:[A-Za-z0-9_-]+)", response)
    if token_match:
        token = token_match.group(1)
        log.info("✅ Bot token obtained: %s...%s", token[:10], token[-5:])
        return token
    else:
        log.warning("⚠️ Could not extract token. BotFather response: %s", response)
        return None


# ── Main Setup ─────────────────────────────────────────────────────────────

async def authenticate():
    """Interactive auth — sends OTP to phone."""
    client = _build_client()
    try:
        await client.connect()
        if await client.is_user_authorized():
            me = await client.get_me()
            log.info("✅ Already authorized as %s (@%s)", me.first_name, me.username)
            return

        log.info("Sending code to %s...", PHONE)
        await client.send_code_request(PHONE)
        code = input(f"Enter the code sent to {PHONE}: ").strip()
        await client.sign_in(PHONE, code)
        me = await client.get_me()
        log.info("✅ Authenticated as %s (@%s, id=%s)", me.first_name, me.username, me.id)
    finally:
        await client.disconnect()


async def run_setup():
    """Full automated setup: channels, bot, content."""
    client = _build_client()
    await client.connect()

    if not await client.is_user_authorized():
        log.error("Not authorized. Run with --auth first.")
        await client.disconnect()
        return

    me = await client.get_me()
    log.info("✅ Connected as %s (@%s)", me.first_name, me.username)

    results = {}

    # ── 1. Create Main Channel ──────────────────────────────────────────
    log.info("📢 Creating main channel: @%s_media", BRAND_LOWER)
    try:
        main_ch = await client(CreateChannelRequest(
            title=f"{BRAND} — Premium Ad Accounts",
            about=(
                f"{BRAND} provides whitelisted agency ad accounts for Google, Meta, "
                f"TikTok, Taboola, Outbrain. No spend limits. Free replacements. "
                f"DM @{BRAND_LOWER} to get started."
            ),
            megagroup=False,
        ))
        main_channel = main_ch.chats[0]
        results["main_channel_id"] = main_channel.id
        log.info("✅ Main channel created (id=%d)", main_channel.id)

        # Post content
        for i, post in enumerate(MAIN_CHANNEL_POSTS):
            msg = await client.send_message(main_channel, post)
            if i == 0:
                try:
                    await client.pin_message(main_channel, msg)
                except Exception:
                    pass
            await asyncio.sleep(1)
        log.info("✅ Posted %d messages to main channel", len(MAIN_CHANNEL_POSTS))

    except Exception as e:
        log.error("❌ Failed to create main channel: %s", e)
        results["main_channel_error"] = str(e)

    # ── 2. Create Vouches Channel ───────────────────────────────────────
    log.info("📢 Creating vouches channel: @%s_vouches", BRAND_LOWER)
    try:
        vouch_ch = await client(CreateChannelRequest(
            title=f"{BRAND} — Client Reviews",
            about=(
                f"Real reviews from {BRAND} clients. "
                f"Main channel: @{BRAND_LOWER}_media | DM: @{BRAND_LOWER}"
            ),
            megagroup=False,
        ))
        vouch_channel = vouch_ch.chats[0]
        results["vouch_channel_id"] = vouch_channel.id
        log.info("✅ Vouches channel created (id=%d)", vouch_channel.id)

        # Post vouches
        for i, post in enumerate(VOUCH_POSTS):
            msg = await client.send_message(vouch_channel, post)
            if i == 0:
                try:
                    await client.pin_message(vouch_channel, msg)
                except Exception:
                    pass
            await asyncio.sleep(1)
        log.info("✅ Posted %d vouches", len(VOUCH_POSTS))

    except Exception as e:
        log.error("❌ Failed to create vouches channel: %s", e)
        results["vouch_channel_error"] = str(e)

    # ── 3. Create Bot via BotFather ─────────────────────────────────────
    log.info("🤖 Creating bot via @BotFather: @%s_bot", BRAND_LOWER)
    bot_token = await _create_bot_via_botfather(client)
    if bot_token:
        results["bot_token"] = bot_token
        # Update bot .env
        env_path = Path(__file__).parent / "bot" / ".env"
        env_content = (
            f"BOT_TOKEN={bot_token}\n"
            f"ADMIN_CHAT_ID={me.id}\n"
            f"ADMIN_USERNAME=@{me.username or BRAND_LOWER}\n"
            f"BOT_USERNAME=@{BRAND_LOWER}_bot\n"
            f"API_BASE_URL=http://localhost:8099\n"
            f"API_TOKEN=\n"
            f"OLLAMA_CLOUD_URL=https://ollama.com/v1/chat/completions\n"
            f"OLLAMA_CLOUD_API_KEY={os.getenv('OLLAMA_CLOUD_API_KEY', '')}\n"
            f"OLLAMA_MODEL=kimi-k2:1t\n"
        )
        env_path.write_text(env_content)
        log.info("✅ Bot .env written to %s", env_path)

        # Update userbot .env with admin bot token
        userbot_env = Path(__file__).parent / "userbot" / ".env"
        content = userbot_env.read_text()
        content = content.replace("ADMIN_BOT_TOKEN=", f"ADMIN_BOT_TOKEN={bot_token}")
        content = content.replace("ADMIN_CHAT_ID=", f"ADMIN_CHAT_ID={me.id}")
        userbot_env.write_text(content)
        log.info("✅ Userbot .env updated with bot token")
    else:
        log.warning("⚠️ Bot creation failed — you may need to create manually")

    # ── 4. Summary ──────────────────────────────────────────────────────
    log.info("\n" + "=" * 60)
    log.info("🎉 SETUP COMPLETE — %s", BRAND)
    log.info("=" * 60)
    log.info("Account: %s (@%s, id=%s)", me.first_name, me.username, me.id)
    if "main_channel_id" in results:
        log.info("Main channel: id=%d", results["main_channel_id"])
    if "vouch_channel_id" in results:
        log.info("Vouches channel: id=%d", results["vouch_channel_id"])
    if "bot_token" in results:
        log.info("Bot token: %s...%s", results["bot_token"][:10], results["bot_token"][-5:])
    log.info("=" * 60)
    log.info("\nNext steps:")
    log.info("  1. Set channel usernames manually in TG app:")
    log.info("     Main → @%s_media", BRAND_LOWER)
    log.info("     Vouches → @%s_vouches", BRAND_LOWER)
    log.info("  2. Start manager bot: cd bot && python bot.py")
    log.info("  3. Start AI userbot: cd userbot && python admin_autoresponder.py")
    log.info("  4. Create ads at ads.telegram.org")

    await client.disconnect()


async def test_connection():
    """Verify connection only."""
    client = _build_client()
    await client.connect()
    if not await client.is_user_authorized():
        log.error("Not authorized. Run with --auth first.")
        await client.disconnect()
        return
    me = await client.get_me()
    log.info("✅ Connected as %s (@%s, id=%s)", me.first_name, me.username, me.id)
    await client.disconnect()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=f"{BRAND} Auto Setup")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--auth", action="store_true", help="Authenticate (paste OTP)")
    group.add_argument("--setup", action="store_true", help="Run full setup")
    group.add_argument("--test", action="store_true", help="Test connection")
    args = parser.parse_args()

    if args.auth:
        asyncio.run(authenticate())
    elif args.setup:
        asyncio.run(run_setup())
    else:
        asyncio.run(test_connection())
