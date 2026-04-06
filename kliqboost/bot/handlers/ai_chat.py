"""KLIQ NEXUS — AI concierge for Kliqboost Media.

Pure conversational AI handler. Qualifies leads through natural
conversation using BANT scoring. When a lead is hot (score >= 75),
triggers deal-room group creation via the Telethon autoresponder bridge.
"""

from __future__ import annotations

import asyncio
import logging
import os
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
HOT_LEAD_THRESHOLD = 60
MAX_HISTORY = 12
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))

# Bridge DB — shared with autoresponder for group creation
BRIDGE_DB = Path("/home/cjs/kliqboost/bridge/deal_rooms.db")

SYSTEM_PROMPT = """\
You are KLIQ NEXUS — the AI concierge for Kliqboost Media, a premium \
ad account agency on Telegram.

YOUR IDENTITY:
- You are an AI and own it. Sleek, efficient, futuristic.
- You are the first touchpoint for clients. You qualify, inform, and route.
- You speak like a knowledgeable insider — concise, confident, no fluff.

HOW YOU TALK:
- 2-4 sentences max per reply. Short, punchy, premium.
- Use subtle emojis (⚡, 🎯, 💎) — never overdo it.
- MATCH the user's language — Russian? Reply in Russian.
- Be direct. No "How can I help you today?" generic crap.
- Sound like a sharp account exec, not a customer service bot.

YOUR JOB — QUALIFY THE LEAD:
You need to learn 4 things through natural conversation (don't ask all at once):
1. PLATFORM — What ad platform do they need? (Google, Meta, TikTok, Taboola, Bing, etc.)
2. BUDGET — What's their monthly ad spend or account budget?
3. NICHE — What vertical? (crypto, finance, nutra, ecommerce, sweeps, etc.)
4. TIMELINE — How soon do they need it?

Ask these naturally across 2-4 messages. When you have enough info and the lead \
is serious, say something like: "Let me set up a private deal room with our team — \
we'll get you sorted fast." Then stop qualifying.

WHAT YOU KNOW:
Google Ads: $50-$800/mo depending on tier.
Meta Ads: $200-$1000/mo.
Bing Ads: $100-$1000/mo.
TikTok Ads: $80-$600/mo.
Taboola: $50-$800/mo.
All plans: replacements included, crypto payments (BTC/ETH/USDT), 24-48hr delivery.

CHANNELS:
- Main: t.me/kliqboost_media
- Vouches: t.me/kliqboost_vouches
- Team lead: @Chris_Darton

RULES:
- Never dump all pricing at once. Answer what they asked.
- If they ask something you don't know, say "Let me pull our team in for that."
- Don't be pushy. Inform, qualify, route.
- Keep it premium and efficient.\
"""

# ── Per-user state ───────────────────────────────────────────────────────
_user_messages: Dict[int, List[str]] = defaultdict(list)
_group_triggered: set[int] = set()

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
        f"⚡ <b>KLIQ NEXUS — Lead Qualified</b>\n\n"
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
        await message.answer("⚡ Send me a message — I'm here to help.")
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

        # Add BANT state as system context
        bant_hint = (
            f"[LEAD STATE: BANT={bant['total']} tier={bant.get('tier','?')}. "
            f"Extracted: platform={bant.get('extracted',{}).get('platform','?')}, "
            f"budget={bant.get('extracted',{}).get('budget','?')}, "
            f"niche={bant.get('extracted',{}).get('niche','?')}, "
            f"timeline={bant.get('extracted',{}).get('timeline','?')}]"
        )
        if uid in _group_triggered:
            deal = _check_deal_status(uid)
            if deal:
                st = deal["status"]
                if st == "manual_refer" and deal.get("ref_code"):
                    bant_hint += (
                        f"\n[GROUP CREATION FAILED — ask the user to DM @Chris_Darton "
                        f"with reference code {deal['ref_code']} to continue. "
                        f"Be apologetic but brief. Also suggest they check their "
                        f"Telegram privacy settings (Settings → Privacy → Groups — set to Everyone).]"
                    )
                elif st == "failed":
                    bant_hint += (
                        "\n[GROUP CREATION FAILED — tell the user to DM @Chris_Darton directly "
                        "to continue the conversation. Also suggest checking their privacy settings "
                        "(Settings → Privacy → Groups → Everyone).]"
                    )
                elif st == "invite_sent" and deal.get("invite_link"):
                    bant_hint += "\n[DEAL ROOM READY — share the invite link with the user.]"
                elif st == "bot_invite" and deal.get("invite_link"):
                    bant_hint += "\n[DEAL ROOM READY — an invite button will be sent to the user. Tell them to tap it.]"
                elif st == "done":
                    bant_hint += "\n[DEAL ROOM TRIGGERED — tell the user a private group is being set up with the team.]"
                else:
                    bant_hint += "\n[DEAL ROOM TRIGGERED — tell the user a private group is being set up with the team.]"
            else:
                bant_hint += "\n[DEAL ROOM TRIGGERED — tell the user a private group is being set up with the team.]"

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
        log.error("KLIQ NEXUS pipeline error for uid=%d: %s", uid, exc)
        ai_reply = None

    if not ai_reply:
        ai_reply = (
            "⚡ Systems are syncing — drop me your question again in a sec, "
            "or DM @Chris_Darton directly."
        )

    # Check deal room status and build inline keyboard if invite link available
    reply_markup = None
    if uid in _group_triggered:
        deal = _check_deal_status(uid)
        if deal:
            st = deal["status"]
            link = deal.get("invite_link")

            if st in ("done", "invite_sent", "bot_invite") and link:
                # Send clickable inline button instead of raw link
                reply_markup = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔥 Join Deal Room", url=link)]
                ])
                ai_reply += "\n\n💎 Your deal room is ready — tap the button below to join!"

                # Mark bot_invite as delivered
                if st == "bot_invite":
                    _update_bridge_status(uid, "invite_delivered")

            elif st == "manual_refer" and deal.get("ref_code"):
                ai_reply += (
                    f"\n\n📋 DM @Chris_Darton with your reference: **{deal['ref_code']}** "
                    f"and he'll get you sorted right away."
                )

    # Save + reply
    save_message(uid, "user", text)
    save_message(uid, "assistant", ai_reply)
    await message.answer(ai_reply, parse_mode=None, reply_markup=reply_markup)
