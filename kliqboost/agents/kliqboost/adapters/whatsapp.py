"""WhatsApp Cloud API adapter.

Handles inbound webhook events and outbound Send API calls.
Coexistence mode: same number runs WhatsApp Business app + Cloud API in parallel.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import aiohttp

from agents.kliqboost.core import NormalizedMessage, respond
from agents.kliqboost.core.types import NormalizedResponse

log = logging.getLogger(__name__)

GRAPH_VERSION = os.getenv("META_GRAPH_VERSION", "v21.0")
WA_PHONE_NUMBER_ID = os.getenv("WA_PHONE_NUMBER_ID", "")
WA_ACCESS_TOKEN = os.getenv("WA_ACCESS_TOKEN", "")


def parse_inbound(payload: dict) -> list[NormalizedMessage]:
    """Convert a Cloud API webhook POST body into 0+ NormalizedMessage(s)."""
    out: list[NormalizedMessage] = []
    try:
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {}) or {}
                metadata = value.get("metadata", {}) or {}
                contacts = {c["wa_id"]: c for c in value.get("contacts", []) or []}
                for m in value.get("messages", []) or []:
                    if m.get("type") != "text":
                        # Acknowledge non-text but skip LLM call (image/audio/etc.)
                        log.info("WA non-text message type=%s skipped", m.get("type"))
                        continue
                    wa_id = m.get("from", "")
                    text = (m.get("text", {}) or {}).get("body", "") or ""
                    if not text.strip():
                        continue
                    contact = contacts.get(wa_id, {}) or {}
                    profile = contact.get("profile", {}) or {}
                    out.append(
                        NormalizedMessage(
                            channel="whatsapp",
                            conversation_id=f"wa:{wa_id}",
                            user_id=wa_id,
                            username=profile.get("name") or wa_id,
                            text=text,
                            metadata={
                                "wamid": m.get("id"),
                                "phone_number_id": metadata.get("phone_number_id"),
                                "display_phone_number": metadata.get("display_phone_number"),
                                "timestamp": m.get("timestamp"),
                            },
                        )
                    )
    except Exception as exc:
        log.exception("WA parse_inbound failed: %s", exc)
    return out


async def send_text(to_wa_id: str, text: str) -> dict[str, Any]:
    """POST a text message via Cloud API."""
    if not (WA_PHONE_NUMBER_ID and WA_ACCESS_TOKEN):
        log.error("WA send_text: missing WA_PHONE_NUMBER_ID or WA_ACCESS_TOKEN")
        return {"error": "not_configured"}
    url = f"https://graph.facebook.com/{GRAPH_VERSION}/{WA_PHONE_NUMBER_ID}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": to_wa_id,
        "type": "text",
        "text": {"body": text[:4000], "preview_url": False},
    }
    headers = {
        "Authorization": f"Bearer {WA_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    timeout = aiohttp.ClientTimeout(total=30)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                data = await resp.json()
                if resp.status != 200:
                    log.error("WA send %s: %s", resp.status, data)
                return data
    except Exception as exc:
        log.exception("WA send_text failed: %s", exc)
        return {"error": str(exc)}


async def handle_message(msg: NormalizedMessage) -> NormalizedResponse:
    resp = await respond(msg)
    if resp.text:
        await send_text(msg.user_id, resp.text)
    return resp
