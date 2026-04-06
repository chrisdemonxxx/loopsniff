#!/usr/bin/env python3
"""Admin AI Auto-Responder — inbound DMs only.

Connects Chris's admin Telegram account via Telethon and auto-responds
to incoming DMs using the Kliqboost RAG knowledge base + Ollama Cloud LLM.

Completely separate from the outreach / burn-and-churn system.

Usage:
    python admin_autoresponder.py              # run daemon
    python admin_autoresponder.py --auth       # authenticate (send OTP)
    python admin_autoresponder.py --test       # connect, print status, exit
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import random
import signal
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiohttp
import aiosqlite

# ── RAG + BANT imports ──────────────────────────────────────────────────────
_base = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_base / "rag"))
sys.path.insert(0, str(_base))

from retrieval.retriever import Retriever
from scoring.bant_scorer import BANTScorer

from telethon import TelegramClient, events
from telethon.tl.functions.messages import CreateChatRequest, AddChatUserRequest

# ── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("admin_autoresponder")

# ── Configuration ───────────────────────────────────────────────────────────

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent / ".env", override=True)

PHONE = os.getenv("TG_PHONE", "+15642618554")
SESSION_DIR = Path(__file__).resolve().parent / "sessions"
SESSION_PATH = str(SESSION_DIR / f"tg_{PHONE.replace('+', '')}")
DB_PATH = SESSION_DIR / "conversations.db"

DEVICE = {
    "api_id": int(os.getenv("TG_API_ID", "33454441")),
    "api_hash": os.getenv("TG_API_HASH", "10ade2b7e270023f3e1debb7e25dab45"),
    "device_model": "iPhone 15 Pro Max",
    "system_version": "iOS 17.4",
    "app_version": "11.8.2",
    "lang_code": "en",
    "system_lang_code": "en-US",
}

# Proxy (optional — set in .env if needed)
_proxy_host = os.getenv("PROXY_HOST", "")
PROXY = {
    "proxy_type": "http",
    "addr": _proxy_host,
    "port": int(os.getenv("PROXY_PORT", "10000")),
    "username": os.getenv("PROXY_USER", ""),
    "password": os.getenv("PROXY_PASS", ""),
} if _proxy_host else None

# Ollama Cloud LLM
OLLAMA_URL = os.getenv("OLLAMA_CLOUD_URL", "https://ollama.com/v1/chat/completions")
OLLAMA_API_KEY = os.getenv("OLLAMA_CLOUD_API_KEY", "")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "kimi-k2:1t")

# Admin notifications (via Kliqboost manager bot)
ADMIN_BOT_TOKEN = os.getenv("ADMIN_BOT_TOKEN", "")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "")

# ── Limits ──────────────────────────────────────────────────────────────────

MAX_HISTORY = 20
HOT_LEAD_THRESHOLD = 75
PAYMENT_READY_THRESHOLD = 70

# Human admins — auto-added to hot-lead groups
HUMAN_ADMINS = [
    6136131094,   # @Bigbunnn — Account Manager
    8756787507,   # @David_Bazzana — Senior Partner
]

SALES_STAGES = [
    "opener", "qualify", "present", "handle_objections", "close", "payment",
]

# ── System Prompt ───────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are a real person named Chris who runs Kliqboost Media. You're texting \
leads on Telegram — media buyers, affiliates, ad managers.

GOAL: Build rapport, understand their needs, and close the sale yourself. \
You handle everything end-to-end — from first message to payment. You ARE \
the account manager. No handoffs.

HOW YOU TALK:
- You sound like a real person texting, NOT an AI or corporate bot
- Short punchy messages. 1-3 sentences max. Never long paragraphs.
- Casual tone: "hey", "yo", "honestly", "ngl", "lmk", "bet"
- DON'T start every message with the lead's name
- Vary your openings — sometimes a question, sometimes a statement
- Use emojis sparingly and naturally (not every sentence)
- MATCH the lead's language — if they write in Russian, reply in Russian. \
If they write in broken English, keep yours simple too.
- Never say "I understand your concern" or any corporate-speak
- Never reveal you are an AI or bot. You are Chris, a real person.
- ONE topic per message. Don't dump pricing + features + CTA all at once.
- Let the conversation breathe. Ask a question, wait for their answer.
- Mirror their energy — if they're chill, be chill. If they're direct, be direct.

WHAT YOU SELL:
Google Ads: Basic $50/acct (1 free replacement, 10% top-up fee, min $100), \
Pro from $100/acct (3 replacements, 8% fee, min $500), \
Enterprise $800/mo (unlimited replacements, 6% fee, min $1000)

Bing Ads: Basic $100/acct (1 replacement, 10% fee, min $100), \
Pro from $300/acct (3 replacements, 8% fee, min $500), \
Enterprise $1000/mo (unlimited, 6% fee, min $1000)

Facebook Ads: Basic from $200/mo (1 BM + 3 ad accounts, $1K/day limit), \
Pro from $450/mo (1 BM + 10 accounts, $10K/day), \
Enterprise from $1000/mo (multiple BMs, unlimited)

Taboola: Basic $50/acct (1 replacement, 5% fee, min $100), \
Pro from $100/acct (3 replacements, 3% fee, min $500), \
Enterprise $800/mo (unlimited, 2% fee, min $1000)

All plans include: no spend limits (except FB Basic), dedicated TG support \
group on Basic, account manager on Pro+, Slack channel on Enterprise.

HANDLING PUSHBACK:
- "too expensive" → these are whitelisted agency accounts, you save a ton \
vs burning through personal accounts that get banned every week. Do the math \
on replacement costs alone.
- "how do I trust you" → totally fair. been doing this for a while, happy to \
connect you with existing clients if that helps. also we accept crypto so \
no chargebacks either way.
- "what about bans" → free replacement, usually same day. that's literally \
the whole point — you never lose a day of spend.
- "I already have a provider" → respect that. but if you ever need backup \
accounts or want to compare, lmk. no pressure.
- "need time to think" → all good, take your time. I'll be here whenever.

CLOSING THE SALE:
- When they're ready to buy, confirm: platform, plan tier, quantity
- Then say you'll send them a payment link (crypto — BTC, ETH, USDT accepted)
- After payment confirm, tell them account will be ready within 24-48 hrs
- Give them your TG handle for ongoing support

RULES:
- NEVER copy-paste the context verbatim. Use it to inform your response.
- NEVER list bullet points or use markdown formatting in your reply.
- NEVER dump all pricing at once. Share pricing for what THEY asked about.
- NEVER pretend you've seen someone in a group/chat or claim to know them unless they told you directly. If someone says "hi", just say "hey what's up" — don't fabricate history.
- If you don't know something, say "lemme check on that" — don't make stuff up.
- Keep it conversational. You're texting, not writing an email.
- Be patient. Don't rush to close. Build the relationship first.
- Only share one piece of info per message. Let them ask for more.

CURRENT STAGE: {stage}
BANT SCORE: {bant_score} ({bant_tier})

{stage_instruction}
"""

