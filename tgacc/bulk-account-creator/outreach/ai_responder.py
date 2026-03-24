"""AI-powered responder for the outreach engine.

Uses the AdFlux RAG system for context retrieval and Ollama Cloud for
generating natural sales responses.  Applies BANT scoring to every
conversation turn and routes hot leads to admin.
"""

from __future__ import annotations

import logging
import sys
from collections import defaultdict
from typing import Any, Dict, List, Optional

import aiohttp

# ── Wire up sibling projects ─────────────────────────────────────────────
sys.path.insert(0, "/home/cjs/tgacc/adflux-rag")
sys.path.insert(0, "/home/cjs/tgacc/bulk-account-creator")

from retrieval.retriever import Retriever          # noqa: E402
from outreach.scoring.bant_scorer import BANTScorer  # noqa: E402
from outreach import config as outreach_config       # noqa: E402
from outreach import db                              # noqa: E402
from outreach.models import Lead                     # noqa: E402

log = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────

OLLAMA_URL = "https://api.ollamacloud.com/v1/chat/completions"
OLLAMA_API_KEY = "5d92bf191608457d951f3eea8459b66e"
OLLAMA_MODEL = "llama3.1:8b"

SYSTEM_PROMPT = (
    "You are a sales representative for AdFlux Media, a premium agency ad "
    "account provider. You help media buyers get whitelisted ad accounts for "
    "Google, Meta, TikTok, Taboola, Outbrain. Be professional but casual. "
    "Keep responses under 3 sentences. Ask qualifying questions about their "
    "budget, platforms, and niche. Never be pushy."
)

HOT_LEAD_THRESHOLD = 75
MAX_HISTORY = 10

# ── Ollama Cloud client ──────────────────────────────────────────────────


async def _ollama_chat(
    messages: list[dict],
    system_prompt: str = SYSTEM_PROMPT,
    temperature: float = 0.7,
    max_tokens: int = 300,
) -> str:
    """Send a chat completion request to Ollama Cloud."""
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [{"role": "system", "content": system_prompt}] + messages,
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


# ── AI Responder ─────────────────────────────────────────────────────────


