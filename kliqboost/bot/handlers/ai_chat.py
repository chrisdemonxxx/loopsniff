"""Kliqboost Media — AI concierge handler.

Pure conversational AI handler. Qualifies leads through natural
conversation using BANT scoring. When a lead is hot (score >= 75),
triggers deal-room group creation via the Telethon autoresponder bridge.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import sys
import sqlite3
import time
import importlib
from pathlib import Path
from collections import defaultdict
from typing import Dict, List

import aiohttp
from aiogram import Router
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ChatAction, ParseMode

from utils.llm_client import call_llm
from db.persistence import save_message, get_history

# ── RAG import (isolated to avoid config collision) ──────────────────────
_rag_root = "/home/cjs/kliqboost/rag"

def _import_retriever_class():
    saved = sys.path[:]
    try:
        sys.path.insert(0, _rag_root)
        rag_cfg_spec = importlib.util.spec_from_file_location(
            "rag_config", f"{_rag_root}/config.py"
        )
        rag_cfg = importlib.util.module_from_spec(rag_cfg_spec)
        sys.modules["config"] = rag_cfg
        rag_cfg_spec.loader.exec_module(rag_cfg)
        from retrieval.retriever import Retriever as _Ret
        return _Ret
    finally:
        sys.path[:] = saved
        from importlib import import_module
        bot_cfg = import_module("config")
        sys.modules["config"] = bot_cfg

_RetrieverCls = None
def _get_retriever_class():
    global _RetrieverCls
    if _RetrieverCls is None:
        try:
            _RetrieverCls = _import_retriever_class()
        except Exception:
            pass
    return _RetrieverCls

# ── BANT scorer import ──────────────────────────────────────────────────
sys.path.insert(0, "/home/cjs/kliqboost")
from scoring.bant_scorer import BANTScorer

log = logging.getLogger(__name__)
router = Router()

# ── Constants ────────────────────────────────────────────────────────────
HOT_LEAD_THRESHOLD = 30
MAX_HISTORY = 30
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))

# Bridge DB — shared with autoresponder for group creation
BRIDGE_DB = Path("/home/cjs/kliqboost/bridge/deal_rooms.db")

SYSTEM_PROMPT = """\
You are the AI concierge for Kliqboost Media, an agency ad account \
provider on Telegram.

YOUR IDENTITY:
- You are an AI assistant. Professional, efficient, knowledgeable.
- You are the first touchpoint for clients. You qualify, inform, and close.
- You speak like a knowledgeable insider — concise, confident, no fluff.

HOW YOU TALK:
- 2-4 sentences max per reply. Short, punchy, professional.
- Use minimal emoji — one or two per message at most.
- MATCH the user's language — Russian? Reply in Russian.
- Be direct. Sound like a sharp account exec.

