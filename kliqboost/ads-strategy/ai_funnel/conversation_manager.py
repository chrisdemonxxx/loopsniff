"""Conversation manager — LLM context window, memory, and RAG integration.

Handles:
  - In-memory conversation history (per-user)
  - RAG context injection from the Kliqboost knowledge base
  - Message splitting for multi-sentence responses
  - Language detection for prompt selection
  - Stage progression based on BANT scores
"""

from __future__ import annotations

import logging
import os
import re
import sys
from collections import defaultdict
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

# ── Wire up RAG ──────────────────────────────────────────────────────────
RAG_PATH = os.getenv("RAG_PATH", "/home/cjs/kliqboost/rag")
OUTREACH_PATH = os.getenv("OUTREACH_PATH", "/home/cjs/kliqboost")
sys.path.insert(0, RAG_PATH)
sys.path.insert(0, OUTREACH_PATH)

try:
    from retrieval.retriever import Retriever
    from outreach.scoring.bant_scorer import BANTScorer
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False
    log.warning("RAG system not available — running without context retrieval")

# ── Constants ────────────────────────────────────────────────────────────

MAX_HISTORY = 20

SALES_STAGES = [
    "opener", "qualify", "present", "handle_objections", "close", "payment",
]

HOT_LEAD_THRESHOLD = 75
PAYMENT_READY_THRESHOLD = 70


# ═══════════════════════════════════════════════════════════════════════════
# Language Detection
# ═══════════════════════════════════════════════════════════════════════════

_CYRILLIC = re.compile(r"[а-яА-ЯёЁ]")


def detect_language(text: str) -> str:
    """Simple language detection — returns 'ru' or 'en'."""
    cyrillic_count = len(_CYRILLIC.findall(text))
    latin_count = len(re.findall(r"[a-zA-Z]", text))
    return "ru" if cyrillic_count > latin_count else "en"


# ═══════════════════════════════════════════════════════════════════════════
# Stage Inference
# ═══════════════════════════════════════════════════════════════════════════

def infer_stage(bant: Dict[str, Any], message_count: int, current_stage: str) -> str:
    """Advance the sales stage based on BANT score and conversation depth."""
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
# Message Splitting
# ═══════════════════════════════════════════════════════════════════════════

def split_message(text: str, max_length: int = 200) -> List[str]:
    """Split a long reply into multiple shorter messages.

    Makes it look like natural texting — people send multiple short
    messages, not one long block.
    """
    if len(text) <= max_length:
        return [text]

    # Split on sentence boundaries
    sentences = re.split(r'(?<=[.!?])\s+', text)

    chunks: List[str] = []
    current = ""

    for sentence in sentences:
        if current and len(current) + len(sentence) + 1 > max_length:
            chunks.append(current.strip())
            current = sentence
        else:
            current = f"{current} {sentence}".strip() if current else sentence

    if current:
        chunks.append(current.strip())

    return chunks if chunks else [text]


# ═══════════════════════════════════════════════════════════════════════════
# Conversation Manager
# ═══════════════════════════════════════════════════════════════════════════

class ConversationManager:
    """Manages per-user conversation state, RAG context, and BANT scoring."""

    def __init__(self):
        self._history: Dict[int, List[Dict[str, str]]] = defaultdict(list)
        self._stages: Dict[int, str] = defaultdict(lambda: "opener")
        self._languages: Dict[int, str] = {}

        if RAG_AVAILABLE:
            self.retriever = Retriever()
            self.scorer = BANTScorer()
            log.info(
                "RAG connected — leads: %d, KB: %d",
                self.retriever.stats().get("lead_profiles", 0),
                self.retriever.stats().get("knowledge_base", 0),
            )
        else:
            self.retriever = None
            self.scorer = None

    def load_history(self, user_id: int, messages: List[Dict[str, str]]) -> None:
        """Load conversation history from database."""
        self._history[user_id] = messages

    def add_message(self, user_id: int, role: str, content: str) -> None:
        """Append a message to in-memory history."""
        self._history[user_id].append({"role": role, "content": content})
        # Keep window bounded
        if len(self._history[user_id]) > MAX_HISTORY * 2:
            self._history[user_id] = self._history[user_id][-MAX_HISTORY:]

    def get_stage(self, user_id: int) -> str:
        return self._stages[user_id]

    def set_stage(self, user_id: int, stage: str) -> None:
        self._stages[user_id] = stage

    def detect_and_store_language(self, user_id: int, text: str) -> str:
        """Detect language from user text and cache it."""
        lang = detect_language(text)
        if user_id not in self._languages:
            self._languages[user_id] = lang
        return self._languages.get(user_id, "en")

    def get_language(self, user_id: int) -> str:
        return self._languages.get(user_id, "en")

    # ── BANT Scoring ─────────────────────────────────────────────────────

    def score_conversation(self, user_id: int) -> Dict[str, Any]:
        """Run BANT scoring across all user messages."""
        if not self.scorer:
            return {"total": 0, "tier": "cold", "extracted": {}}

        user_messages = [
            m["content"] for m in self._history.get(user_id, [])
            if m["role"] == "user"
        ]
        if not user_messages:
            return {"total": 0, "tier": "cold", "extracted": {}}

        return self.scorer.score_from_conversation(user_messages)

    def advance_stage(self, user_id: int, bant: Dict[str, Any]) -> str:
        """Score and advance the sales stage."""
        user_messages = [
            m["content"] for m in self._history.get(user_id, [])
            if m["role"] == "user"
        ]
        current = self._stages[user_id]
        new_stage = infer_stage(bant, len(user_messages), current)
        self._stages[user_id] = new_stage
        return new_stage

    # ── RAG Context ──────────────────────────────────────────────────────

    def build_rag_context(
        self, username: str, query: str, n_kb: int = 3, n_lead: int = 2
    ) -> str:
        """Retrieve relevant context from the RAG system."""
        if not self.retriever:
            return ""

        parts: List[str] = []

        kb_results = self.retriever.get_knowledge(query, n_results=n_kb)
        if kb_results:
            parts.append("=== Relevant Knowledge Base ===")
            for r in kb_results:
                parts.append(r["text"])

        lead_ctx = self.retriever.get_lead_context(username, n_results=n_lead)
        if lead_ctx:
            parts.append("=== Lead Profile ===")
            for r in lead_ctx:
                parts.append(r["text"])

        return "\n\n".join(parts) if parts else ""

    # ── LLM Message Construction ─────────────────────────────────────────

    def build_llm_messages(
        self, user_id: int, username: str, query: str
    ) -> List[Dict[str, str]]:
        """Build the full message array for the LLM call.

        Format:
          1. [RAG context as user message + ack]
          2. [Conversation history]
        """
        messages: List[Dict[str, str]] = []

        # RAG context injection
        rag_context = self.build_rag_context(username, query)
        if rag_context:
            messages.append({
                "role": "user",
                "content": (
                    "[CONTEXT — do NOT repeat verbatim, use to inform your answer]\n\n"
                    + rag_context
                ),
            })
            messages.append({
                "role": "assistant",
                "content": "Understood, I'll use this context to help the lead.",
            })

        # Conversation history
        history = self._history.get(user_id, [])
        messages.extend(history[-MAX_HISTORY:])

        return messages

    @property
    def stats(self) -> Dict[str, Any]:
        return {
            "active_conversations": len(self._history),
            "rag_available": RAG_AVAILABLE,
            "rag_stats": self.retriever.stats() if self.retriever else None,
        }
