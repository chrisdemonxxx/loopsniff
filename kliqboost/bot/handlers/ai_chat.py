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
from aiogram.types import Message
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
HOT_LEAD_THRESHOLD = 75
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

    # Track user messages for BANT scoring
    _user_messages[uid].append(text)

    try:
        await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)

        # 1. BANT score across full conversation
        bant = _scorer.score_from_conversation(_user_messages[uid])

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

    # Check if invite link is ready
    invite = _check_invite_link(uid)
    if invite and uid in _group_triggered:
        ai_reply += f"\n\n💎 Your deal room is ready — join here: {invite}"

    # Save + reply
    save_message(uid, "user", text)
    save_message(uid, "assistant", ai_reply)
    await message.answer(ai_reply, parse_mode=None)
