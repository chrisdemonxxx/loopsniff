"""Main retrieval interface for the AdFlux RAG system."""

import sys
from pathlib import Path

import chromadb

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config


class Retriever:
    """Query ChromaDB collections for lead profiles and knowledge base."""

    def __init__(self, chroma_client: chromadb.ClientAPI | None = None):
        if chroma_client is None:
            chroma_client = chromadb.PersistentClient(path=config.CHROMA_DB_PATH)
        self.client = chroma_client
        self._leads = chroma_client.get_or_create_collection(config.COLLECTION_LEADS)
        self._kb = chroma_client.get_or_create_collection(config.COLLECTION_KB)

    # ── Lead Profiles ─────────────────────────────────────────────────────

    def get_lead_context(self, username: str, n_results: int = 5) -> list[dict]:
        """Retrieve lead profile chunks by TG username (metadata filter)."""
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
            "lead_profiles": self._leads.count(),
            "knowledge_base": self._kb.count(),
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
