"""Single entry point for any channel: ``await respond(NormalizedMessage)``."""

from __future__ import annotations

import logging
import os
from typing import Any

from .types import NormalizedMessage, NormalizedResponse
from .prompts import PROMPT_VERSION, render_prompt
from .llm_client import chat as llm_chat
from .rag_client import format_context, get_retriever
from .memory import load_history, message_count, save_turn
from .guardrails import evaluate_inbound_text, evaluate_outbound_text

log = logging.getLogger(__name__)

try:
    from scoring.bant_scorer import BANTScorer  # type: ignore
    _BANT = BANTScorer()
except Exception as exc:  # pragma: no cover
    log.warning("BANTScorer unavailable: %s", exc)
    _BANT = None

USDT_ERC20 = os.getenv("USDT_ERC20_ADDRESS", "")
BTC_ADDRESS = os.getenv("BTC_ADDRESS", "")
ETH_ADDRESS = os.getenv("ETH_ADDRESS", "")
HOT_LEAD_THRESHOLD = int(os.getenv("HOT_LEAD_THRESHOLD", "60"))
PAYMENT_READY_THRESHOLD = int(os.getenv("PAYMENT_READY_THRESHOLD", "70"))


def _infer_stage(bant: dict, msg_count: int) -> str:
    score = bant.get("total", 0)
    extracted = bant.get("extracted", {}) if isinstance(bant, dict) else {}
    has_budget = bool(extracted.get("budget") and extracted["budget"] != "unknown")
    has_platform = bool(extracted.get("platform") and extracted["platform"] != "unknown")
    if score >= PAYMENT_READY_THRESHOLD:
        return "close"
    if score >= 50 and has_budget and has_platform:
        return "present"
    if msg_count <= 1:
        return "opener"
    return "qualify"


def _score_bant(text_history: list[str]) -> dict:
    if _BANT is None:
        return {"total": 0, "tier": "cold", "extracted": {}}
    if hasattr(_BANT, "score_from_conversation"):
        return _BANT.score_from_conversation(text_history)
    return _BANT.score_from_text(" ".join(text_history))


async def respond(msg: NormalizedMessage) -> NormalizedResponse:
    g_in = evaluate_inbound_text(msg.text)
    if getattr(g_in, "action", "allow") == "block_and_escalate":
        return NormalizedResponse(
            text="", channel=msg.channel, conversation_id=msg.conversation_id,
            guardrail_action="block_and_escalate", action="escalate",
            action_payload={"reason": getattr(g_in, "reason", "guardrail")},
        )

    history = await load_history(msg.channel, msg.conversation_id, limit=20)
    msg_count = await message_count(msg.channel, msg.conversation_id)

    user_texts = [m["content"] for m in history if m["role"] == "user"] + [msg.text]
    bant = _score_bant(user_texts)
    stage = _infer_stage(bant, msg_count)

    rag_block = ""
    try:
        retriever = get_retriever()
        ctx = retriever.get_full_context(
            username=msg.username or msg.user_id, query=msg.text, n_lead=2, n_kb=3
        )
        rag_block = format_context(ctx)
    except Exception as exc:
        log.warning("RAG lookup failed: %s", exc)

    system_prompt = render_prompt(
        channel=msg.channel,
        role=msg.role,
        stage=stage,
        bant_score=bant.get("total", 0),
        bant_tier=bant.get("tier", "cold"),
        rag_context=rag_block,
        usdt_erc20=USDT_ERC20,
        btc=BTC_ADDRESS,
        eth=ETH_ADDRESS,
    )

    llm_messages: list[dict] = list(history)
    llm_messages.append({"role": "user", "content": msg.text})
    reply_text = await llm_chat(system_prompt, llm_messages, temperature=0.7, max_tokens=600)

    if not reply_text:
        reply_text = _deterministic_fallback(stage)

    g_out = evaluate_outbound_text(reply_text, allow_wallets=True)
    if getattr(g_out, "action", "allow") == "safe_rewrite":
        reply_text = getattr(g_out, "rewritten_text", reply_text) or reply_text

    await save_turn(
        msg.channel, msg.conversation_id, msg.user_id, msg.username,
        msg.text, reply_text,
        bant.get("total", 0), bant.get("tier", "cold"),
        stage, PROMPT_VERSION,
    )

    action: str | None = None
    payload: dict[str, Any] = {}
    if bant.get("total", 0) >= HOT_LEAD_THRESHOLD:
        action = "create_deal_room"
        payload = {
            "user_id": msg.user_id,
            "username": msg.username,
            "channel": msg.channel,
            "bant": bant,
        }

    return NormalizedResponse(
        text=reply_text,
        channel=msg.channel,
        conversation_id=msg.conversation_id,
        bant_score=bant.get("total", 0),
        bant_tier=bant.get("tier", "cold"),
        stage=stage,
        action=action,
        action_payload=payload,
        guardrail_action=getattr(g_out, "action", "allow"),
        prompt_version=PROMPT_VERSION,
    )


def _deterministic_fallback(stage: str) -> str:
    return {
        "opener": "yo - got you. what are you trying to run right now (google, meta, tiktok, etc)?",
        "qualify": "got it. what's your monthly ad spend roughly?",
        "present": "we can definitely set you up for that. lemme know if you want a quick rundown of options.",
        "handle_objections": "fair point - what's the main thing holding you back?",
        "close": "cool - which platform and tier you leaning towards?",
        "payment": "drop the tx hash once you've sent it and we'll verify on-chain. takes a few mins.",
    }.get(stage, "got your message - one sec, lemme reply properly.")
