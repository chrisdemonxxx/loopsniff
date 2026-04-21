#!/usr/bin/env python3
"""Qualification Bot — Bot API layer for the TG Ads funnel.

This bot is the FIRST touchpoint for users coming from TG ads.
The ad links to either:
  a) The channel (user joins → bot DMs via channel welcome)
  b) The bot directly (t.me/YourBot?start=ad_campaign_id)

Flow:
  1. User starts bot → Welcome message + inline keyboard
  2. Platform selection → Budget range → Timeline
  3. Based on BANT score:
     - Hot (≥75): Immediate handoff to userbot (DM from "Chris")
     - Warm (50-74): More info + handoff
     - Cool (<50): Nurture sequence via bot
  4. All leads written to shared SQLite for userbot pickup

Usage:
    python qualification_bot.py
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import lead_db
from system_prompts import (
    BOT_WELCOME_EN,
    BOT_WELCOME_RU,
    HANDOFF_EN,
    HANDOFF_RU,
    PLATFORM_QUESTION_EN,
    BUDGET_QUESTION_EN,
    TIMELINE_QUESTION_EN,
)

log = logging.getLogger(__name__)
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# ── Config ──────────────────────────────────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
DB_PATH = os.getenv("DB_PATH", str(Path(__file__).parent / "funnel_leads.db"))
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "kliqboost_chris")

# Wire up RAG for BANT scoring
RAG_PATH = os.getenv("RAG_PATH", "/home/cjs/kliqboost/rag")
OUTREACH_PATH = os.getenv("OUTREACH_PATH", "/home/cjs/kliqboost")
sys.path.insert(0, RAG_PATH)
sys.path.insert(0, OUTREACH_PATH)

try:
    from outreach.scoring.bant_scorer import BANTScorer
    scorer = BANTScorer()
except ImportError:
    scorer = None
    log.warning("BANTScorer not available — using basic scoring")


# ═══════════════════════════════════════════════════════════════════════════
# Inline Keyboards
# ═══════════════════════════════════════════════════════════════════════════

PLATFORM_KEYBOARD = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("Google Ads", callback_data="platform_google"),
        InlineKeyboardButton("Meta/FB Ads", callback_data="platform_meta"),
    ],
    [
        InlineKeyboardButton("Bing Ads", callback_data="platform_bing"),
        InlineKeyboardButton("Taboola", callback_data="platform_taboola"),
    ],
    [
        InlineKeyboardButton("Multiple", callback_data="platform_multiple"),
        InlineKeyboardButton("Other", callback_data="platform_other"),
    ],
])

BUDGET_KEYBOARD = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("< $1K/mo", callback_data="budget_lt1k"),
        InlineKeyboardButton("$1K–$5K/mo", callback_data="budget_1k5k"),
    ],
    [
        InlineKeyboardButton("$5K–$10K/mo", callback_data="budget_5k10k"),
        InlineKeyboardButton("$10K–$50K/mo", callback_data="budget_10k50k"),
    ],
    [
        InlineKeyboardButton("$50K+/mo", callback_data="budget_50k"),
    ],
])

TIMELINE_KEYBOARD = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("ASAP / Today", callback_data="timeline_asap"),
        InlineKeyboardButton("This week", callback_data="timeline_week"),
    ],
    [
        InlineKeyboardButton("This month", callback_data="timeline_month"),
        InlineKeyboardButton("Just exploring", callback_data="timeline_exploring"),
    ],
])

PLAN_KEYBOARD = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("📋 See Pricing", callback_data="show_pricing"),
        InlineKeyboardButton("💬 Talk to Manager", callback_data="talk_manager"),
    ],
    [
        InlineKeyboardButton("📊 View Case Studies", callback_data="case_studies"),
    ],
])


# ═══════════════════════════════════════════════════════════════════════════
# Callback Data Mappings
# ═══════════════════════════════════════════════════════════════════════════

PLATFORM_MAP = {
    "platform_google": "google",
    "platform_meta": "meta",
    "platform_bing": "bing",
    "platform_taboola": "taboola",
    "platform_multiple": "multiple",
    "platform_other": "other",
}

BUDGET_MAP = {
    "budget_lt1k": "< $1k",
    "budget_1k5k": "$1k-$5k",
    "budget_5k10k": "$5k-$10k",
    "budget_10k50k": "$10k-$50k",
    "budget_50k": "$50k+",
}

TIMELINE_MAP = {
    "timeline_asap": "asap",
    "timeline_week": "this_week",
    "timeline_month": "this_month",
    "timeline_exploring": "exploring",
}


# ═══════════════════════════════════════════════════════════════════════════
# Handlers
# ═══════════════════════════════════════════════════════════════════════════

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start — first interaction from TG ad click."""
    user = update.effective_user
    if not user:
        return

    # Track campaign source from deep link (/start=campaign_id)
    source = "tg_ad"
    if context.args:
        source = f"tg_ad_{context.args[0]}"

    # Upsert lead
    await lead_db.upsert_lead(
        DB_PATH,
        user_id=user.id,
        username=user.username.lower() if user.username else None,
        first_name=user.first_name or "",
        language=user.language_code or "en",
        source=source,
    )

    # Initialize user data for the qualification flow
    context.user_data["step"] = "platform"
    context.user_data["platform"] = None
    context.user_data["budget"] = None
    context.user_data["timeline"] = None

    log.info("New lead: @%s (id=%d) from %s", user.username, user.id, source)

    await update.message.reply_text(
        BOT_WELCOME_EN,
        reply_markup=PLATFORM_KEYBOARD,
    )


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline keyboard button presses."""
    query = update.callback_query
    if not query or not query.data:
        return
    await query.answer()

    user = update.effective_user
    data = query.data

    # ── Platform selection ───────────────────────────────────────────────
    if data.startswith("platform_"):
        platform = PLATFORM_MAP.get(data, "other")
        context.user_data["platform"] = platform
        context.user_data["step"] = "budget"

        await lead_db.save_lead_memory(DB_PATH, user.id, {
            "platform_interest": platform,
        })

        await query.edit_message_text(
            f"Great choice! 👍 {platform.title()} it is.\n\n{BUDGET_QUESTION_EN}",
            reply_markup=BUDGET_KEYBOARD,
        )
        return

    # ── Budget selection ─────────────────────────────────────────────────
    if data.startswith("budget_"):
        budget = BUDGET_MAP.get(data, "unknown")
        context.user_data["budget"] = budget
        context.user_data["step"] = "timeline"

        await lead_db.save_lead_memory(DB_PATH, user.id, {
            "platform_interest": context.user_data.get("platform", ""),
            "budget_range": budget,
        })

        await query.edit_message_text(
            f"Nice — {budget}/month. 💪\n\n{TIMELINE_QUESTION_EN}",
            reply_markup=TIMELINE_KEYBOARD,
        )
        return

    # ── Timeline selection ───────────────────────────────────────────────
    if data.startswith("timeline_"):
        timeline = TIMELINE_MAP.get(data, "exploring")
        context.user_data["timeline"] = timeline
        context.user_data["step"] = "done"

        platform = context.user_data.get("platform", "unknown")
        budget = context.user_data.get("budget", "unknown")

        # BANT score
        if scorer:
            bant = scorer.score(
                budget=budget,
                platform=platform,
                timeline=timeline,
            )
        else:
            bant = {"total": 30, "tier": "cool"}

        score = bant["total"]
        tier = bant.get("tier", "cold")

        # Update lead record
        await lead_db.upsert_lead(
            DB_PATH, user.id,
            bot_qualified=1,
            bant_score=score,
            bant_tier=tier,
            sales_stage="qualify" if tier in ("hot", "warm") else "opener",
        )

        await lead_db.save_lead_memory(DB_PATH, user.id, {
            "platform_interest": platform,
            "budget_range": budget,
            "timeline": timeline,
        })

        # Save bot conversation summary for handoff
        summary = (
            f"Platform: {platform}, Budget: {budget}/mo, "
            f"Timeline: {timeline}, BANT: {score} ({tier})"
        )
        await lead_db.save_message(
            DB_PATH, user.id, "system", summary, source="bot", bant_score=score,
        )

        log.info(
            "Lead @%s qualified: %s (BANT=%d, tier=%s)",
            user.username, summary, score, tier,
        )

        # ── Route based on score ─────────────────────────────────────────
        if tier in ("hot", "warm"):
            # Immediate handoff to userbot
            await lead_db.create_handoff(
                DB_PATH, user.id,
                reason="bot_qualified_hot" if tier == "hot" else "bot_qualified_warm",
                bot_summary=summary,
                bant_score=score,
            )

            await query.edit_message_text(HANDOFF_EN)

        else:
            # Cool/cold — nurture via bot, show options
            await query.edit_message_text(
                "Thanks for the info! 👍\n\n"
                "Here's what I can help you with:",
                reply_markup=PLAN_KEYBOARD,
            )

        return

    # ── Action buttons ───────────────────────────────────────────────────
    if data == "show_pricing":
        pricing = (
            "💰 *Our Plans at a Glance:*\n\n"
            "🟢 *Basic* — Starting from $50/acct\n"
            "  → 1 free replacement, TG support group\n\n"
            "🔵 *Pro* — From $100-$450/acct\n"
            "  → 3 replacements, dedicated account manager\n\n"
            "🟣 *Enterprise* — $800-$1000/mo\n"
            "  → Unlimited everything, Slack channel\n\n"
            "All platforms: Google, Meta, Bing, Taboola\n"
            "No spend limits • Agency-level trust • Same-day replacements\n\n"
            "Want to discuss your specific needs?"
        )

        await query.edit_message_text(
            pricing,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💬 Talk to Manager", callback_data="talk_manager")],
            ]),
        )
        return

    if data == "talk_manager":
        # Hand off to userbot
        await lead_db.create_handoff(
            DB_PATH, user.id,
            reason="requested_manager",
            bot_summary=f"User requested to talk to manager. Platform: {context.user_data.get('platform', '?')}",
            bant_score=context.user_data.get("bant_score", 0),
        )

        await query.edit_message_text(
            f"Connecting you with Chris now! 🤝\n\n"
            f"He'll DM you in a few minutes.\n"
            f"Or you can reach him directly: @{ADMIN_USERNAME}"
        )
        return

    if data == "case_studies":
        await query.edit_message_text(
            "📊 *Recent Results:*\n\n"
            "• Crypto advertiser: 300% ROI increase after switching to our Google accounts\n"
            "• Nutra affiliate: $50K/day spend, zero bans in 6 months\n"
            "• E-com store: Scaled from $5K to $30K/day on Meta\n\n"
            "Want similar results?",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💬 Let's Talk", callback_data="talk_manager")],
                [InlineKeyboardButton("📋 See Pricing", callback_data="show_pricing")],
            ]),
        )
        return


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle free-text messages from users."""
    user = update.effective_user
    text = update.message.text or ""
    if not text.strip() or not user:
        return

    # Save the message
    await lead_db.save_message(
        DB_PATH, user.id, "inbound", text, source="bot",
    )

    # If they're typing freely, they want a real conversation → handoff
    step = context.user_data.get("step", "done")
    if step == "done":
        await lead_db.create_handoff(
            DB_PATH, user.id,
            reason="free_text_conversation",
            bot_summary=f"User sent free text: {text[:200]}",
        )

        await update.message.reply_text(
            "Great question! Let me connect you with Chris — "
            "he can help you directly. He'll message you shortly! 🤝\n\n"
            f"Or DM him: @{ADMIN_USERNAME}"
        )
    else:
        # Still in qualification flow — nudge them to use buttons
        await update.message.reply_text(
            "Please use the buttons above to help me get you the right info! ☝️"
        )


