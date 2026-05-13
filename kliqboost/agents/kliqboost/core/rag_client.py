"""Thin wrapper around rag.retrieval.Retriever with import-fail fallback."""

from __future__ import annotations

import importlib
import importlib.util  # noqa: F401  -- Python 3.12 requires explicit import
import logging
from typing import Any

log = logging.getLogger(__name__)

_RETRIEVER: Any = None


class _NullRetriever:
    def get_knowledge(self, query, n_results=5):
        return []

    def get_lead_context(self, username, n_results=5):
        return []

    def search_leads(self, query, n_results=10, source=None):
        return []

    def get_full_context(self, username, query, n_lead=3, n_kb=3):
        return {"lead_context": [], "knowledge_context": []}

    def stats(self):
        return {"lead_profiles": 0, "knowledge_base": 0}


def get_retriever():
    global _RETRIEVER
    if _RETRIEVER is not None:
        return _RETRIEVER
    try:
        mod = importlib.import_module("rag.retrieval.retriever")
        _RETRIEVER = mod.Retriever()
        log.info("RAG retriever loaded; stats=%s", _RETRIEVER.stats())
    except Exception as exc:
        log.warning("RAG retriever unavailable, falling back to null: %s", exc)
        _RETRIEVER = _NullRetriever()
    return _RETRIEVER


def format_context(ctx: dict) -> str:
    parts: list[str] = []
    kb = ctx.get("knowledge_context") or []
    if kb:
        parts.append("=== Relevant Knowledge ===")
        for hit in kb[:3]:
            text = (hit.get("text") or "").strip()
            if text:
                parts.append(text[:500])
    leads = ctx.get("lead_context") or []
    if leads:
        parts.append("\n=== Lead Profile ===")
        for hit in leads[:2]:
            text = (hit.get("text") or "").strip()
            if text:
                parts.append(text[:500])
    return "\n".join(parts)