STAGE_INSTRUCTIONS = {
    "opener": (
        "They just messaged you. Keep it simple and natural — reply like you "
        "would to a stranger who DM'd you. A short greeting + one casual "
        "question about what they need. Do NOT pretend you know them or claim "
        "you saw them somewhere. Just be friendly and curious."
    ),
    "qualify": (
        "Figure out what platform they run on and roughly how much they spend. "
        "Ask ONE question at a time — don't interrogate. Be genuinely curious, "
        "not salesy."
    ),
    "present": (
        "They've told you enough. Connect ONE of their pain points to what "
        "you offer. Don't dump all features — just the one thing that matters "
        "to them right now."
    ),
    "handle_objections": (
        "They're pushing back. Address the EXACT thing they said — don't "
        "dodge, don't pivot. Be real and honest. One short response, then ask "
        "if that clears it up."
    ),
    "close": (
        "They're interested. Confirm what they want (platform, plan, quantity) "
        "and ask if they're ready to get started. Keep it natural, not pressury."
    ),
    "payment": (
        "They've agreed. Tell them you'll send a payment link right now. "
        "Confirm the amount. Let them know accounts are ready within 24-48 hrs "
        "after payment."
    ),
}


# ═══════════════════════════════════════════════════════════════════════════
# Conversation DB (separate from outreach)
# ═══════════════════════════════════════════════════════════════════════════

