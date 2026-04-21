#!/usr/bin/env python3
"""Ingest Kliqboost ad-strategy markdown files into ChromaDB knowledge base."""

import hashlib
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import chromadb
import config

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("ingest_kb")

DOCS_DIR = Path(__file__).resolve().parent.parent / "ads-strategy"


def chunk_text(text: str, size: int = config.CHUNK_SIZE, overlap: int = config.CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end])
        start += size - overlap
    return [c.strip() for c in chunks if c.strip()]


def make_id(path: str, idx: int) -> str:
    """Deterministic chunk ID from file path + index."""
    return hashlib.md5(f"{path}:{idx}".encode()).hexdigest()


def ingest():
    if not DOCS_DIR.exists():
        log.error("Docs dir not found: %s", DOCS_DIR)
        sys.exit(1)

    md_files = sorted(DOCS_DIR.rglob("*.md"))
    log.info("Found %d markdown files in %s", len(md_files), DOCS_DIR)

    db_path = config.CHROMA_DB_PATH
    Path(db_path).mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=db_path)

    # Reset collection for clean ingest
    try:
        client.delete_collection(config.COLLECTION_KB)
    except Exception:
        pass
    kb = client.get_or_create_collection(config.COLLECTION_KB)

    all_ids, all_docs, all_metas = [], [], []

    for md_file in md_files:
        rel = md_file.relative_to(DOCS_DIR)
        text = md_file.read_text(encoding="utf-8", errors="replace")
        if not text.strip():
            continue

        chunks = chunk_text(text)
        for i, chunk in enumerate(chunks):
            cid = make_id(str(rel), i)
            all_ids.append(cid)
            all_docs.append(chunk)
            all_metas.append({
                "source": str(rel),
                "chunk_index": i,
                "total_chunks": len(chunks),
            })

    # Batch upsert
    batch = config.BATCH_SIZE
    for start in range(0, len(all_ids), batch):
        end = start + batch
        kb.upsert(
            ids=all_ids[start:end],
            documents=all_docs[start:end],
            metadatas=all_metas[start:end],
        )

    log.info("✅ Ingested %d chunks from %d files into '%s'", len(all_ids), len(md_files), config.COLLECTION_KB)
    log.info("   ChromaDB path: %s", db_path)

    # Also create the leads collection (empty but ready)
    client.get_or_create_collection(config.COLLECTION_LEADS)
    log.info("   Leads collection ready (empty)")

    # Verify
    stats = {"knowledge_base": kb.count(), "lead_profiles": 0}
    log.info("   Stats: %s", stats)


if __name__ == "__main__":
    ingest()
