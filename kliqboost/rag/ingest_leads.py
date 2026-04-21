#!/usr/bin/env python3
"""Ingest ALL lead intelligence into ChromaDB.

Sources:
  Lead Profiles → lead_profiles collection
    1. BHW verified clients (CSV)
    2. BHW complete TG database (CSV)
    3. BHW verified TG handles (CSV)
    4. BHW account sellers (TXT) — competitor intel
    5. AW master attendees (CSV)
    6. AW verified TG handles (CSV)
    7. HackForums users + contacts (SQLite)
    8. Exploit forum users (CSV)
    9. Scraped TG channel members (CSV)

  Knowledge Base additions → knowledge_base collection
    10. BHW forum posts (CSV) — competitor tactics, niche knowledge
    11. AW chat messages (JSON) — deal patterns
    12. Competitor intel doc (generated)
"""

import csv
import hashlib
import json
import logging
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import chromadb
import config

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("ingest_leads")

csv.field_size_limit(10_000_000)

HOME = Path("/home/cjs")
BHW = HOME / "blackhatworld"
AW = HOME / "aw-attendee-data"
HF = HOME / "hackforums" / "hackforums.db"
EXPLOIT_CSV = Path(config.EXPLOIT_CSV)
TG_MEMBERS = HOME / "TGadsrun" / "output" / "members_with_usernames.csv"
TG_CHANNELS_DB = HOME / "TGadsrun" / "output" / "channels.db"

BATCH = config.BATCH_SIZE
CHUNK_SIZE = config.CHUNK_SIZE
CHUNK_OVERLAP = config.CHUNK_OVERLAP


def _id(prefix: str, key: str) -> str:
    return hashlib.md5(f"{prefix}:{key}".encode()).hexdigest()


def _chunk(text: str) -> list[str]:
    chunks, start = [], 0
    while start < len(text):
        chunks.append(text[start : start + CHUNK_SIZE])
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return [c.strip() for c in chunks if c.strip()]


def _batch_upsert(collection, ids, docs, metas):
    # Deduplicate within batch (keep last occurrence)
    seen = {}
    for i, cid in enumerate(ids):
        seen[cid] = i
    unique_idx = sorted(seen.values())
    ids = [ids[i] for i in unique_idx]
    docs = [docs[i] for i in unique_idx]
    metas = [metas[i] for i in unique_idx]
    for i in range(0, len(ids), BATCH):
        collection.upsert(
            ids=ids[i : i + BATCH],
            documents=docs[i : i + BATCH],
            metadatas=metas[i : i + BATCH],
        )


# ── Lead Profile Loaders ──────────────────────────────────────────────────


def load_bhw_verified_clients(leads_col):
    """BHW all_verified_clients.csv — 72 high-value verified clients."""
    path = BHW / "all_verified_clients.csv"
    if not path.exists():
        log.warning("Skipping BHW verified clients: %s not found", path)
        return 0
    ids, docs, metas = [], [], []
    with open(path, encoding="utf-8", errors="replace") as f:
        for row in csv.DictReader(f):
            handle = row.get("client_handle", "").strip()
            if not handle:
                continue
            text = (
                f"BHW verified client: @{handle}. "
                f"Name: {row.get('name', '')}. Username: {row.get('username', '')}. "
                f"Niche: {row.get('niche', '')}. Agency: {row.get('agency_related', '')}. "
                f"Rank: {row.get('rank', '')}. Profile score: {row.get('profile_score', '')}."
            )
            ids.append(_id("bhw_client", handle))
            docs.append(text)
            metas.append({"username": handle.lower(), "source": "bhw_verified_client", "niche": row.get("niche", "")})
    _batch_upsert(leads_col, ids, docs, metas)
    log.info("  BHW verified clients: %d", len(ids))
    return len(ids)


def load_bhw_tg_database(leads_col):
    """BHW complete_tg_database.csv — 2,440 TG handles."""
    path = BHW / "complete_tg_database.csv"
    if not path.exists():
        return 0
    ids, docs, metas = [], [], []
    with open(path, encoding="utf-8", errors="replace") as f:
        for row in csv.DictReader(f):
            handle = row.get("handle", "").strip()
            if not handle:
                continue
            ctx = row.get("context_sample", "")[:300]
            text = (
                f"BHW TG user: @{handle}. Name: {row.get('name', '')}. "
                f"Username: {row.get('username', '')}. Mentions: {row.get('mention_count', '')}. "
                f"Verified: {row.get('verified', '')}. Context: {ctx}"
            )
            ids.append(_id("bhw_tg", handle))
            docs.append(text)
            metas.append({"username": handle.lower(), "source": "bhw_tg_database", "mentions": row.get("mention_count", "0")})
    _batch_upsert(leads_col, ids, docs, metas)
    log.info("  BHW TG database: %d", len(ids))
    return len(ids)


