"""AI-powered responder for the outreach engine.

Uses the AdFlux RAG system for context retrieval and Ollama Cloud for
generating natural sales responses.  Applies BANT scoring to every
conversation turn, tracks sales stages, generates payment links, and
routes hot leads / escalations to admin.
"""

from __future__ import annotations

import logging
import os
import sys
import uuid
from collections import defaultdict
from typing import Any, Dict, List, Optional

import aiohttp

# ── Wire up sibling projects ─────────────────────────────────────────────
sys.path.insert(0, "/home/cjs/tgacc/adflux-rag")
sys.path.insert(0, "/home/cjs/tgacc/bulk-account-creator")

from retrieval.retriever import Retriever            # noqa: E402
from outreach.scoring.bant_scorer import BANTScorer  # noqa: E402
from outreach import config as outreach_config       # noqa: E402
from outreach import db                              # noqa: E402
from outreach.models import Lead                     # noqa: E402
from outreach.commission import calculate_topup_cost # noqa: E402
from outreach.payment_engine import NOWPaymentsClient  # noqa: E402
from outreach.escalation import EscalationManager    # noqa: E402

log = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────

OLLAMA_URL = "https://ollama.com/v1/chat/completions"
# Hardcoded — system env has stale values that break the responder
OLLAMA_API_KEY = "0af8b3e923b444d481d7fa1b43e8ec78.wfmKhz4OnJ-47RX2tPAt8ePU"
OLLAMA_MODEL = "kimi-k2:1t"

# Sales stages (linear progression)
SALES_STAGES = ["opener", "qualify", "present", "handle_objections", "close", "payment"]

SYSTEM_PROMPT = """\
You are a real person named Alex who works at AdFlux Media. You're texting \
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
- Never reveal you are an AI or bot. You are Alex, a real person.
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
- If you don't know something, say "lemme check on that" — don't make stuff up.
- Keep it conversational. You're texting, not writing an email.
- Be patient. Don't rush to close. Build the relationship first.
- Only share one piece of info per message. Let them ask for more.

CURRENT STAGE: {stage}
BANT SCORE: {bant_score} ({bant_tier})

{stage_instruction}
"""

STAGE_INSTRUCTIONS = {
    "opener": "Break the ice. Mention something specific about them — a post, their niche, mutual group. Don't sell anything yet, just start a convo. One casual question max.",
    "qualify": "Figure out what platform they run on and roughly how much they spend. Ask ONE question at a time — don't interrogate. Be genuinely curious, not salesy.",
    "present": "They've told you enough. Connect ONE of their pain points to what you offer. Don't dump all features — just the one thing that matters to them right now.",
    "handle_objections": "They're pushing back. Address the EXACT thing they said — don't dodge, don't pivot. Be real and honest. One short response, then ask if that clears it up.",
    "close": "They're interested. Confirm what they want (platform, plan, quantity) and ask if they're ready to get started. Keep it natural, not pressury.",
    "payment": "They've agreed. Tell them you'll send a payment link right now. Confirm the amount. Let them know accounts are ready within 24-48 hrs after payment.",
}

HOT_LEAD_THRESHOLD = 75
MAX_HISTORY = 20
PAYMENT_READY_THRESHOLD = 70

# ── Ollama Cloud client ──────────────────────────────────────────────────


async def _ollama_chat(
    messages: list[dict],
    system_prompt: str = "",
    temperature: float = 0.7,
    max_tokens: int = 300,
) -> str:
    """Send a chat completion request to Ollama Cloud."""
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


# ── Stage detection helpers ──────────────────────────────────────────────

def _infer_stage(bant: dict, message_count: int, current_stage: str) -> str:
    """Advance the sales stage based on BANT score and conversation depth."""
    score = bant.get("total", 0)
    extracted = bant.get("extracted", {})

    # Already in payment stage — stay there
    if current_stage == "payment":
        return "payment"

    # Negative intent → don't advance
    if bant.get("negative"):
        return current_stage

    # First message → opener
    if message_count <= 1:
        return "opener"

    # Has budget + platform info → ready to present
    has_budget = extracted.get("budget") is not None
    has_platform = extracted.get("platform") is not None

    if score >= PAYMENT_READY_THRESHOLD:
        return "close"
    if score >= 50 and has_budget and has_platform:
        return "present"
    if has_budget or has_platform:
        return "qualify"

    # Conversation depth-based fallback
    stage_idx = SALES_STAGES.index(current_stage) if current_stage in SALES_STAGES else 0
    if message_count >= 6 and stage_idx < 2:
        return "qualify"
    if message_count >= 10 and stage_idx < 3:
        return "present"

    return current_stage


# ── AI Responder ─────────────────────────────────────────────────────────


