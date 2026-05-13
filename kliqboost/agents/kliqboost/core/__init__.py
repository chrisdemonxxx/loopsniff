"""Kliqboost shared brain — channel-agnostic AI core.

Provides one entry point ``respond(NormalizedMessage) -> NormalizedResponse``
that handles RAG retrieval, BANT scoring, prompt rendering, LLM call
(Baseten Kimi K2.6), and outbound guardrails.

Used by the WhatsApp / Messenger / Instagram FastAPI webhook adapters.
The Telegram userbot and bot still run their own legacy paths today and
will be migrated to call this same brain in a follow-up phase.
"""

from .types import NormalizedMessage, NormalizedResponse, ChannelName
from .agent import respond

__all__ = ["NormalizedMessage", "NormalizedResponse", "ChannelName", "respond"]