def load_bhw_verified_handles(leads_col):
    """BHW verified_active_tg_handles.csv — 2,371 verified handles."""
    path = BHW / "verified_active_tg_handles.csv"
    if not path.exists():
        return 0
    ids, docs, metas = [], [], []
    with open(path, encoding="utf-8", errors="replace") as f:
        for row in csv.DictReader(f):
            handle = row.get("handle", "").strip()
            if not handle:
                continue
            text = (
                f"BHW verified TG handle: @{handle}. Name: {row.get('name', '')}. "
                f"Mentions: {row.get('mention_count', '')}. "
                f"Verified seller: {row.get('is_verified_seller', 'False')}."
            )
            ids.append(_id("bhw_handle", handle))
            docs.append(text)
            is_seller = row.get("is_verified_seller", "False").lower() == "true"
            metas.append({
                "username": handle.lower(),
                "source": "bhw_verified_handle",
                "is_competitor": str(is_seller),
            })
    _batch_upsert(leads_col, ids, docs, metas)
    log.info("  BHW verified handles: %d", len(ids))
    return len(ids)


def load_bhw_account_sellers(leads_col):
    """BHW account_sellers_telegram_verified.txt — 287 competitor handles."""
    path = BHW / "account_sellers_telegram_verified.txt"
    if not path.exists():
        return 0
    ids, docs, metas = [], [], []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("|")
            handle = parts[0].strip().lstrip("@")
            name = parts[1].strip() if len(parts) > 1 else ""
            niche = parts[2].strip() if len(parts) > 2 else "account"
            if not handle:
                continue
            text = f"COMPETITOR — BHW account seller: @{handle}. Name: {name}. Niche: {niche}."
            ids.append(_id("bhw_seller", handle))
            docs.append(text)
            metas.append({"username": handle.lower(), "source": "bhw_account_seller", "is_competitor": "true", "niche": niche})
    _batch_upsert(leads_col, ids, docs, metas)
    log.info("  BHW account sellers (competitors): %d", len(ids))
    return len(ids)


def load_aw_attendees(leads_col):
    """AW all_conferences_master_final.csv — 9,213 attendees."""
    path = AW / "FINAL_EXPORT_V5" / "all_conferences_master_final.csv"
    if not path.exists():
        return 0
    ids, docs, metas = [], [], []
    with open(path, encoding="utf-8", errors="replace") as f:
        for row in csv.DictReader(f):
            uid = row.get("id", "").strip()
            name = row.get("full_name", "").strip()
            if not uid and not name:
                continue
            tg = row.get("telegram", "").strip().lstrip("@")
            company = row.get("company", "")
            position = row.get("position", "")
            niche = row.get("verticals", row.get("company_niche", ""))[:200]
            conf = row.get("conference_name", "")
            conns = row.get("connection_count", "0")
            text = (
                f"Affiliate World attendee: {name}. Position: {position}. "
                f"Company: {company}. Conference: {conf}. "
                f"Niche: {niche}. Connections: {conns}. "
                f"Telegram: @{tg}. " if tg else
                f"Affiliate World attendee: {name}. Position: {position}. "
                f"Company: {company}. Conference: {conf}. "
                f"Niche: {niche}. Connections: {conns}."
            )
            key = tg or uid or name
            ids.append(_id("aw_attendee", key))
            docs.append(text[:CHUNK_SIZE])
            metas.append({
                "username": tg.lower() if tg else "",
                "source": "aw_attendee",
                "company": company[:100],
                "niche": niche[:100],
                "conference": conf,
            })
    _batch_upsert(leads_col, ids, docs, metas)
    log.info("  AW attendees: %d", len(ids))
    return len(ids)


