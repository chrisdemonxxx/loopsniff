"""
AI Account Manager Agent for AdFlux Client Portal.

Professional support AI that:
- Answers billing, account status, and service questions
- Validates proofs (screenshots, transaction IDs) uploaded by clients
- Creates support tickets automatically when human intervention needed
- Uses RAG (ChromaDB knowledge base) for contextual answers
"""

import logging
import uuid
import aiohttp
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import get_settings
from app.models import Ticket, TicketMessage, Client, AdAccount, Order, Subscription

log = logging.getLogger(__name__)
settings = get_settings()

ACCOUNT_MANAGER_PROMPT = """You are an AdFlux Media Account Manager — a professional, friendly support agent.

YOUR ROLE:
- Help clients with account inquiries, billing questions, top-up support, and technical issues
- You represent AdFlux Media's support team and should act like a real human support agent
- Be professional, empathetic, and solution-oriented

CAPABILITIES:
- Answer questions about ad account status, balances, spending
- Help with billing inquiries and payment confirmations
- Guide clients through top-up process (crypto payments via NOWPayments)
- Explain AdFlux services and pricing plans
- Validate payment proofs when clients share transaction details

WHEN TO CREATE A TICKET:
- Client reports a bug or technical issue you cannot resolve
- Payment dispute or refund request
- Account ban or restriction appeal
- Custom pricing or enterprise plan request
- Any issue requiring admin access or manual intervention
- Client explicitly asks to speak with a human

TICKET CREATION:
When creating a ticket, gather:
1. Clear description of the issue
2. Any relevant proof (transaction IDs, screenshots mentioned)
3. Urgency level
Then say: [TICKET_CREATE: subject="...", category="...", priority="...", summary="..."]

COMMUNICATION STYLE:
- Professional but warm — not robotic
- Use client's name when known
- Acknowledge their concern before providing solutions
- Be concise — avoid walls of text
- If unsure, say "Let me create a ticket for our team to look into this" rather than guessing

CONTEXT ABOUT ADFLUX:
- AdFlux Media provides ad accounts (Facebook, Google, TikTok, Snapchat)
- Clients top up via crypto (USDT, BTC, ETH) through NOWPayments
- Commission rates: Starter 15%, Growth 12%, Enterprise 8-10%
- Support available via Telegram bot (@addfluxmedia_bot) and client portal
"""

TICKET_CATEGORIES = {
    "billing": ["payment", "invoice", "charge", "refund", "transaction", "top-up", "topup", "deposit"],
    "technical": ["bug", "error", "broken", "not working", "crash", "issue", "glitch"],
    "account": ["ban", "banned", "suspended", "restricted", "account", "access", "login"],
    "general": [],
}


def detect_category(text: str) -> str:
    text_lower = text.lower()
    for cat, keywords in TICKET_CATEGORIES.items():
        if any(kw in text_lower for kw in keywords):
            return cat
    return "general"


def detect_priority(text: str) -> str:
    text_lower = text.lower()
    urgent_kw = ["urgent", "asap", "emergency", "immediately", "critical", "banned", "lost money"]
    high_kw = ["important", "refund", "payment failed", "not received", "suspended"]
    if any(kw in text_lower for kw in urgent_kw):
        return "urgent"
    if any(kw in text_lower for kw in high_kw):
        return "high"
    return "medium"


async def get_account_manager_response(
    message: str,
    context: list[dict] | None = None,
    client_info: dict | None = None,
) -> str:
    """Get AI Account Manager response using Ollama Cloud."""
    messages = [{"role": "system", "content": ACCOUNT_MANAGER_PROMPT}]

    if client_info:
        info_text = f"\nCLIENT CONTEXT:\n- Name: {client_info.get('name', 'Unknown')}\n"
        if client_info.get("company"):
            info_text += f"- Company: {client_info['company']}\n"
        if client_info.get("plan"):
            info_text += f"- Plan: {client_info['plan']}\n"
        if client_info.get("accounts"):
            info_text += f"- Active Accounts: {client_info['accounts']}\n"
        messages[0]["content"] += info_text

    if context:
        messages.extend(context)

    messages.append({"role": "user", "content": message})

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{settings.OLLAMA_CLOUD_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.OLLAMA_CLOUD_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.OLLAMA_MODEL,
                    "messages": messages,
                    "max_tokens": 600,
                    "temperature": 0.6,
                },
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status != 200:
                    log.error("Account Manager AI returned %d", resp.status)
                    return "I apologize for the inconvenience. Let me create a support ticket for our team to assist you directly."
                data = await resp.json()
                return data["choices"][0]["message"]["content"]
    except Exception as e:
        log.exception("Account Manager AI error: %s", e)
        return "I'm experiencing a temporary issue. Let me create a ticket so our team can help you right away."


async def maybe_create_ticket(
    ai_response: str,
    client_id: str,
    conversation_summary: str,
    db: AsyncSession,
) -> dict | None:
    """Parse AI response for ticket creation markers and create ticket if found."""
    if "[TICKET_CREATE:" not in ai_response:
        return None

    try:
        import re
        match = re.search(r'\[TICKET_CREATE:([^\]]+)\]', ai_response)
        if not match:
            return None
        parts = match.group(1).strip()

        subject = "Support Request"
        category = "general"
        priority = "medium"
        summary = conversation_summary

        for part in parts.split(","):
            part = part.strip()
            if "=" in part:
                key, val = part.split("=", 1)
                key = key.strip().strip('"').strip("'")
                val = val.strip().strip('"').strip("'")
                if key == "subject":
                    subject = val
                elif key == "category":
                    category = val
                elif key == "priority":
                    priority = val
                elif key == "summary":
                    summary = val

        ticket = Ticket(
            client_id=uuid.UUID(client_id),
            subject=subject,
            category=category,
            priority=priority,
            status="open",
            created_by_type="ai",
        )
        db.add(ticket)
        await db.flush()

        initial_msg = TicketMessage(
            ticket_id=ticket.id,
            sender_type="ai",
            text=f"Ticket auto-created by AI Account Manager.\n\nSummary: {summary}",
            is_internal=True,
        )
        db.add(initial_msg)
        await db.flush()

        return {
            "ticket_id": str(ticket.id),
            "subject": subject,
            "category": category,
            "priority": priority,
        }
    except Exception as e:
        log.error("Failed to parse/create ticket from AI response: %s", e)
        return None


async def get_client_context(client_id: str, db: AsyncSession) -> dict:
    """Fetch client info for AI context."""
    try:
        cid = uuid.UUID(client_id)
        result = await db.execute(select(Client).where(Client.id == cid))
        client = result.scalar_one_or_none()
        if not client:
            return {}

        acct_result = await db.execute(
            select(AdAccount).where(AdAccount.client_id == cid, AdAccount.status == "active")
        )
        accounts = acct_result.scalars().all()

        return {
            "name": client.name,
            "company": client.company,
            "plan": client.plan,
            "accounts": len(accounts),
        }
    except Exception as e:
        log.error("Failed to get client context: %s", e)
        return {}
