"""AI chat handler — RAG + Ollama Cloud powered responses.

Catches all text messages not handled by other routers.  Retrieves
context from the AdFlux RAG knowledge base, sends it along with the
user's conversation history to Ollama Cloud, and replies with a
natural AI-generated answer.
"""

from __future__ import annotations

import logging
import sys
from collections import defaultdict
from typing import Dict, List

import aiohttp
from aiogram import Router
from aiogram.types import Message
from aiogram.enums import ParseMode

from middlewares.i18n import t
from keyboards.inline import main_menu_kb
from utils.notifications import notify_admin

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

_RetrieverCls = _import_retriever_class()

log = logging.getLogger(__name__)

router = Router()

# ── Ollama Cloud settings ────────────────────────────────────────────────

OLLAMA_URL = "https://api.ollamacloud.com/v1/chat/completions"
OLLAMA_API_KEY = "5d92bf191608457d951f3eea8459b66e"
OLLAMA_MODEL = "llama3.1:8b"

SYSTEM_PROMPT = (
    "You are the AI assistant for AdFlux Media, a premium agency ad account "
    "provider. You help media buyers get whitelisted ad accounts for Google, "
    "Meta, TikTok, Taboola, Outbrain. Answer questions using the provided "
    "context. Be professional but friendly. If you don't know the answer, "
    "say so and suggest they contact @Adflux_Admin. Keep answers concise."
)

MAX_HISTORY = 10

# ── In-memory conversation history (per user_id) ────────────────────────

_conversations: Dict[int, List[dict]] = defaultdict(list)

# ── RAG retriever singleton ──────────────────────────────────────────────

_retriever: object | None = None


def _get_retriever():
    global _retriever
    if _retriever is None:
        _retriever = _RetrieverCls()
    return _retriever


# ── Ollama Cloud client ──────────────────────────────────────────────────


async def _ollama_chat(messages: list[dict]) -> str:
    """Send chat completion to Ollama Cloud and return the reply text."""
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + messages,
        "temperature": 0.7,
        "max_tokens": 400,
    }
    headers = {
        "Authorization": f"Bearer {OLLAMA_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                OLLAMA_URL,
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    log.error("Ollama Cloud error (%d): %s", resp.status, body)
                    return ""
                data = await resp.json()
                return data["choices"][0]["message"]["content"]
    except Exception as exc:
        log.error("Ollama Cloud request failed: %s", exc)
        return ""


# ── RAG context builder ──────────────────────────────────────────────────


def _build_rag_context(query: str) -> str:
    """Retrieve knowledge-base context from ChromaDB."""
    retriever = _get_retriever()
    results = retriever.get_knowledge(query, n_results=3)
    if not results:
        return ""
    parts = ["=== AdFlux Knowledge Base ==="]
    for r in results:
        parts.append(r["text"])
    return "\n\n".join(parts)


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

    # 1. Retrieve RAG context
    rag_context = _build_rag_context(text)

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
    llm_messages.extend(_conversations[uid][-MAX_HISTORY:])

    # Append current user message
    llm_messages.append({"role": "user", "content": text})

    # 3. Generate AI response
    ai_reply = await _ollama_chat(llm_messages)

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
    _conversations[uid].append({"role": "user", "content": text})
    _conversations[uid].append({"role": "assistant", "content": ai_reply})

    # Trim history
    if len(_conversations[uid]) > MAX_HISTORY * 2:
        _conversations[uid] = _conversations[uid][-MAX_HISTORY:]

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
