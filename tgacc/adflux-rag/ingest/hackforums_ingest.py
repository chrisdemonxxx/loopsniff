"""Ingest HackForums data into lead_profiles.

Schema:
  forums: fid, name, thread_count
  threads: tid, fid, title, author_uid, author_username
  users: uid, username, rank, posts_count, reputation, join_date, bytes
  contacts: id, uid, username, contact_type, contact_value, source
  posts: id, tid, author_uid, author_name, date_posted, text_content, is_op

We care about users who have telegram contacts (contact_type IN ('telegram_at','telegram_link')).
"""

import hashlib
import sqlite3
import sys
from pathlib import Path

import chromadb
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


def _doc_id(handle: str, idx: int) -> str:
    global _counter
    _counter += 1
    h = hashlib.md5(f"hf_{handle}_{idx}_{_counter}".encode()).hexdigest()[:12]
    doc_id = f"hf_{h}"
    while doc_id in _seen_ids:
        _counter += 1
        h = hashlib.md5(f"hf_{handle}_{idx}_{_counter}".encode()).hexdigest()[:12]
        doc_id = f"hf_{h}"
    _seen_ids.add(doc_id)
    return doc_id


def _extract_tg_handle(contact_value: str) -> str:
    """Normalize a telegram contact value to a clean handle."""
    val = contact_value.strip().rstrip("/")
    # Remove common prefixes
    for prefix in ("https://t.me/", "http://t.me/", "t.me/", "@"):
        if val.lower().startswith(prefix.lower()):
            val = val[len(prefix):]
    return val.strip()


def run(chroma_client: chromadb.ClientAPI | None = None):
    """Ingest HackForums user profiles with TG handles."""
    print("\n══════ HackForums Ingestion ══════")

    if chroma_client is None:
        chroma_client = chromadb.PersistentClient(path=config.CHROMA_DB_PATH)
    collection = chroma_client.get_or_create_collection(config.COLLECTION_LEADS)

    db_path = config.HACKFORUMS_DB
    if not db_path.exists():
        print(f"  ✗ Database not found: {db_path}")
        return

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # ── Get users with telegram contacts ──────────────────────────────────
    tg_users = conn.execute("""
        SELECT c.uid, c.contact_value, c.contact_type,
               u.username, u.rank, u.posts_count, u.reputation, u.join_date
        FROM contacts c
        LEFT JOIN users u ON c.uid = u.uid
        WHERE c.contact_type IN ('telegram_at', 'telegram_link')
    """).fetchall()

    print(f"  Found {len(tg_users)} telegram contacts")

    # Build uid → tg_handle mapping (prefer telegram_at over telegram_link)
    uid_tg: dict[int, str] = {}
    uid_info: dict[int, dict] = {}
    for row in tg_users:
        uid = row["uid"]
        handle = _extract_tg_handle(row["contact_value"])
        if not handle:
            continue

        if uid not in uid_tg or row["contact_type"] == "telegram_at":
            uid_tg[uid] = handle

        if uid not in uid_info:
            uid_info[uid] = {
                "username": row["username"] or "",
                "rank": row["rank"] or "",
                "posts_count": row["posts_count"] or "",
                "reputation": row["reputation"] or "",
                "join_date": row["join_date"] or "",
            }

    print(f"  {len(uid_tg)} unique users with TG handles")

    # ── Fetch posts for these users ───────────────────────────────────────
    ids_all, docs_all, metas_all = [], [], []

    for uid, tg_handle in tqdm(uid_tg.items(), desc="  HF users"):
        info = uid_info.get(uid, {})

        posts = conn.execute("""
            SELECT p.text_content, p.date_posted, t.title, f.name AS forum_name
            FROM posts p
            LEFT JOIN threads t ON p.tid = t.tid
            LEFT JOIN forums f ON t.fid = f.fid
            WHERE p.author_uid = ?
            ORDER BY p.date_posted DESC
            LIMIT 50
        """, (uid,)).fetchall()

        parts = [f"HackForums user: {info.get('username', '')} | TG: @{tg_handle}"]
        if info.get("rank"):
            parts.append(f"Rank: {info['rank']}")
        if info.get("reputation"):
            parts.append(f"Reputation: {info['reputation']}")

        categories = set()
        latest_date = ""
        for post in posts:
            text = (post["text_content"] or "").strip()
            title = post["title"] or ""
            forum = post["forum_name"] or ""
            if text:
                parts.append(f"[{forum} > {title}] {text[:300]}")
            if forum:
                categories.add(forum)
            d = post["date_posted"] or ""
            if d > latest_date:
                latest_date = d

        if len(parts) <= 3 and not posts:
            # No posts, still create a minimal profile
            parts.append("(no posts found)")

        full_text = "\n".join(parts)
        chunks = _chunk_text(full_text)

        for i, chunk in enumerate(chunks):
            ids_all.append(_doc_id(tg_handle, i))
            docs_all.append(chunk)
            metas_all.append({
                "username": tg_handle,
                "source": "hackforums",
                "category": ", ".join(sorted(categories)[:5]),
                "date": latest_date[:10] if latest_date else "",
            })

    conn.close()

    # ── Batch upsert ──────────────────────────────────────────────────────
    print(f"  {len(docs_all)} chunks to upsert")
    for start in tqdm(range(0, len(docs_all), config.BATCH_SIZE), desc="  Upserting"):
        end = start + config.BATCH_SIZE
        collection.upsert(
            ids=ids_all[start:end],
            documents=docs_all[start:end],
            metadatas=metas_all[start:end],
        )

    print(f"  ✓ HackForums ingestion complete — collection size: {collection.count()}")


if __name__ == "__main__":
    run()