YOUR JOB — QUALIFY AND CLOSE:
You need to learn 4 things through natural conversation (don't ask all at once):
1. PLATFORM — What ad platform do they need? (Google, Meta, TikTok, Taboola, Bing, etc.)
2. BUDGET — What's their monthly ad spend or account budget?
3. VERTICAL — What industry or vertical are they in?
4. TIMELINE — How soon do they need it?

Ask these naturally across 2-4 messages. When you have enough info and the lead \
is serious, tell them you can process their order right here — tap the button below.

WHAT YOU KNOW:
Google Ads: $50-$800/mo depending on tier.
Meta Ads: $200-$1000/mo.
Bing Ads: $100-$1000/mo.
TikTok Ads: $80-$600/mo.
Taboola: $50-$800/mo.
All plans: replacements included, crypto payments (BTC/ETH/USDT), 2-hour delivery.

PAYMENT:
- We accept BTC, ETH, and USDT (ERC-20)
- When the lead is ready, tell them to tap "Ready to Order" and the checkout handles the rest
- DO NOT make up wallet addresses or amounts — the checkout system handles that

CHANNELS:
- Main: t.me/kliqboost_media
- Vouches: t.me/kliqboost_vouches
- Team lead: @Chris_Darton

RULES:
- Never dump all pricing at once. Answer what they asked.
- If they ask something you don't know, say "Let me pull our team in for that."
- Don't be pushy. Inform, qualify, close.
- When lead is qualified and ready, tell them to tap the order button.
- Keep it professional and efficient.
- NEVER say a button is there if it's not — only mention the order button when you're told it's shown.
- NEVER make up features, buttons, or links that don't exist.
- NEVER say "24-48 hours" — delivery is always 2 hours.
- If you're unsure about platform/vertical/budget, ASK the user — don't guess.
- Stay consistent with what the user told you. If they said "Google 3k", repeat that back.
- We support all verticals and industries. When a client mentions their vertical, \
acknowledge it professionally without judgment.\
"""

# ── Per-user state ───────────────────────────────────────────────────────
_user_messages: Dict[int, List[str]] = defaultdict(list)
_group_triggered: set[int] = set()
_checkout_offered: set[int] = set()  # users who've seen the "Ready to Order" button

# ── BANT scorer ──────────────────────────────────────────────────────────
_scorer = BANTScorer()

# ── RAG singleton ────────────────────────────────────────────────────────
_retriever = None
def _get_retriever():
    global _retriever
    if _retriever is None:
        cls = _get_retriever_class()
        if cls is not None:
            _retriever = cls()
    return _retriever

def _build_rag_context(query: str, username: str = "") -> str:
    try:
        retriever = _get_retriever()
        if retriever is None:
            return ""
        parts = []
        kb = retriever.get_knowledge(query, n_results=3)
        if kb:
            parts.append("=== Knowledge Base ===")
            for r in kb:
                parts.append(r["text"])
        if username:
            lead = retriever.get_lead_context(username, n_results=2)
            if lead:
                parts.append("=== Lead Profile ===")
                for r in lead:
                    parts.append(r["text"])
        return "\n\n".join(parts)
    except Exception as exc:
        log.error("RAG failed: %s", exc)
        return ""

async def _rag_async(query: str, username: str = "") -> str:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _build_rag_context, query, username)

# ── Bridge DB init ───────────────────────────────────────────────────────
def _init_bridge_db():
    BRIDGE_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(BRIDGE_DB))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pending_deal_rooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT,
            full_name TEXT,
            bant_score INTEGER DEFAULT 0,
            platform TEXT,
            niche TEXT,
            budget TEXT,
            timeline TEXT,
            status TEXT DEFAULT 'pending',
            invite_link TEXT,
            ref_code TEXT,
            created_at REAL,
            completed_at REAL
        )
    """)
    # Migrate: add ref_code column if missing
    try:
        conn.execute("SELECT ref_code FROM pending_deal_rooms LIMIT 1")
    except sqlite3.OperationalError:
        conn.execute("ALTER TABLE pending_deal_rooms ADD COLUMN ref_code TEXT")
    conn.commit()
    conn.close()