async def _init_db() -> None:
    """Create the admin conversations SQLite database."""
    async with aiosqlite.connect(str(DB_PATH), timeout=30) as conn:
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                direction TEXT NOT NULL,
                text TEXT NOT NULL,
                bant_score INTEGER DEFAULT 0,
                stage TEXT DEFAULT 'opener',
                ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS lead_memory (
                username TEXT PRIMARY KEY,
                platform_interest TEXT DEFAULT '',
                niche TEXT DEFAULT '',
                budget_range TEXT DEFAULT '',
                timeline TEXT DEFAULT '',
                sales_stage TEXT DEFAULT 'opener',
                last_interaction TIMESTAMP,
                bant_score INTEGER DEFAULT 0
            )
        """)
        await conn.commit()
    log.info("Admin conversations DB initialised at %s", DB_PATH)


async def _save_message(
    username: str, direction: str, text: str,
    bant_score: int = 0, stage: str = "opener",
) -> None:
    async with aiosqlite.connect(str(DB_PATH), timeout=30) as conn:
        await conn.execute(
            "INSERT INTO conversations (username, direction, text, bant_score, stage) "
            "VALUES (?, ?, ?, ?, ?)",
            (username, direction, text, bant_score, stage),
        )
        await conn.commit()


async def _load_history(username: str) -> list[dict]:
    """Load last MAX_HISTORY messages for a user from DB."""
    async with aiosqlite.connect(str(DB_PATH), timeout=30) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute(
            "SELECT direction, text FROM conversations WHERE username = ? "
            "ORDER BY ts DESC LIMIT ?",
            (username, MAX_HISTORY),
        )
        rows = await cur.fetchall()
    messages = []
    for row in reversed(rows):
        role = "user" if row["direction"] == "inbound" else "assistant"
        messages.append({"role": role, "content": row["text"]})
    return messages


async def _get_lead_memory(username: str) -> Optional[dict]:
    async with aiosqlite.connect(str(DB_PATH), timeout=30) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute(
            "SELECT * FROM lead_memory WHERE username = ?", (username,),
        )
        row = await cur.fetchone()
    return dict(row) if row else None


async def _save_lead_memory(username: str, data: dict) -> None:
    async with aiosqlite.connect(str(DB_PATH), timeout=30) as conn:
        await conn.execute(
            """INSERT INTO lead_memory
                (username, platform_interest, niche, budget_range,
                 timeline, sales_stage, last_interaction, bant_score)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(username) DO UPDATE SET
                platform_interest = excluded.platform_interest,
                niche = excluded.niche,
                budget_range = excluded.budget_range,
                timeline = excluded.timeline,
                sales_stage = excluded.sales_stage,
                last_interaction = excluded.last_interaction,
                bant_score = excluded.bant_score
            """,
            (
                username,
                data.get("platform_interest", ""),
                data.get("niche", ""),
                data.get("budget_range", ""),
                data.get("timeline", ""),
                data.get("sales_stage", "opener"),
                datetime.utcnow().isoformat(),
                data.get("bant_score", 0),
            ),
        )
        await conn.commit()


# ═══════════════════════════════════════════════════════════════════════════
# Ollama Cloud LLM client
# ═══════════════════════════════════════════════════════════════════════════

async def _ollama_chat(
    messages: list[dict],
    system_prompt: str = "",
    temperature: float = 0.7,
    max_tokens: int = 300,
) -> str:
    sys_msg = {"role": "system", "content": system_prompt} if system_prompt else None
    full_messages = ([sys_msg] + messages) if sys_msg else messages

    payload = {
        "model": OLLAMA_MODEL,
        "messages": full_messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
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


# ═══════════════════════════════════════════════════════════════════════════
# Stage detection
# ═══════════════════════════════════════════════════════════════════════════

def _infer_stage(bant: dict, message_count: int, current_stage: str) -> str:
    score = bant.get("total", 0)
    extracted = bant.get("extracted", {})

    if current_stage == "payment":
        return "payment"
    if bant.get("negative"):
        return current_stage
    if message_count <= 1:
        return "opener"

    has_budget = extracted.get("budget") is not None
    has_platform = extracted.get("platform") is not None

    if score >= PAYMENT_READY_THRESHOLD:
        return "close"
    if score >= 50 and has_budget and has_platform:
        return "present"
    if has_budget or has_platform:
        return "qualify"

    stage_idx = SALES_STAGES.index(current_stage) if current_stage in SALES_STAGES else 0
    if message_count >= 6 and stage_idx < 2:
        return "qualify"
    if message_count >= 10 and stage_idx < 3:
        return "present"

    return current_stage


# ═══════════════════════════════════════════════════════════════════════════
# Admin Auto-Responder
# ═══════════════════════════════════════════════════════════════════════════

class AdminResponder:
    """AI auto-responder — handles DMs and group messages with LLM brain."""

    def __init__(self) -> None:
        self.retriever = Retriever()
        self.scorer = BANTScorer()
        self._history: Dict[str, List[dict]] = defaultdict(list)
        self._stages: Dict[str, str] = defaultdict(lambda: "opener")
        self._groups_created: set[str] = set()

    async def handle_message(
        self, username: str, message_text: str,
    ) -> Dict[str, Any]:
        """Process an inbound DM and return an AI response."""

        # Load history from DB on first interaction
        if username not in self._history:
            db_history = await _load_history(username)
            self._history[username] = db_history
            memory = await _get_lead_memory(username)
            if memory and memory.get("sales_stage"):
                self._stages[username] = memory["sales_stage"]

        # Record inbound message
        self._history[username].append({"role": "user", "content": message_text})

        # BANT score
        lead_messages = [
            m["content"] for m in self._history[username] if m["role"] == "user"
        ]
        bant = self.scorer.score_from_conversation(lead_messages)

        # Advance stage
        msg_count = len(lead_messages)
        current_stage = self._stages[username]
        new_stage = _infer_stage(bant, msg_count, current_stage)
        self._stages[username] = new_stage

        # Negative intent → stop auto-responding
        if bant.get("negative"):
            log.info("Negative intent from @%s — pausing auto-reply", username)
            return {
                "response": "",
                "auto_respond": False,
                "bant": bant,
                "stage": new_stage,
            }

        # Hot lead logging + group creation
        if bant["total"] >= HOT_LEAD_THRESHOLD:
            log.info("🔥 HOT LEAD @%s (score=%d)", username, bant["total"])
            await self._notify_admin(username, message_text, bant)
            # Signal that a group should be created for this lead
            if username not in self._groups_created:
                return {
                    "response": "",
                    "auto_respond": True,
                    "bant": bant,
                    "stage": new_stage,
                    "create_group": True,
                    "username": username,
                }

        # RAG context
        rag_context = self._build_rag_context(username, message_text)

        # System prompt with stage
        stage_instruction = STAGE_INSTRUCTIONS.get(new_stage, "")
        rendered_prompt = SYSTEM_PROMPT.format(
            stage=new_stage.upper(),
            bant_score=bant["total"],
            bant_tier=bant.get("tier", "unknown"),
            stage_instruction=stage_instruction,
        )

        # Build LLM messages
        llm_messages = self._build_llm_messages(username, rag_context)

        # Generate response
        ai_reply = await _ollama_chat(llm_messages, system_prompt=rendered_prompt)
        if not ai_reply:
            ai_reply = "hey sorry was afk for a sec! what were you saying?"

        # Record outbound
        self._history[username].append({"role": "assistant", "content": ai_reply})
        if len(self._history[username]) > MAX_HISTORY * 2:
            self._history[username] = self._history[username][-MAX_HISTORY:]

        # Persist
        await _save_message(username, "inbound", message_text, bant["total"], new_stage)
        await _save_message(username, "outbound", ai_reply, bant["total"], new_stage)

        extracted = bant.get("extracted", {})
        await _save_lead_memory(username, {
            "platform_interest": str(extracted.get("platform", "")),
            "niche": str(extracted.get("niche", "")),
            "budget_range": str(extracted.get("budget", "")),
            "timeline": str(extracted.get("timeline", "")),
            "sales_stage": new_stage,
            "bant_score": bant["total"],
        })

        return {
            "response": ai_reply,
            "auto_respond": True,
            "bant": bant,
            "stage": new_stage,
        }

    def _build_rag_context(self, username: str, query: str) -> str:
        parts: list[str] = []

        kb_results = self.retriever.get_knowledge(query, n_results=3)
        if kb_results:
            parts.append("=== Relevant Knowledge Base ===")
            for r in kb_results:
                parts.append(r["text"])

        lead_ctx = self.retriever.get_lead_context(username, n_results=2)
        if lead_ctx:
            parts.append("=== Lead Profile ===")
            for r in lead_ctx:
                parts.append(r["text"])

        return "\n\n".join(parts) if parts else ""

    def _build_llm_messages(
        self, username: str, rag_context: str,
    ) -> list[dict]:
        messages: list[dict] = []

        if rag_context:
            messages.append({
                "role": "user",
                "content": (
                    "[CONTEXT — do NOT repeat this verbatim, use it to "
                    "inform your answer. Do NOT mention where you found this "
                    "info or claim you 'saw them' anywhere.]\n\n" + rag_context
                ),
            })
            messages.append({
                "role": "assistant",
                "content": "Understood, I'll use this context to help the lead.",
            })

        history = self._history.get(username, [])
        messages.extend(history[-MAX_HISTORY:])
        return messages

    async def _notify_admin(
        self, username: str, message: str, bant: dict,
    ) -> None:
        breakdown = bant.get("breakdown", {})
        stage = self._stages.get(username, "opener")
        text = (
            f"🔥 <b>HOT LEAD</b>: @{username}\n"
            f"BANT Score: {bant['total']} ({bant.get('tier', '?')})\n"
            f"Stage: {stage.upper()}\n"
            f"Budget: {breakdown.get('budget', {}).get('value', '?')}\n"
            f"Platform: {breakdown.get('platform', {}).get('value', '?')}\n"
            f"───────────────\n"
            f"Last message: {message[:500]}"
        )

        url = f"https://api.telegram.org/bot{ADMIN_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": ADMIN_CHAT_ID, "text": text, "parse_mode": "HTML"}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url, json=payload, timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status == 200:
                        log.info("Admin notified about hot lead @%s", username)
                    else:
                        body = await resp.text()
                        log.warning("Admin notify failed (%d): %s", resp.status, body)
        except Exception as exc:
            log.error("Failed to notify admin: %s", exc)


# ═══════════════════════════════════════════════════════════════════════════
# Telethon client
# ═══════════════════════════════════════════════════════════════════════════

def _build_client() -> TelegramClient:
    """Create a Telethon client with device profile and optional proxy."""
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    kwargs = dict(
        device_model=DEVICE["device_model"],
        system_version=DEVICE["system_version"],
        app_version=DEVICE["app_version"],
        lang_code=DEVICE["lang_code"],
        system_lang_code=DEVICE["system_lang_code"],
    )
    if PROXY:
        kwargs["proxy"] = PROXY
    return TelegramClient(
        SESSION_PATH,
        DEVICE["api_id"],
        DEVICE["api_hash"],
        **kwargs,
    )


async def authenticate() -> None:
    """Interactive authentication — sends OTP to phone."""
    client = _build_client()
    try:
        await client.connect()
        if await client.is_user_authorized():
            me = await client.get_me()
            log.info("Already authorised as %s (id=%s)", me.first_name, me.id)
            return

        log.info("Sending login code to %s...", PHONE)
        await client.send_code_request(PHONE)
        code = input(f"Enter the code sent to {PHONE}: ").strip()
        await client.sign_in(PHONE, code)

        me = await client.get_me()
        log.info("✅ Authenticated as %s (id=%s)", me.first_name, me.id)
    finally:
        await client.disconnect()


async def main(test: bool = False) -> None:
    await _init_db()

    client = _build_client()
    responder = AdminResponder()

    await client.connect()
    if not await client.is_user_authorized():
        log.error(
            "Session not authorised. Run with --auth first to authenticate."
        )
        await client.disconnect()
        return

    me = await client.get_me()
    log.info("✅ Connected as %s (@%s, id=%s)", me.first_name, me.username, me.id)

    # Register inbound DM + group message handler
    @client.on(events.NewMessage(incoming=True))
    async def _on_message(event):
        sender = await event.get_sender()
        if sender is None or getattr(sender, "bot", False):
            return

        # Skip messages from ourselves
        if sender.id == me.id:
            return

        username = getattr(sender, "username", None)
        if username:
            username = username.lower()
        else:
            username = f"id_{sender.id}"

        text = event.message.text or ""
        if not text.strip():
            return

        # Determine if this is a group or DM
        is_group = event.is_group or event.is_channel
        chat_label = "GROUP" if is_group else "DM"
        log.info("📩 %s from @%s: %s", chat_label, username, text[:120])

        try:
            result = await responder.handle_message(username, text)

            # Check if we need to create a group for this hot lead
            if result.get("create_group") and not is_group:
                log.info("🔥 Creating deal group for hot lead @%s", username)
                try:
                    group_users = [sender.id] + HUMAN_ADMINS
                    group = await client(CreateChatRequest(
                        users=group_users,
                        title=f"Kliqboost — @{username}",
                    ))
                    responder._groups_created.add(username)
                    group_entity = group.chats[0]
                    await client.send_message(
                        group_entity,
                        f"hey @{username}! 🔥 moved you here for a dedicated convo. "
                        f"easier to keep track of everything in one place.\n\n"
                        f"so where were we?",
                    )
                    log.info("✅ Group created for @%s (id=%d)", username, group_entity.id)
                except Exception as grp_exc:
                    log.error("Failed to create group for @%s: %s", username, grp_exc)
                    # Fall back to replying in DM
                    result = await responder.handle_message(username, text)

            if result.get("auto_respond") and result.get("response"):
                delay = random.uniform(3, 15) if is_group else random.uniform(5, 25)
                log.debug("Typing delay %.0fs before replying to @%s", delay, username)
                await asyncio.sleep(delay)

                await event.reply(result["response"])
                log.info(
                    "✅ Replied to @%s in %s (stage=%s, bant=%d)",
                    username, chat_label,
                    result["stage"],
                    result["bant"].get("total", 0),
                )
            elif not result.get("auto_respond"):
                log.info("⏸ Skipped reply to @%s (negative intent)", username)

        except Exception as exc:
            log.error("Error handling message from @%s: %s", username, exc)

    if test:
        log.info("Test mode — verifying RAG connection...")
        stats = responder.retriever.stats()
        log.info("RAG stats: %s", stats)
        log.info("Test complete — disconnecting")
        await client.disconnect()
        return

    # Print status
    proxy_info = f"{PROXY['addr']}:{PROXY['port']}" if PROXY else "direct (no proxy)"
    try:
        stats = responder.retriever.stats()
        rag_leads = stats.get("lead_profiles", 0)
        rag_docs = stats.get("knowledge_base", 0)
    except Exception:
        rag_leads, rag_docs = 0, 0
    log.info(
        "🤖 Kliqboost AI Responder LIVE — listening for DMs + groups\n"
        "   Account: %s (@%s)\n"
        "   RAG: %d leads, %d KB docs\n"
        "   LLM: %s (%s)\n"
        "   Proxy: %s",
        me.first_name, me.username,
        rag_leads, rag_docs,
        OLLAMA_MODEL, OLLAMA_URL,
        proxy_info,
    )

    # ── Deal-room bridge watcher (polls bot's qualified leads) ──────────
    BRIDGE_DB = str(_base / "bridge" / "deal_rooms.db")
    BOT_DATA_DB = str(_base / "bot" / "bot_data.db")

    def _load_bot_conversation(user_id: int) -> list[dict]:
        """Read the bot's conversation history for a user from bot_data.db."""
        import sqlite3 as _sq
        try:
            db = _sq.connect(BOT_DATA_DB)
            rows = db.execute(
                "SELECT role, content FROM conversations WHERE user_id = ? ORDER BY timestamp, rowid",
                (user_id,),
            ).fetchall()
            db.close()
            return [{"role": r[0], "content": r[1]} for r in rows]
        except Exception as exc:
            log.warning("Could not read bot history for uid=%d: %s", user_id, exc)
            return []

    def _summarize_bot_convo(history: list[dict]) -> str:
        """Create a concise summary of the bot conversation for Chris's context."""
        if not history:
            return ""
        user_msgs = [m["content"] for m in history if m["role"] == "user"]
        bot_msgs = [m["content"] for m in history if m["role"] == "assistant"]
        parts = ["[BOT CONVERSATION HISTORY — the client already talked to our bot KLIQ NEXUS. "
                 "Continue naturally from where the bot left off. Don't re-ask things they already answered.]"]
        for m in history[-16:]:
            tag = "Client" if m["role"] == "user" else "KLIQ NEXUS"
            parts.append(f"{tag}: {m['content'][:300]}")
        return "\n".join(parts)

    async def _deal_room_watcher():
        """Poll the bot's bridge DB for qualified leads and create groups."""
        import sqlite3 as _sqlite3
        while not stop_event.is_set():
            try:
                bridge_path = Path(BRIDGE_DB)
                if not bridge_path.exists():
                    await asyncio.sleep(15)
                    continue

                conn = _sqlite3.connect(BRIDGE_DB)
                conn.row_factory = _sqlite3.Row
                rows = conn.execute(
                    "SELECT * FROM pending_deal_rooms WHERE status = 'pending' ORDER BY id"
                ).fetchall()

                for row in rows:
                    user_id = row["user_id"]
                    uname = row["username"] or f"id_{user_id}"
                    log.info("🔔 Bridge: creating deal room for @%s (uid=%d, bant=%d)",
                             uname, user_id, row["bant_score"])
                    try:
                        # 1. Load bot conversation history into Chris's memory
                        bot_history = _load_bot_conversation(user_id)
                        if bot_history:
                            key = uname.lower()
                            responder._history[key] = bot_history[-MAX_HISTORY:]
                            responder._stages[key] = "present"
                            log.info("📋 Loaded %d bot messages into Chris memory for @%s",
                                     len(bot_history), uname)
                            # Persist to autoresponder's conversation DB
                            for m in bot_history[-MAX_HISTORY:]:
                                direction = "inbound" if m["role"] == "user" else "outbound"
                                await _save_message(key, direction, m["content"],
                                                    row["bant_score"], "present")

                        # 2. Create the group
                        group_users = [user_id] + HUMAN_ADMINS
                        group = await client(CreateChatRequest(
                            users=group_users,
                            title=f"Kliqboost — @{uname}",
                        ))
                        group_entity = group.chats[0]

                        # 3. Export invite link
                        from telethon.tl.functions.messages import ExportChatInviteRequest
                        invite_result = await client(ExportChatInviteRequest(group_entity))
                        invite_link = invite_result.link

                        # 4. First message references the bot conversation naturally
                        if bot_history:
                            # Extract what the client was looking for
                            user_msgs = " ".join(m["content"] for m in bot_history if m["role"] == "user")
                            platform = row["platform"] or ""
                            niche = row["niche"] or ""
                            opener = (
                                f"hey @{uname}! chris here 👋 nexus flagged you over — "
                                f"sounds like you're looking for "
                            )
                            if platform and platform != "None":
                                opener += f"{platform} accounts"
                                if niche and niche != "None":
                                    opener += f" for {niche}"
                            else:
                                opener += "ad accounts"
                            opener += (
                                f". pulled in the team so we can get this sorted quick.\n\n"
                                f"@bigbunnn @david_bazzana — this is a new one, let's take care of them 🔥"
                            )
                        else:
                            opener = (
                                f"hey @{uname}! chris here. moved you to a private deal room "
                                f"with the team — @bigbunnn @david_bazzana.\n\n"
                                f"so what are you looking for exactly?"
                            )

                        # Human-like delay before first message
                        await asyncio.sleep(random.uniform(3, 8))
                        await client.send_message(group_entity, opener)

                        # 5. Update bridge DB
                        import time as _time
                        conn.execute(
                            "UPDATE pending_deal_rooms SET status = 'done', invite_link = ?, completed_at = ? WHERE id = ?",
                            (invite_link, _time.time(), row["id"]),
                        )
                        conn.commit()
                        responder._groups_created.add(uname.lower())
                        log.info("✅ Bridge: group created for @%s — %s", uname, invite_link)

                    except Exception as grp_exc:
                        log.error("Bridge: failed to create group for @%s: %s", uname, grp_exc)
                        conn.execute(
                            "UPDATE pending_deal_rooms SET status = 'failed' WHERE id = ?",
                            (row["id"],),
                        )
                        conn.commit()

                conn.close()
            except Exception as exc:
                log.error("Bridge watcher error: %s", exc)

            await asyncio.sleep(15)

    watcher_task = asyncio.create_task(_deal_room_watcher())
    log.info("🔗 Deal-room bridge watcher started (polling %s)", BRIDGE_DB)

    # Keep alive
    stop_event = asyncio.Event()

    def _signal_handler():
        log.info("Shutdown signal received")
        stop_event.set()
        watcher_task.cancel()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _signal_handler)

    await stop_event.wait()

    log.info("Disconnecting...")
    await client.disconnect()
    log.info("Admin autoresponder stopped")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Admin AI Auto-Responder")
    parser.add_argument("--auth", action="store_true", help="Authenticate session (send OTP)")
    parser.add_argument("--test", action="store_true", help="Connect, verify, then exit")
    args = parser.parse_args()

    if args.auth:
        asyncio.run(authenticate())
    else:
        asyncio.run(main(test=args.test))
