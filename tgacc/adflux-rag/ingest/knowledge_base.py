"""Load AdFlux Media knowledge base into the knowledge_base collection.

This creates hard-coded business documents covering services, pricing, FAQs,
and objection handling so the AI auto-responder can retrieve relevant context.
"""

import hashlib
import sys
from pathlib import Path

import chromadb
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config


KB_DOCUMENTS = {
    # ── Services ──────────────────────────────────────────────────────────
    "services_overview": (
        "AdFlux Media is a premium agency ad account provider. "
        "We supply whitelisted, high-trust agency ad accounts for all major platforms: "
        "Google Ads, Meta (Facebook & Instagram), TikTok Ads, Taboola, Outbrain, and Mediago. "
        "Our accounts come pre-approved for restricted verticals and are managed through our agency MCC/BM. "
        "We also offer account rentals (you run ads on our accounts) and full campaign management services."
    ),
    "services_google": (
        "Google Ads Agency Accounts: Whitelisted agency sub-accounts under our MCC. "
        "Unlimited daily spend capacity, no spend caps. Pre-approved for finance, crypto, trading, "
        "Nutra, supplements, sweepstakes, tech support, VPN, gambling, and other restricted niches. "
        "Accounts are ready within 2 hours max. If an account gets suspended, we provide an immediate "
        "free replacement and instant ad funds transfer to the new account. We handle policy compliance and appeals on your behalf."
    ),
    "services_meta": (
        "Meta (Facebook/Instagram) Agency Accounts: Premium agency BM ad accounts with "
        "high trust scores and unlimited spend limits. Suitable for e-commerce, lead generation, "
        "finance, crypto, Nutra, sweepstakes, and dating verticals. Warmed-up accounts with "
        "spending history. Ban replacement guarantee included. We provide dedicated ad account "
        "managers and pixel/CAPI integration support."
    ),
    "services_native": (
        "Native Ads Agency Accounts: We provide agency accounts for Taboola, Outbrain, and Mediago. "
        "These are ideal for content arbitrage, finance, health, and news verticals. "
        "Our native ad accounts come with pre-approved campaign templates and dedicated "
        "account representatives at each platform. Higher approval rates for sensitive content."
    ),
    "services_tiktok": (
        "TikTok Ads Agency Accounts: Whitelisted TikTok agency sub-accounts for e-commerce, "
        "app installs, gaming, finance, and Nutra verticals. High spend limits, priority review, "
        "and direct TikTok rep support. We help with creative compliance and ad format optimization."
    ),
    "services_rentals": (
        "Account Rentals: Don't want to manage your own accounts? Rent our pre-warmed agency "
        "accounts on a monthly basis. You get full access to run campaigns while we handle "
        "compliance, billing, and account health. Ideal for media buyers who need quick access "
        "without the overhead of account setup and warming."
    ),
    "services_management": (
        "Campaign Management: Full-service campaign management by our team of experienced "
        "media buyers. We handle strategy, creative, targeting, optimization, and reporting. "
        "Performance-based pricing available. Specializing in lead generation, e-commerce, "
        "and direct response campaigns across all major platforms."
    ),

    # ── Niches ────────────────────────────────────────────────────────────
    "niches": (
        "AdFlux Media specializes in restricted and high-risk verticals that are difficult "
        "to advertise through standard accounts. Our core niches include: "
        "Finance (forex, trading platforms, investment), Crypto (exchanges, wallets, DeFi, tokens), "
        "Nutra (supplements, health products, weight loss, CBD), Trading (binary options, CFDs), "
        "Sweepstakes (giveaways, prize draws, competitions), Tech Support (software, antivirus, VPN), "
        "Gambling (online casinos, sports betting, poker), Dating (matchmaking, apps), "
        "E-commerce (dropshipping, high-ticket items), Insurance, Real Estate, and Legal services."
    ),

    # ── Features ──────────────────────────────────────────────────────────
    "features": (
        "Key features of AdFlux Media accounts:\n"
        "• Unlimited spend — no daily or lifetime caps\n"
        "• Whitelisted accounts — pre-approved for restricted verticals\n"
        "• Within 2 hours delivery — all accounts ready in under 2 hours\n"
        "• Immediate ban replacement — instant free replacement if account is suspended\n"
        "• Immediate ad funds transfer — your ad balance moves to the new account instantly\n"
        "• Dedicated account manager — personal support for each client\n"
        "• Multi-platform — Google, Meta, TikTok, Taboola, Outbrain, Mediago\n"
        "• Flexible billing — prepaid or postpaid options available\n"
        "• Compliance support — we handle policy reviews and appeals\n"
        "• Priority platform support — direct reps at each ad network"
    ),

    # ── Pricing ───────────────────────────────────────────────────────────
    "pricing": (
        "AdFlux Media Pricing:\n\n"
        "💰 Bing Ads:\n"
        "🥉 Basic — $100/account: 1 replacement free, no spend limit, top up fee 10%, min top up $100, dedicated TG group support\n"
        "🥈 Pro — from $300/account: 3 replacements free, no spend limit, top up fee 8%, min top up $500, priority support + account manager\n"
        "🥇 Enterprise rental — from $1000/month: unlimited replacements, no spend limit, top up fee 6%, min top up $1000, dedicated account manager + Slack channel\n\n"
        "💰 Google Ads:\n"
        "🥉 Basic — $50/account: 1 replacement free, no spend limit, top up fee 10%, min top up $100, dedicated TG group support\n"
        "🥈 Pro — from $100/account: 3 replacements free, no spend limit, top up fee 8%, min top up $500, priority support + account manager\n"
        "🥇 Enterprise rental — from $800/month: unlimited replacements, no spend limit, top up fee 6%, min top up $1000, dedicated account manager + Slack channel\n\n"
        "💰 Facebook Ads:\n"
        "🥉 Basic — from $200/mo: 1 BM + 3 ad accounts, up to $1,000/day spend limit, email support\n"
        "🥈 Pro — from $450/mo: 1 BM + 10 ad accounts, up to $10,000/day spend limit, priority support + account manager\n"
        "🥇 Enterprise — from $1,000/mo: multiple BMs + unlimited ad accounts, unlimited spend, dedicated account manager + Slack channel\n\n"
        "💰 Taboola:\n"
        "🥉 Basic — $50/account: 1 replacement free, no spend limit, top up fee 5%, min top up $100, dedicated TG group support\n"
        "🥈 Pro — from $100/account: 3 replacements free, no spend limit, top up fee 3%, min top up $500, priority support + account manager\n"
        "🥇 Enterprise rental — from $800/month: unlimited replacements, no spend limit, top up fee 2%, min top up $1000, dedicated account manager + Slack channel"
    ),

    # ── FAQ ────────────────────────────────────────────────────────────────
    "faq_what_is": (
        "FAQ: What is AdFlux Media?\n"
        "AdFlux Media is a premium agency ad account provider. We give media buyers and "
        "advertisers access to whitelisted, high-trust ad accounts on Google, Meta, TikTok, "
        "and native ad platforms. Our accounts are pre-approved for restricted verticals "
        "like crypto, finance, Nutra, and sweepstakes — niches where standard accounts "
        "typically get banned quickly."
    ),
    "faq_how_it_works": (
        "FAQ: How does it work?\n"
        "1. Tell us your niche, platform, and expected spend\n"
        "2. We set up a whitelisted agency sub-account under our MCC/BM\n"
        "3. You get full access to run campaigns (we share the account or add your pixel)\n"
        "4. You fund the account via prepaid balance or invoice\n"
        "5. If the account gets flagged or banned, we replace it immediately with instant ad funds transfer\n"
        "6. Our compliance team monitors account health proactively"
    ),
    "faq_which_niches": (
        "FAQ: Which niches do you support?\n"
        "We specialize in restricted verticals: finance, crypto, forex, trading, Nutra, "
        "supplements, sweepstakes, tech support, gambling, dating, CBD, weight loss, "
        "insurance, real estate, and legal. We also support standard niches like e-commerce, "
        "SaaS, apps, and lead generation. If you're unsure whether your niche is supported, "
        "just ask — we've likely worked with it before."
    ),
    "faq_ban_replacement": (
        "FAQ: What happens if my account gets banned?\n"
        "We provide immediate free replacement — zero waiting. Your ad funds are instantly "
        "transferred/withdrawn to your new account. All plans include free replacements. "
        "We also proactively monitor account health to prevent bans before they happen."
    ),
    "faq_payment": (
        "FAQ: How do I pay?\n"
        "We accept crypto only — BTC, ETH, USDT (ERC20). "
        "Wallet addresses:\n"
        "BTC: bc1qakgfhqtm5c803xspzyawg0veg3g2eae885uu99\n"
        "ETH: 0xd6ae83AaBcB4DC048Eb6A479b901e8ebDB9A8709\n"
        "USDT ERC20: 0xd6ae83AaBcB4DC048Eb6A479b901e8ebDB9A8709\n"
        "Send payment proof to @Chris_AdFlux after transfer."
    ),
    "faq_delivery": (
        "FAQ: How quickly can I get an account?\n"
        "All accounts are delivered within 2 hours max. Most are ready in under 30 minutes. "
        "No waiting days — pay and get your account fast."
    ),
    "faq_platforms": (
        "FAQ: Which platforms do you support?\n"
        "We currently support: Google Ads, Meta (Facebook & Instagram), TikTok Ads, "
        "Taboola, Outbrain, and Mediago. We're constantly adding new platforms. "
        "If you need an account on a platform not listed, reach out — we may be able to help."
    ),
    "faq_support": (
        "FAQ: What kind of support do you provide?\n"
        "All plans include Telegram-based support. Growth and Enterprise plans get a "
        "dedicated account manager who handles compliance, troubleshooting, and optimization. "
        "Enterprise clients get 24/7 priority support with guaranteed response times. "
        "We also provide creative review, policy compliance guidance, and appeal assistance."
    ),

    # ── Objection Handling ────────────────────────────────────────────────
    "objection_expensive": (
        "Objection: 'It's too expensive'\n"
        "Response: I understand budget is important. Consider this — how much time and money "
        "do you spend creating new accounts that get banned within days? Our clients typically "
        "save 40-60% on account replacement costs alone. Plus, with unlimited spend capacity "
        "and no bans, your ROAS improves significantly. We offer flexible plans starting from "
        "just $XXX/month. Would you like to see a cost comparison for your specific situation?"
    ),
    "objection_trust": (
        "Objection: 'How do I know it works / is legit?'\n"
        "Response: Great question — trust is everything in this space. We've been operating "
        "for over 2 years with hundreds of active clients. I can share case studies, testimonials, "
        "and connect you with existing clients for references. We also start with a trial period "
        "so you can test with lower spend before committing. Our ban replacement guarantee is "
        "in writing — if we don't deliver, you don't pay."
    ),
    "objection_already_have": (
        "Objection: 'I already have accounts / a provider'\n"
        "Response: That's great — having backup accounts is actually a best practice. Many of "
        "our clients use us alongside their existing setup as a safety net. Our accounts are "
        "whitelisted at the agency level, which means higher trust scores and better delivery "
        "than individual accounts. Would you be open to testing one account alongside your "
        "current setup to compare performance?"
    ),
    "objection_banned_before": (
        "Objection: 'I've been burned before / other providers didn't work'\n"
        "Response: I hear you — there are a lot of unreliable providers out there. What makes us "
        "different is our agency-level whitelisting. We don't sell aged or farmed accounts. These "
        "are legitimate sub-accounts under our verified agency, which means Google/Meta actually "
        "trusts them. Our ban replacement guarantee means you're never left without an account. "
        "Start with one account to test — zero risk."
    ),
    "objection_need_time": (
        "Objection: 'I need time to think about it'\n"
        "Response: Absolutely, take your time. Just keep in mind that every day without a stable "
        "account is potential revenue lost. I'll send you our info sheet so you have everything "
        "you need to make a decision. Also, we have a limited-time onboarding offer — if you "
        "start this week, we'll include an extra replacement account at no cost. Want me to "
        "reserve a spot for you?"
    ),
    "objection_compliance": (
        "Objection: 'Won't these accounts also get banned?'\n"
        "Response: No provider can guarantee 100% ban-proof accounts — anyone who says that is lying. "
        "What we CAN guarantee is that our accounts have significantly higher survival rates because "
        "they're whitelisted at the agency level. We also provide compliance guidance to keep your "
        "ads within policy. And if an account does get flagged, we replace it immediately for free "
        "with instant ad funds transfer. "
        "Our clients typically see 3-5x longer account lifespans compared to self-created accounts."
    ),

    # ── BANT Scoring ──────────────────────────────────────────────────────
    "bant_scoring": (
        "BANT Lead Scoring Guide for AdFlux Media:\n\n"
        "Budget: What's their monthly ad spend? ($1K-5K = low, $5K-20K = medium, $20K+ = high)\n"
        "Authority: Are they the decision maker? (media buyer = high, assistant = low)\n"
        "Need: Do they have an urgent need? (account just banned = high, exploring = low)\n"
        "Timeline: When do they need accounts? (this week = hot, next month = warm, someday = cold)\n\n"
        "Scoring: High = 3 or more high indicators → fast-track to close\n"
        "Medium = 2 high indicators → nurture with value\n"
        "Low = 0-1 high indicators → educate and build relationship\n\n"
        "Key qualifying questions:\n"
        "• What platforms are you currently running ads on?\n"
        "• What's your monthly ad spend?\n"
        "• What niche/vertical are you in?\n"
        "• Have you had account bans recently?\n"
        "• When are you looking to get started?"
    ),
}