class AIResponder:
    """Generate AI sales replies using RAG context + Ollama Cloud."""

    def __init__(self) -> None:
        self.retriever = Retriever()
        self.scorer = BANTScorer()
        # conversation history keyed by lead username
        self._history: Dict[str, List[dict]] = defaultdict(list)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def handle_reply(
        self,
        lead: Lead,
        message_text: str,
    ) -> Dict[str, Any]:
        """Process an inbound lead reply and return an AI response.

        Returns a dict with keys:
            response     – the AI-generated reply text (empty if human takeover)
            bant         – full BANT scoring result
            auto_respond – True if the bot should send the response
        """
        username = lead.username

        # 1. Record lead message in conversation history
        self._append_history(username, role="user", content=message_text)

        # 2. BANT-score the full conversation
        lead_messages = [
            m["content"] for m in self._history[username] if m["role"] == "user"
        ]
        bant = self.scorer.score_from_conversation(lead_messages)

        # 3. Check for negative intent → stop auto-responding
        if bant.get("negative"):
            log.info("Negative intent from @%s — stopping auto-reply", username)
            await db.update_lead(username, status="dead", bant_score=bant["total"])
            return {
                "response": "",
                "bant": bant,
                "auto_respond": False,
            }

        # 4. Hot lead → notify admin, hand over to human
        if bant["total"] >= HOT_LEAD_THRESHOLD:
            log.info(
                "🔥 HOT LEAD @%s (score=%d) — handing to admin",
                username,
                bant["total"],
            )
            await db.update_lead(username, status="hot", bant_score=bant["total"])
            await self._notify_admin(lead, message_text, bant)
            return {
                "response": "",
                "bant": bant,
                "auto_respond": False,
            }

        # 5. Retrieve RAG context
        rag_context = self._build_rag_context(username, message_text)

        # 6. Build message list for Ollama Cloud
        llm_messages = self._build_llm_messages(username, rag_context)

        # 7. Generate response
        ai_reply = await _ollama_chat(llm_messages)
        if not ai_reply:
            ai_reply = (
                "Hey! Thanks for reaching out. Let me get the right person "
                "to help you — one moment!"
            )

        # 8. Record assistant message
        self._append_history(username, role="assistant", content=ai_reply)

        # 9. Update lead status
        await db.update_lead(
            username,
            status="qualified" if bant["total"] >= 50 else "replied",
            bant_score=bant["total"],
        )

        return {
            "response": ai_reply,
            "bant": bant,
            "auto_respond": True,
        }

    # ------------------------------------------------------------------
    # RAG context
    # ------------------------------------------------------------------

    def _build_rag_context(self, username: str, query: str) -> str:
        """Retrieve knowledge-base + lead context from ChromaDB."""
        parts: list[str] = []

        # Knowledge-base docs
        kb_results = self.retriever.get_knowledge(query, n_results=3)
        if kb_results:
            parts.append("=== Relevant Knowledge Base ===")
            for r in kb_results:
                parts.append(r["text"])

        # Lead profile
        lead_ctx = self.retriever.get_lead_context(username, n_results=2)
        if lead_ctx:
            parts.append("=== Lead Profile ===")
            for r in lead_ctx:
                parts.append(r["text"])

        return "\n\n".join(parts) if parts else ""

    # ------------------------------------------------------------------
    # LLM message building
    # ------------------------------------------------------------------

    def _build_llm_messages(
        self, username: str, rag_context: str
    ) -> list[dict]:
        """Compose the message list sent to Ollama Cloud."""
        messages: list[dict] = []

        # Inject RAG context as a system-level user message
        if rag_context:
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "[CONTEXT — do NOT repeat this verbatim, use it to "
                        "inform your answer]\n\n" + rag_context
                    ),
                }
            )
            messages.append(
                {
                    "role": "assistant",
                    "content": "Understood, I'll use this context to help the lead.",
                }
            )

        # Append conversation history (last MAX_HISTORY messages)
        history = self._history.get(username, [])
        messages.extend(history[-MAX_HISTORY:])

        return messages

    # ------------------------------------------------------------------
    # Conversation history
    # ------------------------------------------------------------------

    def _append_history(self, username: str, role: str, content: str) -> None:
        self._history[username].append({"role": role, "content": content})
        # Trim to prevent unbounded growth
        if len(self._history[username]) > MAX_HISTORY * 2:
            self._history[username] = self._history[username][-MAX_HISTORY:]

    def clear_history(self, username: str) -> None:
        """Wipe conversation history for a lead."""
        self._history.pop(username, None)

    # ------------------------------------------------------------------
    # Admin notification
    # ------------------------------------------------------------------

    async def _notify_admin(
        self, lead: Lead, message: str, bant: dict
    ) -> None:
        """Send hot-lead card to admin via Telegram Bot API."""
        breakdown = bant.get("breakdown", {})
        text = (
            f"🔥 <b>HOT LEAD</b>: @{lead.username}\n"
            f"Source: {lead.source}\n"
            f"BANT Score: {bant['total']} ({bant['tier']})\n"
            f"Budget: {breakdown.get('budget', {}).get('value', '?')}\n"
            f"Platform: {breakdown.get('platform', {}).get('value', '?')}\n"
            f"Niche: {breakdown.get('niche', {}).get('value', '?')}\n"
            f"Timeline: {breakdown.get('timeline', {}).get('value', '?')}\n"
            f"───────────────\n"
            f"Last message: {message[:500]}"
        )

        url = (
            f"https://api.telegram.org/bot{outreach_config.ADMIN_BOT_TOKEN}"
            f"/sendMessage"
        )
        payload = {
            "chat_id": outreach_config.ADMIN_CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status == 200:
                        log.info("Admin notified about hot lead @%s", lead.username)
                    else:
                        body = await resp.text()
                        log.warning(
                            "Admin notify failed (%d): %s", resp.status, body
                        )
        except Exception as exc:
            log.error("Failed to notify admin: %s", exc)