def _request_deal_room(
    user_id: int, username: str, full_name: str, bant: dict
) -> None:
    """Write a qualified lead to the bridge DB for group creation."""
    extracted = bant.get("extracted", {})
    conn = sqlite3.connect(str(BRIDGE_DB))
    conn.execute(
        """INSERT INTO pending_deal_rooms
           (user_id, username, full_name, bant_score, platform, niche, budget, timeline, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            user_id,
            username or "",
            full_name or "",
            bant.get("total", 0),
            str(extracted.get("platform", "")),
            str(extracted.get("niche", "")),
            str(extracted.get("budget", "")),
            str(extracted.get("timeline", "")),
            time.time(),
        ),
    )
    conn.commit()
    conn.close()
    log.info("🔥 Deal room requested for user_id=%d (@%s) score=%d",
             user_id, username, bant.get("total", 0))

def _check_deal_status(user_id: int) -> dict | None:
    """Check the deal room status — returns dict with status, invite_link, ref_code."""
    try:
        conn = sqlite3.connect(str(BRIDGE_DB))
        row = conn.execute(
            "SELECT status, invite_link, ref_code FROM pending_deal_rooms "
            "WHERE user_id = ? ORDER BY id DESC LIMIT 1",
            (user_id,),
        ).fetchone()
        conn.close()
        if not row:
            return None
        return {"status": row[0], "invite_link": row[1], "ref_code": row[2]}
    except Exception:
        return None

def _check_invite_link(user_id: int) -> str | None:
    """Legacy compat — returns invite link if deal room is done."""
    result = _check_deal_status(user_id)
    if result and result["status"] in ("done", "invite_sent") and result["invite_link"]:
        return result["invite_link"]
    return None

def _update_bridge_status(user_id: int, new_status: str):
    """Update the bridge DB status for a user."""
    try:
        conn = sqlite3.connect(str(BRIDGE_DB))
        conn.execute(
            "UPDATE pending_deal_rooms SET status = ? WHERE user_id = ? AND status = 'bot_invite'",
            (new_status, user_id),
        )
        conn.commit()
        conn.close()
        log.info("Bridge status updated for uid=%d → %s", user_id, new_status)
    except Exception as exc:
        log.warning("Failed to update bridge status for uid=%d: %s", user_id, exc)

# ── Admin notification ───────────────────────────────────────────────────
async def _notify_admin(bot, user_id: int, username: str, bant: dict):
    if not ADMIN_CHAT_ID:
        return
    breakdown = bant.get("breakdown", {})
    text = (
        f"<b>Kliqboost Media — Lead Qualified</b>\n\n"
        f"👤 @{username or 'N/A'} (id: {user_id})\n"
        f"🎯 BANT: {bant['total']} ({bant.get('tier', '?')})\n"
        f"📊 Budget: {breakdown.get('budget', {}).get('value', '?')}\n"
        f"🔧 Platform: {breakdown.get('platform', {}).get('value', '?')}\n"
        f"🏷 Niche: {breakdown.get('niche', {}).get('value', '?')}\n"
        f"⏱ Timeline: {breakdown.get('timeline', {}).get('value', '?')}\n\n"
        f"Deal room creation triggered ✅"
    )
    try:
        await bot.send_message(ADMIN_CHAT_ID, text, parse_mode=ParseMode.HTML)
    except Exception as exc:
        log.error("Admin notify failed: %s", exc)

# ── Init bridge on import ────────────────────────────────────────────────
_init_bridge_db()

# ── Handler ──────────────────────────────────────────────────────────────

@router.message()
async def nexus_handler(message: Message) -> None:
    uid = message.from_user.id
    text = (message.text or "").strip()
    if not text:
        await message.answer("Send me a message — I'm here to help.")
        return

    username = message.from_user.username or ""
    full_name = message.from_user.full_name or ""

    # Track user messages for BANT scoring (load from DB on first encounter)
    if uid not in _user_messages:
        db_history = get_history(uid, limit=50)
        _user_messages[uid] = [
            m["content"] for m in db_history if m.get("role") == "user"
        ]
        # Check if deal room was already triggered (survives restart)
        deal = _check_deal_status(uid)
        if deal and deal["status"] in ("done", "invite_sent", "bot_invite", "manual_refer", "pending"):
            _group_triggered.add(uid)
    _user_messages[uid].append(text)

    try:
        await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)

        # 1. BANT score across full conversation
        bant = _scorer.score_from_conversation(_user_messages[uid])
        log.info("BANT @%s (uid=%d): score=%d tier=%s msgs=%d",
                 username, uid, bant["total"], bant.get("tier","?"), len(_user_messages[uid]))

        # 2. Check if we should trigger deal room
        if bant["total"] >= HOT_LEAD_THRESHOLD and uid not in _group_triggered:
            _group_triggered.add(uid)
            _request_deal_room(uid, username, full_name, bant)
            await _notify_admin(message.bot, uid, username, bant)

        # 3. RAG context
        rag_context = await _rag_async(text, username.lower() if username else "")

        # 4. Build LLM messages
        llm_messages: list[dict] = []
        if rag_context:
            llm_messages.append({
                "role": "user",
                "content": f"[CONTEXT — use to inform, don't repeat]\n\n{rag_context}",
            })
            llm_messages.append({
                "role": "assistant",
                "content": "Got it.",
            })

        # Add BANT state as system context — only confirmed fields
        extracted = bant.get("extracted", {})
        confirmed_parts = []
        if extracted.get("platform"):
            confirmed_parts.append(f"platform={extracted['platform']}")
        if extracted.get("budget"):
            confirmed_parts.append(f"budget={extracted['budget']}")
        if extracted.get("niche"):
            confirmed_parts.append(f"niche={extracted['niche']}")
        if extracted.get("timeline"):
            confirmed_parts.append(f"timeline={extracted['timeline']}")

        bant_hint = f"[LEAD STATE: BANT={bant['total']} tier={bant.get('tier','?')}."
        if confirmed_parts:
            bant_hint += f" Confirmed: {', '.join(confirmed_parts)}."
        else:
            bant_hint += " No confirmed details yet — ask what they need."
        bant_hint += "]"
        if uid in _group_triggered:
            deal = _check_deal_status(uid)
            if deal:
                st = deal["status"]
                if st in ("done", "invite_sent", "bot_invite") and deal.get("invite_link"):
                    bant_hint += "\n[DEAL ROOM READY — the user can also join the deal room if they want.]"
                elif st == "pending":
                    bant_hint += "\n[Deal room is being set up — tell user it's coming shortly if they ask.]"

        # Pre-compute if checkout button will be shown
        _CHECKOUT_TRIGGERS = re.compile(
            r"\border\b|\bbuy\b|\bpurchas\w*\b|\bready\b|\bcheckout\b|\bpay\b"
            r"|\bget started\b|\bsign me up\b|\blet'?s go\b|\blet'?s do it\b"
            r"|\bhow do i pay\b|\bwhere.{0,10}pay\b|\bsend.{0,10}invoice\b"
            r"|\bзаказ\w*\b|\bкупить\b|\bоплат\w*\b|\bготов\b|\bдавай\b",
            re.I,
        )
        has_checkout_intent = bool(_CHECKOUT_TRIGGERS.search(text))
        will_show_button = (bant["total"] >= HOT_LEAD_THRESHOLD or has_checkout_intent)

        if will_show_button:
            from payments.order_manager import get_active_order
            if get_active_order(uid):
                will_show_button = False

        # Add checkout hint
        if will_show_button:
            bant_hint += (
                "\n[CHECKOUT BUTTON IS SHOWN BELOW YOUR REPLY — tell them to tap "
                "'Ready to Order' below to start checkout. Be natural about it. "
                "Mention we accept BTC, ETH, USDT. Delivery: 2 hours.]"
            )
        elif bant["total"] >= HOT_LEAD_THRESHOLD:
            bant_hint += (
                "\n[LEAD IS QUALIFIED but already has an active order. "
                "Don't offer a new order — ask about their existing one.]"
            )

        llm_messages.append({"role": "user", "content": bant_hint})
        llm_messages.append({"role": "assistant", "content": "Understood."})

        # Conversation history
        llm_messages.extend(get_history(uid, limit=MAX_HISTORY))
        llm_messages.append({"role": "user", "content": text})

        # 5. Generate response
        ai_reply = await call_llm(
            prompt=text,
            system_prompt=SYSTEM_PROMPT,
            history=llm_messages,
        )
    except Exception as exc:
        log.error("Kliqboost Media pipeline error for uid=%d: %s", uid, exc)
        ai_reply = None

    if not ai_reply:
        ai_reply = (
            "⚡ Systems are syncing — drop me your question again in a sec, "
            "or DM @Chris_Darton directly."
        )

    # Build reply markup — checkout button takes priority over deal room
    reply_markup = None
    from keyboards.inline import checkout_ready_kb

    # Show "Ready to Order" button (already pre-computed before LLM call)
    if will_show_button:
        reply_markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💎 Ready to Order", callback_data="checkout:start")],
        ])

    # Also show deal room button if available (as second row)
    if uid in _group_triggered:
        deal = _check_deal_status(uid)
        if deal:
            st = deal["status"]
            link = deal.get("invite_link")

            if st in ("done", "invite_sent", "bot_invite") and link:
                deal_btn = [InlineKeyboardButton(text="🔥 Join Deal Room", url=link)]
                if reply_markup:
                    reply_markup.inline_keyboard.append(deal_btn)
                else:
                    reply_markup = InlineKeyboardMarkup(inline_keyboard=[deal_btn])

                if st == "bot_invite":
                    _update_bridge_status(uid, "invite_delivered")

    # Save + reply
    save_message(uid, "user", text)
    save_message(uid, "assistant", ai_reply)
    await message.answer(ai_reply, parse_mode=None, reply_markup=reply_markup)
