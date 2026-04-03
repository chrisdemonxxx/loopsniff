"""Ingest BlackHatWorld posts into lead_profiles collection.

Data:
  posts.csv columns:
    thread_url, thread_title, category, username, user_id, user_profile,
    user_rank, post_date, post_excerpt, signature,
    telegram, jabber, skype, icq, whatsapp, email
  verified_active_tg_handles.csv columns:
    handle, name, username, all_users, mention_count, verified, is_verified_seller
"""

import ast
import hashlib
import sys
from pathlib import Path

import chromadb
import pandas as pd
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config


def _safe_list(val):
    """Parse a stringified list like "['handle1']" or return empty list."""
    if pd.isna(val):
        return []
    val = str(val).strip()
    if val in ("[]", "", "nan"):
        return []
    try:
        parsed = ast.literal_eval(val)
        return list(parsed) if isinstance(parsed, (list, tuple, set)) else [str(parsed)]
    except Exception:
        return [val]


def _chunk_text(text: str, size: int = config.CHUNK_SIZE, overlap: int = config.CHUNK_OVERLAP):
    """Split text into overlapping chunks."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end])
        start += size - overlap
    return chunks


_seen_ids: set[str] = set()
_counter = 0


def _doc_id(username: str, idx: int) -> str:
    global _counter
    _counter += 1
    h = hashlib.md5(f"bhw_{username}_{idx}_{_counter}".encode()).hexdigest()[:12]
    doc_id = f"bhw_{h}"
    while doc_id in _seen_ids:
        _counter += 1
        h = hashlib.md5(f"bhw_{username}_{idx}_{_counter}".encode()).hexdigest()[:12]
        doc_id = f"bhw_{h}"
    _seen_ids.add(doc_id)
    return doc_id


def run(chroma_client: chromadb.ClientAPI | None = None):
    """Ingest BHW posts grouped by username with TG handles."""
    print("\n══════ BHW Posts Ingestion ══════")

    if chroma_client is None:
        chroma_client = chromadb.PersistentClient(path=config.CHROMA_DB_PATH)
    collection = chroma_client.get_or_create_collection(config.COLLECTION_LEADS)

    # ── Load TG handle lookup ─────────────────────────────────────────────
    tg_handles: dict[str, str] = {}  # bhw_username -> tg_handle
    if config.BHW_TG_HANDLES_CSV.exists():
        tg_df = pd.read_csv(config.BHW_TG_HANDLES_CSV, dtype=str)
        # 'handle' is the TG handle, 'username' is the BHW username
        for _, row in tg_df.iterrows():
            handle = str(row.get("handle", "")).strip()
            bhw_user = str(row.get("username", "")).strip()
            if handle and bhw_user and handle != "nan":
                tg_handles[bhw_user.lower()] = handle
        print(f"  Loaded {len(tg_handles)} TG handle mappings")
    else:
        print("  ⚠ verified_active_tg_handles.csv not found — skipping TG mapping")

    # ── Read posts ────────────────────────────────────────────────────────
    if not config.BHW_POSTS_CSV.exists():
        print("  ✗ posts.csv not found — aborting")
        return

    print(f"  Reading {config.BHW_POSTS_CSV} …")
    df = pd.read_csv(
        config.BHW_POSTS_CSV,
        dtype=str,
        on_bad_lines="skip",
        encoding_errors="replace",
        low_memory=False,
    )
    print(f"  {len(df):,} rows loaded")

    # Also gather TG handles embedded in the posts themselves
    for _, row in df.iterrows():
        uname = str(row.get("username", "")).strip().lower()
        if uname and uname != "nan" and uname not in tg_handles:
            tg_vals = _safe_list(row.get("telegram", ""))
            if tg_vals:
                tg_handles[uname] = tg_vals[0]

    # ── Group by username ─────────────────────────────────────────────────
    grouped = df.groupby("username", dropna=True)
    ids, docs, metas = [], [], []
    skipped = 0

    for username, group in tqdm(grouped, desc="  BHW users"):
        uname_lower = username.strip().lower()
        tg = tg_handles.get(uname_lower)
        if not tg:
            skipped += 1
            continue

        # Build document from user's posts
        parts = []
        categories = set()
        latest_date = ""
        for _, row in group.iterrows():
            excerpt = str(row.get("post_excerpt", "")).strip()
            title = str(row.get("thread_title", "")).strip()
            cat = str(row.get("category", "")).strip()
            if excerpt and excerpt != "nan":
                parts.append(f"[{title}] {excerpt}")
            if cat and cat != "nan":
                categories.add(cat)
            d = str(row.get("post_date", ""))
            if d and d != "nan" and d > latest_date:
                latest_date = d

        if not parts:
            skipped += 1
            continue

        full_text = f"BHW user: {username} | TG: @{tg}\n" + "\n---\n".join(parts)
        chunks = _chunk_text(full_text)

        for i, chunk in enumerate(chunks):
            ids.append(_doc_id(tg, i))
            docs.append(chunk)
            metas.append({
                "username": tg,
                "source": "bhw",
                "category": ", ".join(sorted(categories)[:5]),
                "date": latest_date[:10] if latest_date else "",
                "bhw_user": username.strip(),
            })

    # ── Batch upsert ──────────────────────────────────────────────────────
    print(f"  {len(docs):,} chunks from {len(docs)} documents (skipped {skipped} users w/o TG)")
    for start in tqdm(range(0, len(docs), config.BATCH_SIZE), desc="  Upserting"):
        end = start + config.BATCH_SIZE
        collection.upsert(
            ids=ids[start:end],
            documents=docs[start:end],
            metadatas=metas[start:end],
        )

    print(f"  ✓ BHW ingestion complete — collection size: {collection.count()}")


if __name__ == "__main__":
    run()
