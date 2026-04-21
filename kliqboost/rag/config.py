"""Central configuration for the Kliqboost RAG system."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

# ── Paths ──────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", str(BASE_DIR / "chroma_db"))

BHW_DIR = Path(os.getenv("BHW_DIR", "/home/cjs/blackhatworld"))
AW_DIR = Path(os.getenv("AW_DIR", "/home/cjs/aw-attendee-data"))
HACKFORUMS_DB = Path(os.getenv("HACKFORUMS_DB", "/home/cjs/hackforums/hackforums.db"))
EXPLOIT_CSV = Path(os.getenv(
    "EXPLOIT_CSV",
    "/home/cjs/exploit_forum_scrapper/user_db_output/deep_database_20260226_022321.csv",
))

# AW sub-paths
AW_MASTER_CSV = AW_DIR / "FINAL_EXPORT_V5" / "all_conferences_master_final.csv"
AW_TG_CSV = AW_DIR / "FINAL_EXPORT_V5" / "verified_telegram_handles.csv"
AW_CHAT_FILES = [
    AW_DIR / "awd26_chat_messages.json",
    AW_DIR / "awa25_chat_messages.json",
    AW_DIR / "awe25_chat_messages.json",
]
AW_CONNECTIONS_CSV = AW_DIR / "awd26_connection_edges.csv"

# BHW sub-paths
BHW_POSTS_CSV = BHW_DIR / "posts.csv"
BHW_TG_HANDLES_CSV = BHW_DIR / "verified_active_tg_handles.csv"
BHW_CLIENTS_CSV = BHW_DIR / "all_verified_clients.csv"

# ── ChromaDB collections ──────────────────────────────────────────────────
COLLECTION_LEADS = "lead_profiles"
COLLECTION_KB = "knowledge_base"

# ── Embedding model ───────────────────────────────────────────────────────
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

# ── Chunking ──────────────────────────────────────────────────────────────
CHUNK_SIZE = 500
CHUNK_OVERLAP = 100
BATCH_SIZE = 256
