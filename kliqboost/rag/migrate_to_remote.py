#!/usr/bin/env python3
"""Migrate ChromaDB data from local PersistentClient to remote HttpClient.

Usage:
    python migrate_to_remote.py --host <host> --port <port>
    python migrate_to_remote.py --host kliqboost-vectordb --port 10000
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import chromadb
import config

BATCH_SIZE = 500


def migrate_collection(src_col, dst_col, name: str):
    """Copy all records from src collection to dst collection in batches."""
    total = src_col.count()
    if total == 0:
        print(f"  {name}: empty, skipping")
        return

    dst_count = dst_col.count()
    if dst_count >= total:
        print(f"  {name}: already has {dst_count}/{total} records, skipping")
        return

    print(f"  {name}: migrating {total} records (dst has {dst_count})...")

    offset = 0
    migrated = 0
    t0 = time.time()

    while offset < total:
        batch = src_col.get(
            limit=BATCH_SIZE,
            offset=offset,
            include=["documents", "metadatas", "embeddings"],
        )

        ids = batch["ids"]
        if not ids:
            break

        dst_col.upsert(
            ids=ids,
            documents=batch.get("documents"),
            metadatas=batch.get("metadatas"),
            embeddings=batch.get("embeddings"),
        )

        migrated += len(ids)
        elapsed = time.time() - t0
        rate = migrated / elapsed if elapsed > 0 else 0
        pct = migrated / total * 100
        print(f"    {migrated}/{total} ({pct:.1f}%) — {rate:.0f} rec/s", end="\r")

        offset += BATCH_SIZE

    elapsed = time.time() - t0
    print(f"\n  {name}: done — {migrated} records in {elapsed:.1f}s")


def main():
    parser = argparse.ArgumentParser(description="Migrate ChromaDB local → remote")
    parser.add_argument("--host", required=True, help="Remote ChromaDB host")
    parser.add_argument("--port", type=int, default=8000, help="Remote ChromaDB port")
    parser.add_argument("--local-path", default=config.CHROMA_DB_PATH, help="Local ChromaDB path")
    args = parser.parse_args()

    local_path = args.local_path
    if not Path(local_path).exists():
        print(f"❌ Local ChromaDB not found at {local_path}")
        sys.exit(1)

    print(f"📂 Local: {local_path}")
    print(f"🌐 Remote: {args.host}:{args.port}")

    src = chromadb.PersistentClient(path=local_path)
    dst = chromadb.HttpClient(host=args.host, port=args.port)

    # Test connection
    try:
        heartbeat = dst.heartbeat()
        print(f"✅ Remote connected (heartbeat: {heartbeat})")
    except Exception as e:
        print(f"❌ Cannot connect to remote: {e}")
        sys.exit(1)

    # Migrate each collection
    for col_name in [config.COLLECTION_LEADS, config.COLLECTION_KB]:
        src_col = src.get_or_create_collection(col_name)
        dst_col = dst.get_or_create_collection(col_name)
        migrate_collection(src_col, dst_col, col_name)

    # Verify
    print("\n📊 Final counts:")
    for col_name in [config.COLLECTION_LEADS, config.COLLECTION_KB]:
        sc = src.get_or_create_collection(col_name).count()
        dc = dst.get_or_create_collection(col_name).count()
        status = "✅" if dc >= sc else "⚠️"
        print(f"  {status} {col_name}: local={sc}, remote={dc}")

    print("\n🎉 Migration complete!")


if __name__ == "__main__":
    main()
