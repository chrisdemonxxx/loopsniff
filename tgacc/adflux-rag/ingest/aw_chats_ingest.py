"""Ingest Affiliate World conference chat messages into lead_profiles.

Chat JSON structure (per file):
  {
    "106110_120621": [
      {
        "id": "...",
        "chat_id": "106110_120621",
        "text": "...",
        "type": "text",
        "sender_id": "120621",
        "timestamp": "2026-03-03T14:05:32.676Z",
        "read_by": [...]
      },
      ...
    ],
    ...
  }

We map sender_id → TG handle using the AW master CSV (id column → telegram column).
"""

import hashlib
import json
import sys
from pathlib import Path

import chromadb
import pandas as pd
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config


def _chunk_text(text: str, size: int = config.CHUNK_SIZE, overlap: int = config.CHUNK_OVERLAP):
    chunks = []
    start = 0
    while start < len(text):
        chunks.append(text[start:start + size])
        start += size - overlap
    return chunks


_seen_ids: set[str] = set()
_counter = 0


def _doc_id(handle: str, file_tag: str, idx: int) -> str:
    global _counter
    _counter += 1
    h = hashlib.md5(f"awc_{handle}_{file_tag}_{idx}_{_counter}".encode()).hexdigest()[:12]
    doc_id = f"awc_{h}"
    while doc_id in _seen_ids:
        _counter += 1
        h = hashlib.md5(f"awc_{handle}_{file_tag}_{idx}_{_counter}".encode()).hexdigest()[:12]
        doc_id = f"awc_{h}"
    _seen_ids.add(doc_id)
    return doc_id


def _build_sender_map() -> dict[str, str]:
    """Map AW attendee id → telegram handle."""
    mapping: dict[str, str] = {}
    if not config.AW_MASTER_CSV.exists():
        return mapping
    df = pd.read_csv(config.AW_MASTER_CSV, dtype=str, encoding_errors="replace")
    for _, row in df.iterrows():
        aid = str(row.get("id", "")).strip()
        tg = str(row.get("telegram", "")).strip().lstrip("@")
        if aid and tg and tg != "nan":
            mapping[aid] = tg
    return mapping


def _process_chat_file(
    filepath: Path,
    sender_map: dict[str, str],
    collection: chromadb.Collection,
    file_tag: str,
):
    """Process a single chat JSON file."""
    if not filepath.exists():
        print(f"    ⚠ {filepath.name} not found — skipping")
        return 0

    file_size_mb = filepath.stat().st_size / (1024 * 1024)
    print(f"    Processing {filepath.name} ({file_size_mb:.1f} MB) …")

    # Load JSON (these files are 20-80 MB, manageable in memory)
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        print(f"    ⚠ Unexpected format in {filepath.name}")
        return 0

    # Group messages by sender_id
    sender_messages: dict[str, list[str]] = {}
    total_msgs = 0
    for chat_id, messages in data.items():
        if not isinstance(messages, list):
            continue
        for msg in messages:
            if not isinstance(msg, dict):
                continue
            text = msg.get("text", "")
            sender_id = str(msg.get("sender_id", ""))
            if text and sender_id:
                sender_messages.setdefault(sender_id, []).append(str(text))
                total_msgs += 1

    print(f"      {total_msgs:,} messages from {len(sender_messages)} senders")

    ids, docs, metas = [], [], []
    mapped_count = 0

    for sender_id, messages in sender_messages.items():
        tg_handle = sender_map.get(sender_id)
        if not tg_handle:
            continue
        mapped_count += 1

        full_text = f"AW Chat messages from @{tg_handle}:\n" + "\n".join(messages)
        chunks = _chunk_text(full_text)

        for i, chunk in enumerate(chunks):
            ids.append(_doc_id(tg_handle, file_tag, i))
            docs.append(chunk)
            metas.append({
                "username": tg_handle,
                "source": "aw_chat",
                "category": file_tag,
                "date": "",
            })

    # Batch upsert
    for start in range(0, len(docs), config.BATCH_SIZE):
        end = start + config.BATCH_SIZE
        collection.upsert(
            ids=ids[start:end],
            documents=docs[start:end],
            metadatas=metas[start:end],
        )

    print(f"      Mapped {mapped_count} senders → {len(docs)} chunks")
    return len(docs)


def run(chroma_client: chromadb.ClientAPI | None = None):
    """Ingest all AW conference chat messages."""
    print("\n══════ AW Chats Ingestion ══════")

    if chroma_client is None:
        chroma_client = chromadb.PersistentClient(path=config.CHROMA_DB_PATH)
    collection = chroma_client.get_or_create_collection(config.COLLECTION_LEADS)

    sender_map = _build_sender_map()
    print(f"  Sender ID → TG mapping: {len(sender_map)} entries")

    total_chunks = 0
    chat_files_and_tags = [
        (config.AW_DIR / "awd26_chat_messages.json", "aw_dubai26"),
        (config.AW_DIR / "awa25_chat_messages.json", "aw_asia25"),
        (config.AW_DIR / "awe25_chat_messages.json", "aw_europe25"),
    ]

    for filepath, tag in chat_files_and_tags:
        total_chunks += _process_chat_file(filepath, sender_map, collection, tag)

    print(f"  ✓ AW chats ingestion complete — {total_chunks} total chunks — collection size: {collection.count()}")


if __name__ == "__main__":
    run()