class AIResponder:
    """Generate AI sales replies using RAG context + Ollama Cloud.

    Enhanced with:
    - Sales stage tracking (opener → qualify → present → handle_objections → close → payment)
    - Conversation memory from outreach DB (last 20 messages)
    - Payment link generation via NOWPayments
    - BANT auto-scoring after each exchange
    - Multi-channel escalation for unresolvable issues
    """

    def __init__(self) -> None:
        self.retriever = Retriever()
        self.scorer = BANTScorer()
        self.payments = NOWPaymentsClient()
        self.escalation = EscalationManager()
        # In-memory conversation history keyed by lead username
        self._history: Dict[str, List[dict]] = defaultdict(list)
        # Sales stage per lead
        self._stages: Dict[str, str] = defaultdict(lambda: "opener")

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
            stage        – current sales stage
            payment_link – invoice URL if payment stage triggered (or None)
        """
        username = lead.username

        # 0. Load history + persistent memory from DB on first interaction
        if username not in self._history:
            await self._load_history_from_db(username)
            memory = await db.get_lead_memory(username)
            if memory and memory.get("sales_stage"):
                self._stages[username] = memory["sales_stage"]

        # 1. Record lead message in conversation history
        self._append_history(username, role="user", content=message_text)

        # 2. BANT-score the full conversation
        lead_messages = [
            m["content"] for m in self._history[username] if m["role"] == "user"
        ]
        bant = self.scorer.score_from_conversation(lead_messages)

        # 3. Advance sales stage
        msg_count = len([m for m in self._history[username] if m["role"] == "user"])
        current_stage = self._stages[username]
        new_stage = _infer_stage(bant, msg_count, current_stage)
        self._stages[username] = new_stage

        # 4. Check for negative intent → stop auto-responding
        if bant.get("negative"):
            log.info("Negative intent from @%s — stopping auto-reply", username)
            await db.update_lead(username, status="dead", bant_score=bant["total"])
            return {
                "response": "",
                "bant": bant,
                "auto_respond": False,
                "stage": new_stage,
                "payment_link": None,
            }

        # 5. Hot lead → log it (AI handles the sale, only alert on payment stage)
        if bant["total"] >= HOT_LEAD_THRESHOLD:
            log.info(
                "🔥 HOT LEAD @%s (score=%d) — AI continuing sale",
                username,
                bant["total"],
            )
            await db.update_lead(username, status="hot", bant_score=bant["total"])
            # Only notify admin when lead reaches payment stage (ready to pay)
            if new_stage == "payment":
                await self._notify_admin(lead, message_text, bant)

        # 6. Retrieve RAG context + persistent memory
        rag_context = await self._build_rag_context(username, message_text)

        # 7. Build system prompt with stage context
        stage_instruction = STAGE_INSTRUCTIONS.get(new_stage, "")
        rendered_prompt = SYSTEM_PROMPT.format(
            stage=new_stage.upper(),
            bant_score=bant["total"],
            bant_tier=bant.get("tier", "unknown"),
            stage_instruction=stage_instruction,
        )

        # 8. Build message list for Ollama Cloud
        llm_messages = self._build_llm_messages(username, rag_context)

        # 9. Generate response
        ai_reply = await _ollama_chat(llm_messages, system_prompt=rendered_prompt)
        if not ai_reply:
            ai_reply = (
                "hey sorry was afk for a sec! what were you saying?"
            )
            # Escalate if AI fails to generate
            await self.escalation.escalate(
                client_name=username,
                issue="AI failed to generate response",
                session_id=f"lead-{username}",
                priority="medium",
            )

        # 10. Payment link generation if in close/payment stage
        payment_link = None
        if new_stage in ("close", "payment") and bant["total"] >= PAYMENT_READY_THRESHOLD:
            payment_link = await self._generate_payment_link(lead, bant)
            if payment_link:
                ai_reply += (
                    f"\n\nHere's your payment link: {payment_link}"
                    "\nPay with BTC, ETH, USDT, or 70+ other cryptos 🔐"
                )
                self._stages[username] = "payment"

        # 11. Record assistant message
        self._append_history(username, role="assistant", content=ai_reply)

        # 12. Update lead status + BANT score in DB
        if bant["total"] >= HOT_LEAD_THRESHOLD:
            status = "hot"
        elif bant["total"] >= 50:
            status = "qualified"
        else:
            status = "replied"

        await db.update_lead(
            username,
            status=status,
            bant_score=bant["total"],
        )

        # 13. Save persistent memory
        extracted = bant.get("extracted", {})
        await db.save_lead_memory(username, {
            "platform_interest": str(extracted.get("platform", "")),
            "niche": str(extracted.get("niche", "")),
            "budget_range": str(extracted.get("budget", "")),
            "timeline": str(extracted.get("timeline", "")),
            "pain_points": "",
            "objections": "",
            "preferences": "",
            "sales_stage": new_stage,
            "session_summary": "",
        })

        return {
            "response": ai_reply,
            "bant": bant,
            "auto_respond": True,
            "stage": new_stage,
            "payment_link": payment_link,
        }

    # ------------------------------------------------------------------
    # Payment link generation
    # ------------------------------------------------------------------

    async def _generate_payment_link(
        self, lead: Lead, bant: dict,
    ) -> Optional[str]:
        """Create a NOWPayments invoice for the lead's likely spend."""
        try:
            budget_val = bant.get("extracted", {}).get("budget", "$1k-$5k")
            niche = bant.get("extracted", {}).get("niche", "other") or "other"

            amount_map = {
                "$50k+": 50000,
                "$10k-$50k": 10000,
                "$5k-$10k": 5000,
                "$1k-$5k": 2000,
                "< $1k": 500,
            }
            ad_spend = amount_map.get(budget_val, 500)

            plan = "enterprise" if ad_spend >= 10000 else "growth" if ad_spend >= 2000 else "starter"
            cost = calculate_topup_cost(ad_spend, plan, niche)

            invoice = await self.payments.create_invoice(
                price_amount=cost["total"],
                price_currency="usd",
                pay_currency="btc",
                order_id=f"adflux-{lead.username}-{uuid.uuid4().hex[:8]}",
                order_description=(
                    f"AdFlux {plan.title()} — ${ad_spend} ad spend top-up for @{lead.username}"
                ),
            )

            return invoice.get("invoice_url")
        except Exception as exc:
            log.error("Payment link generation failed for @%s: %s", lead.username, exc)
            return None

    # ------------------------------------------------------------------
    # DB-backed conversation memory
    # ------------------------------------------------------------------

    async def _load_history_from_db(self, username: str) -> None:
        """Load the last MAX_HISTORY messages for a lead from the outreach DB."""
        try:
            messages = await db.get_messages(lead_username=username)
            recent = messages[-MAX_HISTORY:] if len(messages) > MAX_HISTORY else messages

            for msg in recent:
                role = "user" if msg.direction == "inbound" else "assistant"
                self._history[username].append({
                    "role": role,
                    "content": msg.text,
                })
            log.debug("Loaded %d messages from DB for @%s", len(recent), username)
        except Exception as exc:
            log.warning("Failed to load history from DB for @%s: %s", username, exc)

    # ------------------------------------------------------------------
    # RAG context
    # ------------------------------------------------------------------

    async def _build_rag_context(self, username: str, query: str) -> str:
        """Retrieve knowledge-base + lead context from ChromaDB + persistent memory."""
        parts: list[str] = []

        # Persistent memory from SQLite
        memory = await db.get_lead_memory(username)
        if memory:
            mem_parts = []
            for key in ("platform_interest", "niche", "budget_range", "timeline",
                        "pain_points", "objections", "preferences"):
                val = memory.get(key, "")
                if val:
                    mem_parts.append(f"  {key}: {val}")
            if memory.get("session_summary"):
                mem_parts.append(f"  Previous conversation summary: {memory['session_summary']}")
            if mem_parts:
                parts.append("=== Lead Memory (from previous conversations) ===\n" + "\n".join(mem_parts))

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
        self, username: str, rag_context: str,
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
        """Wipe conversation history and reset stage for a lead."""
        self._history.pop(username, None)
        self._stages.pop(username, None)

    def get_stage(self, username: str) -> str:
        """Return the current sales stage for a lead."""
        return self._stages.get(username, "opener")

    def set_stage(self, username: str, stage: str) -> None:
        """Manually override the sales stage for a lead."""
        if stage in SALES_STAGES:
            self._stages[username] = stage
        else:
            log.warning("Invalid stage %r — must be one of %s", stage, SALES_STAGES)

    # ------------------------------------------------------------------
    # Admin notification
    # ------------------------------------------------------------------

    async def _notify_admin(
        self, lead: Lead, message: str, bant: dict,
    ) -> None:
        """Send hot-lead card to admin via Telegram Bot API."""
        breakdown = bant.get("breakdown", {})
        stage = self._stages.get(lead.username, "opener")
        text = (
            f"🔥 <b>HOT LEAD</b>: @{lead.username}\n"
            f"Source: {lead.source}\n"
            f"BANT Score: {bant['total']} ({bant['tier']})\n"
            f"Stage: {stage.upper()}\n"
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
                            "Admin notify failed (%d): %s", resp.status, body,
                        )
        except Exception as exc:
            log.error("Failed to notify admin: %s", exc)

    # ------------------------------------------------------------------
    # Escalation shortcut
    # ------------------------------------------------------------------

    async def escalate_issue(
        self, username: str, issue: str, priority: str = "high",
    ) -> dict:
        """Manually trigger escalation for a lead's issue."""
        return await self.escalation.escalate(
            client_name=username,
            issue=issue,
            session_id=f"lead-{username}",
            priority=priority,
        )
