"""AI chat handler — RAG + Ollama Cloud powered responses.

Catches all text messages not handled by other routers.  Retrieves
context from the AdFlux RAG knowledge base, sends it along with the
user's conversation history to Ollama Cloud, and replies with a
natural AI-generated answer.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from typing import Dict, List

import aiohttp
from aiogram import Router
from aiogram.types import Message
from aiogram.enums import ChatAction, ParseMode

from middlewares.i18n import t
from keyboards.inline import main_menu_kb
from utils.notifications import notify_admin
from utils.llm_client import call_llm
from db.persistence import save_message, get_history

# ── Wire up RAG project ──────────────────────────────────────────────────
# Import the RAG retriever in an isolated way so its `config` module
# doesn't collide with the bot's own `config`.
import importlib
_rag_root = "/home/cjs/tgacc/adflux-rag"

def _import_retriever_class():
    """Import the Retriever class without polluting sys.path permanently."""
    saved = sys.path[:]
    try:
        sys.path.insert(0, _rag_root)
        # Force-load the RAG config under its own name
        rag_cfg_spec = importlib.util.spec_from_file_location(
            "rag_config", f"{_rag_root}/config.py"
        )
        rag_cfg = importlib.util.module_from_spec(rag_cfg_spec)
        sys.modules["config"] = rag_cfg          # temporarily override
        rag_cfg_spec.loader.exec_module(rag_cfg)

        from retrieval.retriever import Retriever as _Ret

        return _Ret
    finally:
        sys.path[:] = saved
        # Restore the bot's config module
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

log = logging.getLogger(__name__)

router = Router()

# ── LLM settings ─────────────────────────────────────────────────────────

SYSTEM_PROMPT = (
    "You are the AI assistant for AdFlux Media, a premium agency ad account "
    "provider. You help media buyers get whitelisted ad accounts for Google, "
    "Meta, TikTok, Taboola, Outbrain. Answer questions using the provided "
    "context. Be professional but friendly. If you don't know the answer, "
    "say so and suggest they contact @Adflux_Admin. Keep answers concise."
)

MAX_HISTORY = 10

# ── RAG retriever singleton ──────────────────────────────────────────────

_retriever: object | None = None


def _get_retriever():
    global _retriever
    if _retriever is None:
        cls = _get_retriever_class()
        if cls is not None:
            _retriever = cls()
    return _retriever


# ── RAG context builder ──────────────────────────────────────────────────


def _build_rag_context(query: str) -> str:
    """Retrieve knowledge-base context from ChromaDB (sync — run in executor)."""
    try:
        retriever = _get_retriever()
        if retriever is None:
            return ""
        results = retriever.get_knowledge(query, n_results=3)
        if not results:
            return ""
        parts = ["=== AdFlux Knowledge Base ==="]
        for r in results:
            parts.append(r["text"])
        return "\n\n".join(parts)
    except Exception as exc:
        log.error("RAG context retrieval failed: %s", exc)
        return ""


async def _build_rag_context_async(query: str) -> str:
    """Run the sync RAG retrieval in a thread to avoid blocking the event loop."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _build_rag_context, query)


# ── Handler ──────────────────────────────────────────────────────────────


@router.message()
async def free_text_handler(message: Message) -> None:
    uid = message.from_user.id
    _t = lambda k, **kw: t(uid, k, **kw)

    text = (message.text or "").strip()
    if not text:
        await message.answer(
            _t("ai_stub"),
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu_kb(_t),
        )
        return

    try:
        # Show typing indicator while processing
        await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)

        # 1. Retrieve RAG context (non-blocking)
        rag_context = await _build_rag_context_async(text)

        # 2. Build LLM messages with history
        llm_messages: list[dict] = []

        if rag_context:
            llm_messages.append(
                {
                    "role": "user",
                    "content": (
                        "[CONTEXT — use to inform your answer, do not repeat "
                        "verbatim]\n\n" + rag_context
                    ),
                }
            )
            llm_messages.append(
                {
                    "role": "assistant",
                    "content": "Got it, I'll use this context.",
                }
            )

        # Append conversation history (last MAX_HISTORY messages)
        llm_messages.extend(get_history(uid, limit=MAX_HISTORY))

        # Append current user message
        llm_messages.append({"role": "user", "content": text})

        # 3. Generate AI response via LLM client
        ai_reply = await call_llm(
            prompt=text,
            system_prompt=SYSTEM_PROMPT,
            history=llm_messages,
        )
    except Exception as exc:
        log.error("AI pipeline failed for user %d: %s", uid, exc)
        ai_reply = ""

    if not ai_reply:
        # Fallback when Ollama Cloud is unavailable
        await message.answer(
            _t("ai_stub"),
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu_kb(_t),
        )
        # Forward to admin as before
        admin_text = t(
            uid,
            "admin_free_text",
            user_name=message.from_user.full_name,
            user_id=uid,
            username=message.from_user.username or "N/A",
            message=text,
        )
        await notify_admin(message.bot, admin_text)
        return

    # 4. Save conversation history
    save_message(uid, "user", text)
    save_message(uid, "assistant", ai_reply)

    # 5. Reply to user
    await message.answer(ai_reply, parse_mode=None)

    # 6. Still forward to admin for visibility
    admin_text = t(
        uid,
        "admin_free_text",
        user_name=message.from_user.full_name,
        user_id=uid,
        username=message.from_user.username or "N/A",
        message=text,
    )
    await notify_admin(message.bot, admin_text)