def load_aw_tg_handles(leads_col):
    """AW verified_telegram_handles.csv — 1,586 verified TG handles."""
    path = AW / "FINAL_EXPORT_V5" / "verified_telegram_handles.csv"
    if not path.exists():
        return 0
    ids, docs, metas = [], [], []
    with open(path, encoding="utf-8", errors="replace") as f:
        for row in csv.DictReader(f):
            handle = row.get("telegram_handle", "").strip().lstrip("@")
            if not handle:
                continue
            text = (
                f"AW verified TG: @{handle}. Name: {row.get('name', '')}. "
                f"Position: {row.get('position', '')}. Company: {row.get('company', '')}. "
                f"Niche: {row.get('niche', '')}. Conference: {row.get('conference', '')}. "
                f"Connections: {row.get('connections', '')}. Speaker: {row.get('is_speaker', '')}. "
                f"Score: {row.get('profile_score', '')}."
            )
            ids.append(_id("aw_tg", handle))
            docs.append(text)
            metas.append({
                "username": handle.lower(),
                "source": "aw_verified_tg",
                "niche": row.get("niche", "")[:100],
                "company": row.get("company", "")[:100],
            })
    _batch_upsert(leads_col, ids, docs, metas)
    log.info("  AW TG handles: %d", len(ids))
    return len(ids)


def load_hackforums(leads_col):
    """HackForums users + telegram contacts."""
    if not HF.exists():
        return 0
    conn = sqlite3.connect(str(HF))
    conn.row_factory = sqlite3.Row
    ids, docs, metas = [], [], []

    # Users with telegram contacts
    rows = conn.execute("""
        SELECT u.uid, u.username, u.rank, u.posts_count, u.reputation,
               GROUP_CONCAT(c.contact_value, ', ') as tg_contacts
        FROM users u
        LEFT JOIN contacts c ON u.uid = c.uid AND c.contact_type LIKE '%telegram%'
        GROUP BY u.uid
    """).fetchall()

    for row in rows:
        username = row["username"] or ""
        tg = row["tg_contacts"] or ""
        text = (
            f"HackForums user: {username}. Rank: {row['rank'] or ''}. "
            f"Posts: {row['posts_count'] or ''}. Reputation: {row['reputation'] or ''}. "
            f"Telegram: {tg}."
        )
        ids.append(_id("hf_user", str(row["uid"])))
        docs.append(text)
        # Use first telegram handle if available
        tg_handle = tg.split(",")[0].strip().lstrip("@") if tg else ""
        metas.append({
            "username": tg_handle.lower() if tg_handle else username.lower(),
            "source": "hackforums",
            "rank": row["rank"] or "",
        })

    conn.close()
    _batch_upsert(leads_col, ids, docs, metas)
    log.info("  HackForums users: %d", len(ids))
    return len(ids)


def load_exploit_forum(leads_col):
    """Exploit forum deep_database CSV."""
    if not EXPLOIT_CSV.exists():
        return 0
    ids, docs, metas = [], [], []
    with open(EXPLOIT_CSV, encoding="utf-8", errors="replace") as f:
        for row in csv.DictReader(f):
            username = row.get("username", "").strip()
            if not username:
                continue
            tg = row.get("telegram", "").strip().lstrip("@")
            text = (
                f"Exploit.in user: {username}. Rank: {row.get('rank', '')}. "
                f"Posts: {row.get('posts', '')}. Reputation: {row.get('reputation', '')}. "
                f"Telegram: @{tg}. " if tg else
                f"Exploit.in user: {username}. Rank: {row.get('rank', '')}. "
                f"Posts: {row.get('posts', '')}. Reputation: {row.get('reputation', '')}."
            )
            ids.append(_id("exploit", row.get("user_id", username)))
            docs.append(text)
            metas.append({
                "username": tg.lower() if tg else username.lower(),
                "source": "exploit_forum",
                "rank": row.get("rank", ""),
            })
    _batch_upsert(leads_col, ids, docs, metas)
    log.info("  Exploit forum users: %d", len(ids))
    return len(ids)