def _chunk_text(text: str, size: int = config.CHUNK_SIZE, overlap: int = config.CHUNK_OVERLAP):
    chunks = []
    start = 0
    while start < len(text):
        chunks.append(text[start:start + size])
        start += size - overlap
    return chunks


def run(chroma_client: chromadb.ClientAPI | None = None):
    """Load the knowledge base into ChromaDB."""
    print("\n══════ Knowledge Base Ingestion ══════")

    if chroma_client is None:
        chroma_client = chromadb.PersistentClient(path=config.CHROMA_DB_PATH)
    collection = chroma_client.get_or_create_collection(config.COLLECTION_KB)

    ids, docs, metas = [], [], []

    for doc_key, text in KB_DOCUMENTS.items():
        chunks = _chunk_text(text)
        for i, chunk in enumerate(chunks):
            doc_id = f"kb_{doc_key}_{i}"
            ids.append(doc_id)
            docs.append(chunk)
            metas.append({
                "doc_key": doc_key,
                "category": doc_key.split("_")[0],
            })

    # Batch upsert
    for start in tqdm(range(0, len(docs), config.BATCH_SIZE), desc="  Loading KB"):
        end = start + config.BATCH_SIZE
        collection.upsert(
            ids=ids[start:end],
            documents=docs[start:end],
            metadatas=metas[start:end],
        )

    print(f"  ✓ Knowledge base loaded — {len(docs)} chunks from {len(KB_DOCUMENTS)} documents")
    print(f"    Collection size: {collection.count()}")


if __name__ == "__main__":
    run()
