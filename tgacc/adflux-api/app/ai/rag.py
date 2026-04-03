"""RAG Integration — query the knowledge base with LLM-powered answer synthesis."""

import json
import logging
import re
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.dependencies import get_current_user, require_admin
from app.ai.llm_client import call_llm

router = APIRouter()
log = logging.getLogger(__name__)

RAG_DIR = Path("/home/cjs/tgacc/adflux-rag")

# ---------------------------------------------------------------------------
# Lazy-loaded retriever singleton
# ---------------------------------------------------------------------------

_retriever = None


def _get_retriever():
    global _retriever
    if _retriever is None:
        # Add the RAG project root to sys.path so imports resolve
        rag_str = str(RAG_DIR)
        if rag_str not in sys.path:
            sys.path.insert(0, rag_str)
        from retrieval.retriever import Retriever  # type: ignore[import-untyped]
        _retriever = Retriever()
    return _retriever


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class RAGQueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000, description="Question for the knowledge base")
    n_results: int = Field(5, ge=1, le=20, description="Number of results to return")
    source: str | None = Field(None, description="Optional source filter: bhw, aw_profile, aw_chat, hackforums, exploit")


class RAGSource(BaseModel):
    text: str
    metadata: dict | None = None
    distance: float | None = None


class RAGQueryResponse(BaseModel):
    answer: str
    sources: list[RAGSource]
    confidence: float = Field(..., ge=0.0, le=1.0)
    stats: dict | None = None


class RAGIngestRequest(BaseModel):
    target: str = Field(
        "knowledge-base",
        description="Ingestion target: all, bhw, aw-profiles, aw-chats, hackforums, exploit, knowledge-base",
    )


class RAGIngestResponse(BaseModel):
    status: str
    target: str
    message: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_answer(results: list[dict], query: str) -> str:
    """Fallback: return the top chunk as the answer (no LLM)."""
    if not results:
        return "No relevant information found in the knowledge base for your query."
    top = results[0]
    text = top.get("text", "")
    if len(text) > 600:
        text = text[:600] + "…"
    return text


_RAG_SYSTEM_PROMPT = (
    "You are a knowledgeable ad optimization assistant. Answer the user's question based "
    "ONLY on the provided knowledge base excerpts. Cite which source(s) you used by number. "
    "If the excerpts don't contain enough information, say so clearly."
)


async def _synthesize_answer(results: list[dict], query: str) -> str:
    """Use LLM to synthesize a coherent answer from retrieved chunks."""
    if not results:
        return "No relevant information found in the knowledge base for your query."

    # Format chunks with source numbers for citation
    chunk_parts: list[str] = []
    for i, r in enumerate(results, 1):
        text = r.get("text", "").strip()
        meta = r.get("metadata", {})
        source_label = meta.get("source", "unknown") if meta else "unknown"
        chunk_parts.append(f"[Source {i} — {source_label}]\n{text}")

    chunks_text = "\n\n".join(chunk_parts)

    prompt = (
        f"Knowledge base excerpts:\n\n{chunks_text}\n\n"
        f"Question: {query}\n\n"
        "Provide a comprehensive answer citing source numbers."
    )

    llm_response = await call_llm(prompt, system_prompt=_RAG_SYSTEM_PROMPT, temperature=0.3, max_tokens=1024)
    if llm_response is None:
        return _build_answer(results, query)

    return llm_response.strip()


def _compute_confidence(results: list[dict]) -> float:
    if not results:
        return 0.0
    distances = [r.get("distance", 1.0) for r in results]
    avg = sum(distances) / len(distances)
    # ChromaDB cosine distance: 0 = perfect, 2 = opposite
    confidence = max(0.0, min(1.0, 1.0 - avg / 2.0))
    return round(confidence, 3)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/rag/query", response_model=RAGQueryResponse)
async def rag_query(
    req: RAGQueryRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Query the RAG knowledge base for ad optimization advice."""
    try:
        retriever = _get_retriever()
    except Exception as exc:
        log.error(f"Failed to initialise RAG retriever: {exc}")
        raise HTTPException(status_code=503, detail="RAG service unavailable.")

    try:
        if req.source:
            results = retriever.search_leads(req.query, n_results=req.n_results, source=req.source)
        else:
            results = retriever.get_knowledge(req.query, n_results=req.n_results)
    except Exception as exc:
        log.error(f"RAG query failed: {exc}")
        raise HTTPException(status_code=500, detail="RAG query failed.")

    sources = [
        RAGSource(
            text=r.get("text", ""),
            metadata=r.get("metadata"),
            distance=r.get("distance"),
        )
        for r in results
    ]

    return RAGQueryResponse(
        answer=await _synthesize_answer(results, req.query),
        sources=sources,
        confidence=_compute_confidence(results),
        stats=retriever.stats(),
    )


@router.post("/rag/ingest", response_model=RAGIngestResponse)
async def rag_ingest(
    req: RAGIngestRequest,
    user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Admin: trigger document ingestion into the RAG knowledge base."""
    ingest_script = RAG_DIR / "run_ingest.py"
    if not ingest_script.exists():
        raise HTTPException(status_code=503, detail="Ingestion script not found.")

    target_flag = f"--{req.target}"
    try:
        result = subprocess.run(
            [sys.executable, str(ingest_script), target_flag],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=str(RAG_DIR),
        )
        if result.returncode != 0:
            log.error(f"Ingest failed: {result.stderr}")
            return RAGIngestResponse(status="error", target=req.target, message=result.stderr[:500])
        return RAGIngestResponse(status="success", target=req.target, message=result.stdout[:500] or "Ingestion completed.")
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Ingestion timed out (>5 min).")
    except Exception as exc:
        log.error(f"Ingest error: {exc}")
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {exc}")