# ═══════════════════════════════════════════════════════════════════════════
# Stats Command (admin only)
# ═══════════════════════════════════════════════════════════════════════════

async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show funnel statistics (admin only)."""
    user = update.effective_user
    admin_id = int(os.getenv("ADMIN_CHAT_ID", "0"))
    if not user or user.id != admin_id:
        return

    stats = await lead_db.get_funnel_stats(DB_PATH)
    text = (
        "📊 *Funnel Stats*\n\n"
        f"Total leads: {stats['total_leads']}\n"
        f"Channel joins: {stats['joined_channel']} ({stats['channel_rate']})\n"
        f"Bot qualified: {stats['bot_qualified']} ({stats['qualification_rate']})\n"
        f"Active DMs: {stats['active_dm']} ({stats['dm_rate']})\n"
        f"Hot leads: {stats['hot_leads']}\n\n"
        f"Tier breakdown: {stats['tier_breakdown']}"
    )
    await update.message.reply_text(text)


# ═══════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════

async def post_init(app: Application) -> None:
    """Initialize database on startup."""
    await lead_db.init_db(DB_PATH)
    log.info("Qualification bot started — DB at %s", DB_PATH)


def main() -> None:
    if not BOT_TOKEN:
        log.error("BOT_TOKEN not set — exiting")
        sys.exit(1)

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    log.info("Starting qualification bot...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