def load_tg_members(leads_col):
    """Scraped TG channel members with usernames."""
    if not TG_MEMBERS.exists():
        return 0
    ids, docs, metas = [], [], []
    with open(TG_MEMBERS, encoding="utf-8", errors="replace") as f:
        for row in csv.DictReader(f):
            username = row.get("username", "").strip().lstrip("@")
            if not username:
                continue
            groups = row.get("groups", "")
            text = (
                f"TG channel member: @{username}. "
                f"Name: {row.get('first_name', '')} {row.get('last_name', '')}. "
                f"Premium: {row.get('is_premium', '0')}. "
                f"Messages: {row.get('message_count', '0')}. "
                f"Groups: {row.get('groups_count', '0')}. "
                f"Active in: {groups[:200]}."
            )
            ids.append(_id("tg_member", username))
            docs.append(text[:CHUNK_SIZE])
            metas.append({
                "username": username.lower(),
                "source": "tg_channel_member",
                "is_premium": row.get("is_premium", "0"),
                "message_count": row.get("message_count", "0"),
            })
    _batch_upsert(leads_col, ids, docs, metas)
    log.info("  TG channel members: %d", len(ids))
    return len(ids)


# ── Knowledge Base Loaders ─────────────────────────────────────────────────


def load_bhw_posts(kb_col):
    """BHW forum posts — competitor intel and niche knowledge. Top 10K most relevant."""
    path = BHW / "posts.csv"
    if not path.exists():
        return 0
    ids, docs, metas = [], [], []
    # Filter for relevant categories and high-value posts
    relevant_cats = {"ads", "account", "affiliate", "marketing", "media", "seo", "social",
                     "making money", "marketplace", "black hat", "cpa", "bing", "google",
                     "facebook", "tiktok", "native"}
    count = 0
    with open(path, encoding="utf-8", errors="replace") as f:
        for row in csv.DictReader(f):
            cat = row.get("category", "").lower()
            title = row.get("thread_title", "").lower()
            excerpt = row.get("post_excerpt", "")
            # Filter for ad-account relevant posts
            if not any(k in cat or k in title for k in relevant_cats):
                continue
            if len(excerpt) < 50:
                continue
            text = (
                f"[BHW Forum] Category: {row.get('category', '')}. "
                f"Thread: {row.get('thread_title', '')}. "
                f"By: {row.get('username', '')} ({row.get('user_rank', '')}). "
                f"Content: {excerpt[:400]}"
            )
            for ci, chunk in enumerate(_chunk(text)):
                ids.append(_id("bhw_post", f"{row.get('thread_url', '')}:{ci}"))
                docs.append(chunk)
                metas.append({"source": "bhw_forum_post", "category": row.get("category", "")})
            count += 1
            if count >= 10000:
                break
    _batch_upsert(kb_col, ids, docs, metas)
    log.info("  BHW forum posts: %d posts → %d chunks", count, len(ids))
    return len(ids)


def load_aw_chats(kb_col):
    """AW conference chat messages — networking patterns and deal signals."""
    chat_files = [
        AW / "awd26_chat_messages.json",
        AW / "awa25_chat_messages.json",
        AW / "awe25_chat_messages.json",
    ]
    ids, docs, metas = [], [], []
    total_convos = 0
    for chat_file in chat_files:
        if not chat_file.exists():
            continue
        conf_name = chat_file.stem.replace("_chat_messages", "")
        with open(chat_file, encoding="utf-8") as f:
            data = json.load(f)

        # data is dict of chat_id → list of messages
        for chat_id, messages in data.items():
            if not isinstance(messages, list) or len(messages) < 2:
                continue
            # Build conversation text
            convo_parts = []
            for msg in messages[:20]:  # Cap at 20 messages per thread
                text = msg.get("text", "")
                if text:
                    convo_parts.append(text)
            if not convo_parts:
                continue
            convo_text = (
                f"[AW {conf_name} chat] Conversation {chat_id}: "
                + " | ".join(convo_parts)
            )
            for ci, chunk in enumerate(_chunk(convo_text)):
                ids.append(_id(f"aw_chat_{conf_name}", f"{chat_id}:{ci}"))
                docs.append(chunk)
                metas.append({"source": f"aw_chat_{conf_name}", "chat_id": chat_id})
            total_convos += 1

    _batch_upsert(kb_col, ids, docs, metas)
    log.info("  AW chat messages: %d conversations → %d chunks", total_convos, len(ids))
    return len(ids)


