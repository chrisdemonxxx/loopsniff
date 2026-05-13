"""Instagram DM adapter — same Messenger Platform Send API, channel='instagram'.

Requires:
- IG account connected to a Facebook Page (Business type)
- Page Access Token with instagram_manage_messages scope
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
# Reuse the Page Access Token; Instagram DMs route through the linked FB Page.
IG_PAGE_TOKEN = os.getenv("IG_PAGE_TOKEN") or os.getenv("MESSENGER_PAGE_TOKEN", "")


def parse_inbound(payload: dict) -> list[NormalizedMessage]:
    out: list[NormalizedMessage] = []
    try:
        if payload.get("object") != "instagram":
            return out
        for entry in payload.get("entry", []) or []:
            ig_account_id = entry.get("id", "")
            for ev in entry.get("messaging", []) or []:
                msg = ev.get("message") or {}
                if msg.get("is_echo"):
                    continue
                text = msg.get("text", "") or ""
                if not text.strip():
                    continue
                sender_id = (ev.get("sender") or {}).get("id", "")
                if not sender_id:
                    continue
                out.append(
                    NormalizedMessage(
                        channel="instagram",
                        conversation_id=f"ig:{ig_account_id}:{sender_id}",
                        user_id=sender_id,
                        username=sender_id,
                        text=text,
                        metadata={
                            "ig_account_id": ig_account_id,
                            "mid": msg.get("mid"),
                            "timestamp": ev.get("timestamp"),
                        },
                    )
                )
    except Exception as exc:
        log.exception("IG parse_inbound failed: %s", exc)
    return out


async def send_text(recipient_id: str, text: str, *, tag: str | None = None) -> dict[str, Any]:
    if not IG_PAGE_TOKEN:
        log.error("IG send_text: IG_PAGE_TOKEN/MESSENGER_PAGE_TOKEN missing")
        return {"error": "not_configured"}
    url = f"https://graph.facebook.com/{GRAPH_VERSION}/me/messages"
    payload: dict[str, Any] = {
        "recipient": {"id": recipient_id},
        "messaging_type": "RESPONSE" if not tag else "MESSAGE_TAG",
        "message": {"text": text[:1000]},
    }
    if tag:
        payload["tag"] = tag
    headers = {"Content-Type": "application/json"}
    params = {"access_token": IG_PAGE_TOKEN}
    timeout = aiohttp.ClientTimeout(total=30)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, json=payload, headers=headers, params=params) as resp:
                data = await resp.json()
                if resp.status != 200:
                    log.error("IG send %s: %s", resp.status, data)
                return data
    except Exception as exc:
        log.exception("IG send_text failed: %s", exc)
        return {"error": str(exc)}


async def handle_message(msg: NormalizedMessage) -> NormalizedResponse:
    resp = await respond(msg)
    if resp.text:
        await send_text(msg.user_id, resp.text)
    return resp
