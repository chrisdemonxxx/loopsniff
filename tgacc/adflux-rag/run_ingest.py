#!/usr/bin/env python3
"""CLI to run AdFlux RAG ingestions.

Usage:
    python run_ingest.py --all              # Run all ingestions
    python run_ingest.py --bhw              # Just BHW
    python run_ingest.py --aw-profiles      # Just AW profiles
    python run_ingest.py --aw-chats         # Just AW chats
    python run_ingest.py --hackforums       # Just HackForums
    python run_ingest.py --exploit          # Just exploit forum
    python run_ingest.py --knowledge-base   # Just knowledge base
    python run_ingest.py --stats            # Show collection stats
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import chromadb
import config
from ingest import (
    bhw_ingest,
    aw_profiles_ingest,
    aw_chats_ingest,
    hackforums_ingest,
    exploit_ingest,
    knowledge_base,
)


def show_stats(client: chromadb.ClientAPI):
    """Print collection statistics."""
    print("\n══════ Collection Statistics ══════")
    for name in [config.COLLECTION_LEADS, config.COLLECTION_KB]:
        try:
            col = client.get_collection(name)
            print(f"  {name}: {col.count():,} documents")
        except Exception:
            print(f"  {name}: (not created yet)")
    print()


def main():
    parser = argparse.ArgumentParser(description="AdFlux RAG Ingestion CLI")
    parser.add_argument("--all", action="store_true", help="Run all ingestions")
    parser.add_argument("--bhw", action="store_true", help="Ingest BHW posts")
    parser.add_argument("--aw-profiles", action="store_true", help="Ingest AW profiles")
    parser.add_argument("--aw-chats", action="store_true", help="Ingest AW chats")
    parser.add_argument("--hackforums", action="store_true", help="Ingest HackForums")
    parser.add_argument("--exploit", action="store_true", help="Ingest Exploit forum")
    parser.add_argument("--knowledge-base", action="store_true", help="Load knowledge base")
    parser.add_argument("--stats", action="store_true", help="Show collection stats")
    args = parser.parse_args()

    # If nothing specified, show help
    if not any(vars(args).values()):
        parser.print_help()
        return

    print(f"ChromaDB path: {config.CHROMA_DB_PATH}")
    client = chromadb.PersistentClient(path=config.CHROMA_DB_PATH)

    if args.stats:
        show_stats(client)
        if not any(v for k, v in vars(args).items() if k != "stats"):
            return

    t0 = time.time()

    if args.all or args.knowledge_base:
        knowledge_base.run(client)

    if args.all or args.bhw:
        bhw_ingest.run(client)

    if args.all or args.aw_profiles:
        aw_profiles_ingest.run(client)

    if args.all or args.aw_chats:
        aw_chats_ingest.run(client)

    if args.all or args.hackforums:
        hackforums_ingest.run(client)

    if args.all or args.exploit:
        exploit_ingest.run(client)

    elapsed = time.time() - t0
    print(f"\n{'═' * 50}")
    print(f"  Total time: {elapsed:.1f}s")
    show_stats(client)


if __name__ == "__main__":
    main()