def load_competitor_intel(kb_col):
    """Generate a competitor intelligence document from BHW data."""
    sellers_path = BHW / "account_sellers_telegram_verified.txt"
    competitors_path = BHW / "competitors_clients_master.txt"

    chunks_ids, chunks_docs, chunks_metas = [], [], []

    # Competitor overview from sellers list
    if sellers_path.exists():
        with open(sellers_path, encoding="utf-8", errors="replace") as f:
            sellers_text = f.read()
        doc = (
            "COMPETITOR INTELLIGENCE: Known ad account sellers and renters from "
            "BlackHatWorld forum. These are competitors in the ad account market. "
            "Key competitive advantages for Kliqboost: dedicated account manager, "
            "free replacements same-day, no spend limits, Slack support on Enterprise. "
            f"Competitor handles: {sellers_text[:2000]}"
        )
        for ci, chunk in enumerate(_chunk(doc)):
            chunks_ids.append(_id("competitor_intel", f"sellers:{ci}"))
            chunks_docs.append(chunk)
            chunks_metas.append({"source": "competitor_intelligence"})

    # Competitor/client relationship data
    if competitors_path.exists():
        with open(competitors_path, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()[:5000]
        doc = (
            "MARKET INTELLIGENCE: Competitor and client relationships from BHW. "
            "These users are active in the ad account market — either buying or selling. "
            + "".join(lines[:2000])
        )
        for ci, chunk in enumerate(_chunk(doc)):
            chunks_ids.append(_id("competitor_intel", f"market:{ci}"))
            chunks_docs.append(chunk)
            chunks_metas.append({"source": "market_intelligence"})

    _batch_upsert(kb_col, chunks_ids, chunks_docs, chunks_metas)
    log.info("  Competitor intel: %d chunks", len(chunks_ids))
    return len(chunks_ids)


def load_scraped_channels(kb_col):
    """Scraped TG channels — competitor channel info."""
    if not TG_CHANNELS_DB.exists():
        return 0
    conn = sqlite3.connect(str(TG_CHANNELS_DB))
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT title, members_count, category_name, country, language, description_text
        FROM channels WHERE members_count > 100
        ORDER BY members_count DESC LIMIT 500
    """).fetchall()
    conn.close()

    ids, docs, metas = [], [], []
    for row in rows:
        title = row["title"] or ""
        desc = (row["description_text"] or "")[:300]
        text = (
            f"TG Channel: {title}. Members: {row['members_count']}. "
            f"Category: {row['category_name'] or ''}. Country: {row['country'] or ''}. "
            f"Language: {row['language'] or ''}. Description: {desc}"
        )
        ids.append(_id("tg_channel", title))
        docs.append(text)
        metas.append({"source": "tg_channel", "category": row["category_name"] or ""})
    _batch_upsert(kb_col, ids, docs, metas)
    log.info("  Scraped channels: %d", len(ids))
    return len(ids)


# ── Main ───────────────────────────────────────────────────────────────────


def main():
    db_path = config.CHROMA_DB_PATH
    Path(db_path).mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=db_path)

    # Reset lead_profiles for clean ingest
    try:
        client.delete_collection(config.COLLECTION_LEADS)
    except Exception:
        pass
    leads = client.get_or_create_collection(config.COLLECTION_LEADS)

    # Get existing KB collection (don't reset — keep strategy docs)
    kb = client.get_or_create_collection(config.COLLECTION_KB)
    kb_before = kb.count()

    log.info("═══ LEAD PROFILES ═══")
    total_leads = 0
    total_leads += load_bhw_verified_clients(leads)
    total_leads += load_bhw_tg_database(leads)
    total_leads += load_bhw_verified_handles(leads)
    total_leads += load_bhw_account_sellers(leads)
    total_leads += load_aw_attendees(leads)
    total_leads += load_aw_tg_handles(leads)
    total_leads += load_hackforums(leads)
    total_leads += load_exploit_forum(leads)
    total_leads += load_tg_members(leads)

    log.info("")
    log.info("═══ KNOWLEDGE BASE (additions) ═══")
    total_kb_new = 0
    total_kb_new += load_bhw_posts(kb)
    total_kb_new += load_aw_chats(kb)
    total_kb_new += load_competitor_intel(kb)
    total_kb_new += load_scraped_channels(kb)

    log.info("")
    log.info("═══ SUMMARY ═══")
    log.info("  Lead profiles: %d docs", leads.count())
    log.info("  Knowledge base: %d docs (was %d, added %d)", kb.count(), kb_before, total_kb_new)
    log.info("  ChromaDB path: %s", db_path)
    log.info("✅ Full ingestion complete!")


if __name__ == "__main__":
    main()
