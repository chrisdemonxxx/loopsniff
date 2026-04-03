#!/usr/bin/env python3
"""Test retrieval from the AdFlux RAG system.

Usage:
    python test_retrieval.py --username "some_user"
    python test_retrieval.py --query "agency ad accounts for crypto"
    python test_retrieval.py --username "some_user" --query "what plans do you offer"
    python test_retrieval.py --stats
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from retrieval.retriever import Retriever
from retrieval.prompt_builder import build_outreach_prompt, build_simple_prompt


def main():
    parser = argparse.ArgumentParser(description="Test AdFlux RAG retrieval")
    parser.add_argument("--username", "-u", help="TG username to look up")
    parser.add_argument("--query", "-q", help="Knowledge base query")
    parser.add_argument("--search", "-s", help="Semantic search across leads")
    parser.add_argument("--source", help="Filter lead search by source (bhw/aw_profile/aw_chat/hackforums/exploit)")
    parser.add_argument("--n", type=int, default=5, help="Number of results")
    parser.add_argument("--prompt", action="store_true", help="Show the built prompt")
    parser.add_argument("--stats", action="store_true", help="Show collection stats")
    args = parser.parse_args()

    if not any([args.username, args.query, args.search, args.stats]):
        parser.print_help()
        return

    retriever = Retriever()

    if args.stats:
        stats = retriever.stats()
        print("\n══════ Collection Stats ══════")
        for k, v in stats.items():
            print(f"  {k}: {v:,} documents")
        print()

    if args.username:
        print(f"\n══════ Lead Profile: @{args.username} ══════")
        results = retriever.get_lead_context(args.username, n_results=args.n)
        if results:
            for i, r in enumerate(results, 1):
                print(f"\n─── Result {i} (distance: {r.get('distance', 'N/A'):.4f}) ───")
                print(f"  Metadata: {r.get('metadata', {})}")
                print(f"  Text: {r['text'][:500]}")
        else:
            print("  No results found for this username.")

    if args.query:
        print(f"\n══════ Knowledge Base: '{args.query}' ══════")
        results = retriever.get_knowledge(args.query, n_results=args.n)
        if results:
            for i, r in enumerate(results, 1):
                print(f"\n─── Result {i} (distance: {r.get('distance', 'N/A'):.4f}) ───")
                print(f"  Category: {r.get('metadata', {}).get('category', 'N/A')}")
                print(f"  Text: {r['text'][:500]}")
        else:
            print("  No results found.")

    if args.search:
        print(f"\n══════ Lead Search: '{args.search}' ══════")
        results = retriever.search_leads(args.search, n_results=args.n, source=args.source)
        if results:
            for i, r in enumerate(results, 1):
                print(f"\n─── Result {i} (distance: {r.get('distance', 'N/A'):.4f}) ───")
                print(f"  Metadata: {r.get('metadata', {})}")
                print(f"  Text: {r['text'][:300]}")
        else:
            print("  No results found.")

    if args.prompt and (args.username or args.query):
        print("\n══════ Built Prompt ══════")
        lead_ctx = retriever.get_lead_context(args.username, n_results=3) if args.username else []
        kb_ctx = retriever.get_knowledge(args.query or "tell me about your services", n_results=3)
        message = args.query or "Hi, I'm interested in ad accounts"

        if args.username:
            prompt = build_outreach_prompt(lead_ctx, kb_ctx, lead_message=message)
        else:
            prompt = build_simple_prompt(message, kb_ctx)

        print(json.dumps(prompt, indent=2)[:3000])


if __name__ == "__main__":
    main()
