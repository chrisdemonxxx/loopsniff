"""Main retrieval interface for the Kliqboost RAG system.

Supports two modes:
  - Local: PersistentClient reading from CHROMA_DB_PATH (default)
  - Remote: HttpClient connecting to CHROMA_HOST (e.g. Render private service)

Set CHROMA_HOST env var to enable remote mode (e.g. "kliqboost-vectordb:10000").
"""

import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

log = logging.getLogger("retriever")

_CHROMA_AVAILABLE = False
try:
    import chromadb
    import config
    _CHROMA_AVAILABLE = True
except ImportError:
    log.warning("ChromaDB not available — RAG disabled")

COLLECTION_LEADS = "lead_profiles"
COLLECTION_KB = "knowledge_base"


class Retriever:
    """Query ChromaDB collections for lead profiles and knowledge base.
    Gracefully degrades if ChromaDB is missing or data dir doesn't exist."""

    def __init__(self, chroma_client=None):
        self._leads = None
        self._kb = None
        self.client = None

        if not _CHROMA_AVAILABLE:
            log.info("RAG: ChromaDB not installed — running without RAG")
            return

        try:
            if chroma_client is None:
                chroma_host = os.getenv("CHROMA_HOST", "")
                if chroma_host:
                    # Remote mode: connect to ChromaDB server via HTTP
                    host, _, port = chroma_host.partition(":")
                    port = int(port) if port else 8000
                    chroma_client = chromadb.HttpClient(host=host, port=port)
                    log.info("RAG: Connecting to remote ChromaDB at %s:%d", host, port)
                else:
                    # Local mode: read from disk
                    db_path = config.CHROMA_DB_PATH
                    if not Path(db_path).exists():
                        log.info("RAG: ChromaDB path %s not found — running without RAG", db_path)
                        return
                    chroma_client = chromadb.PersistentClient(path=db_path)
                    log.info("RAG: Local ChromaDB at %s", db_path)
            self.client = chroma_client
            col_leads = getattr(config, "COLLECTION_LEADS", COLLECTION_LEADS)
            col_kb = getattr(config, "COLLECTION_KB", COLLECTION_KB)
            self._leads = chroma_client.get_or_create_collection(col_leads)
            self._kb = chroma_client.get_or_create_collection(col_kb)
            log.info("RAG: Connected — leads=%d, kb=%d", self._leads.count(), self._kb.count())
        except Exception as exc:
            log.warning("RAG: Failed to init ChromaDB: %s — running without RAG", exc)

    # ── Lead Profiles ─────────────────────────────────────────────────────

    def get_lead_context(self, username: str, n_results: int = 5) -> list[dict]:
        """Retrieve lead profile chunks by TG username (metadata filter)."""
        if not self._leads:
            return []
        username = username.lstrip("@").strip()
        if not username:
            return []

        results = self._leads.query(
            query_texts=[f"user profile for {username}"],
            n_results=n_results,
            where={"username": username},
        )
        return self._format_results(results)

    def search_leads(self, query: str, n_results: int = 10, source: str | None = None) -> list[dict]:
        """Semantic search across all lead profiles."""
        if not self._leads:
            return []
        where = {"source": source} if source else None
        results = self._leads.query(
            query_texts=[query],
            n_results=n_results,
            where=where,
        )
        return self._format_results(results)

    # ── Knowledge Base ────────────────────────────────────────────────────

    def get_knowledge(self, query: str, n_results: int = 5) -> list[dict]:
        """Semantic search in the knowledge base."""
        if not self._kb:
            return []
        results = self._kb.query(
            query_texts=[query],
            n_results=n_results,
        )
        return self._format_results(results)

    # ── Combined ──────────────────────────────────────────────────────────

    def get_full_context(
        self, username: str, query: str, n_lead: int = 3, n_kb: int = 3
    ) -> dict:
        """Get combined lead context + knowledge base context."""
        lead_ctx = self.get_lead_context(username, n_results=n_lead)
        kb_ctx = self.get_knowledge(query, n_results=n_kb)
        return {
            "lead_context": lead_ctx,
            "knowledge_context": kb_ctx,
        }

    # ── Stats ─────────────────────────────────────────────────────────────

    def stats(self) -> dict:
        """Return collection statistics."""
        return {
            "lead_profiles": self._leads.count() if self._leads else 0,
            "knowledge_base": self._kb.count() if self._kb else 0,
        }

    # ── Helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _format_results(results: dict) -> list[dict]:
        """Convert ChromaDB query results into a list of dicts."""
        if not results or not results.get("documents"):
            return []
        out = []
        for i, doc in enumerate(results["documents"][0]):
            entry = {"text": doc}
            if results.get("metadatas") and results["metadatas"][0]:
                entry["metadata"] = results["metadatas"][0][i]
            if results.get("distances") and results["distances"][0]:
                entry["distance"] = results["distances"][0][i]
            out.append(entry)
        return out
