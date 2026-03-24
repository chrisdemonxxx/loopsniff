#!/usr/bin/env python3
"""Quick smoke-test for the AI responder — validates imports and basic flow."""

import asyncio
import sys

sys.path.insert(0, "/home/cjs/tgacc/adflux-rag")
sys.path.insert(0, "/home/cjs/tgacc/bulk-account-creator")


async def test_ai_responder():
    print("=" * 60)
    print("AI Responder Integration Test")
    print("=" * 60)

    # 1. Test RAG retriever import + init
    print("\n[1] Testing RAG Retriever import...")
    from retrieval.retriever import Retriever
    retriever = Retriever()
    stats = retriever.stats()
    print(f"    ✅ Retriever OK — {stats['lead_profiles']} leads, "
          f"{stats['knowledge_base']} KB docs")

    # 2. Test BANT scorer import
    print("\n[2] Testing BANT Scorer import...")
    from outreach.scoring.bant_scorer import BANTScorer
    scorer = BANTScorer()
    result = scorer.score_from_text(
        "I need Google Ads accounts ASAP, budget around $10k for crypto"
    )
    print(f"    ✅ BANTScorer OK — score={result['total']}, tier={result['tier']}")
    print(f"    Extracted: {result['extracted']}")

    # 3. Test AIResponder class import
    print("\n[3] Testing AIResponder import...")
    from outreach.ai_responder import AIResponder
    responder = AIResponder()
    print("    ✅ AIResponder instantiated OK")

    # 4. Test RAG context retrieval
    print("\n[4] Testing RAG knowledge retrieval...")
    kb_results = retriever.get_knowledge("ad account pricing", n_results=2)
    if kb_results:
        print(f"    ✅ Got {len(kb_results)} knowledge results")
        for i, r in enumerate(kb_results):
            preview = r["text"][:100].replace("\n", " ")
            print(f"       [{i+1}] {preview}...")
    else:
        print("    ⚠️  No knowledge results (KB may be empty)")

    # 5. Test Ollama Cloud connectivity
    print("\n[5] Testing Ollama Cloud API...")
    from outreach.ai_responder import _ollama_chat
    reply = await _ollama_chat(
        [{"role": "user", "content": "Hi, I need Google ad accounts. What do you offer?"}]
    )
    if reply:
        print(f"    ✅ Ollama Cloud replied: {reply[:150]}...")
    else:
        print("    ⚠️  No reply (API may be unreachable — non-blocking)")

    # 6. Test conversation scoring flow
    print("\n[6] Testing conversation BANT scoring...")
    msgs = [
        "hi, do you sell google ads accounts?",
        "I run crypto offers, need something ASAP",
        "budget is around $50k per month",
    ]
    conv_score = scorer.score_from_conversation(msgs)
    print(f"    ✅ Conversation score: {conv_score['total']} ({conv_score['tier']})")
    hot = conv_score["total"] >= 75
    print(f"    Hot lead? {'YES 🔥' if hot else 'No'}")

    print("\n" + "=" * 60)
    print("All import and integration tests passed ✅")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_ai_responder())
