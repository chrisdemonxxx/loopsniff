"""Ingest Affiliate World conference attendee profiles into lead_profiles.

Data:
  all_conferences_master_final.csv columns:
    id, conference, conference_name, first_name, last_name, full_name,
    position, company, company_type, company_website, company_description,
    company_niche, company_country, booth_number, booth_contact_email,
    email, telegram, whatsapp, linkedin, instagram, twitter, facebook,
    website, phone, verticals, looking_to_meet, traffic_sources, geos,
    is_speaker, speaker_bio

  verified_telegram_handles.csv columns:
    telegram_handle, name, position, company, niche, email, whatsapp,
    linkedin, conference, profile_score, confidence, connections, is_speaker
"""

import hashlib
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


def _doc_id(handle: str, idx: int) -> str:
    global _counter
    _counter += 1
    h = hashlib.md5(f"aw_profile_{handle}_{idx}_{_counter}".encode()).hexdigest()[:12]
    doc_id = f"awp_{h}"
    while doc_id in _seen_ids:
        _counter += 1
        h = hashlib.md5(f"aw_profile_{handle}_{idx}_{_counter}".encode()).hexdigest()[:12]
        doc_id = f"awp_{h}"
    _seen_ids.add(doc_id)
    return doc_id


def _clean(val) -> str:
    if pd.isna(val):
        return ""
    return str(val).strip()


def run(chroma_client: chromadb.ClientAPI | None = None):
    """Ingest AW attendee profiles."""
    print("\n══════ AW Profiles Ingestion ══════")
    _seen_ids.clear()

    if chroma_client is None:
        chroma_client = chromadb.PersistentClient(path=config.CHROMA_DB_PATH)
    collection = chroma_client.get_or_create_collection(config.COLLECTION_LEADS)

    # ── Load verified TG handles for enrichment ───────────────────────────
    tg_lookup: dict[str, dict] = {}  # telegram_handle -> row data
    if config.AW_TG_CSV.exists():
        tg_df = pd.read_csv(config.AW_TG_CSV, dtype=str, encoding_errors="replace")
        for _, row in tg_df.iterrows():
            handle = _clean(row.get("telegram_handle"))
            if handle:
                handle_clean = handle.lstrip("@").lower()
                tg_lookup[handle_clean] = row.to_dict()
        print(f"  Loaded {len(tg_lookup)} verified TG handles")

    # ── Read master CSV ───────────────────────────────────────────────────
    if not config.AW_MASTER_CSV.exists():
        print("  ✗ all_conferences_master_final.csv not found — aborting")
        return

    df = pd.read_csv(config.AW_MASTER_CSV, dtype=str, encoding_errors="replace")
    print(f"  {len(df):,} attendee rows loaded")

    ids, docs, metas = [], [], []
    processed = 0

    for _, row in tqdm(df.iterrows(), total=len(df), desc="  AW profiles"):
        tg_raw = _clean(row.get("telegram", ""))
        if not tg_raw:
            continue

        tg_handle = tg_raw.lstrip("@").strip()
        if not tg_handle:
            continue

        name = _clean(row.get("full_name")) or f'{_clean(row.get("first_name"))} {_clean(row.get("last_name"))}'.strip()
        position = _clean(row.get("position"))
        company = _clean(row.get("company"))
        niche = _clean(row.get("company_niche"))
        verticals = _clean(row.get("verticals"))
        looking = _clean(row.get("looking_to_meet"))
        traffic = _clean(row.get("traffic_sources"))
        geos = _clean(row.get("geos"))
        conference = _clean(row.get("conference_name")) or _clean(row.get("conference"))
        is_speaker = _clean(row.get("is_speaker"))
        speaker_bio = _clean(row.get("speaker_bio"))
        company_desc = _clean(row.get("company_description"))

        parts = [f"AW Attendee: {name}"]
        if position:
            parts.append(f"Position: {position}")
        if company:
            parts.append(f"Company: {company}")
        if company_desc:
            parts.append(f"Company info: {company_desc}")
        if niche:
            parts.append(f"Niche: {niche}")
        if verticals:
            parts.append(f"Verticals: {verticals}")
        if looking:
            parts.append(f"Looking to meet: {looking}")
        if traffic:
            parts.append(f"Traffic sources: {traffic}")
        if geos:
            parts.append(f"Geos: {geos}")
        if conference:
            parts.append(f"Conference: {conference}")
        if is_speaker and is_speaker.lower() == "true":
            parts.append(f"Speaker: {speaker_bio}" if speaker_bio else "Speaker: Yes")

        # Enrich from verified TG handles
        enriched = tg_lookup.get(tg_handle.lower(), {})
        connections = _clean(enriched.get("connections"))
        if connections:
            parts.append(f"Connections: {connections}")

        full_text = f"TG: @{tg_handle}\n" + "\n".join(parts)
        chunks = _chunk_text(full_text)

        for i, chunk in enumerate(chunks):
            ids.append(_doc_id(tg_handle, i))
            docs.append(chunk)
            metas.append({
                "username": tg_handle,
                "source": "aw_profile",
                "category": niche or verticals or "",
                "date": "",
                "conference": conference,
            })
        processed += 1

    # ── Batch upsert ──────────────────────────────────────────────────────
    print(f"  {processed} profiles → {len(docs)} chunks")
    for start in tqdm(range(0, len(docs), config.BATCH_SIZE), desc="  Upserting"):
        end = start + config.BATCH_SIZE
        collection.upsert(
            ids=ids[start:end],
            documents=docs[start:end],
            metadatas=metas[start:end],
        )

    print(f"  ✓ AW profiles ingestion complete — collection size: {collection.count()}")


if __name__ == "__main__":
    run()
