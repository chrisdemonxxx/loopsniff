"""CLI entry point for throwaway Telegram outreach campaigns.

Usage:
  # Run a campaign with defaults
  python run_throwaway.py --campaign my_campaign --niche crypto

  # Run with custom settings
  python run_throwaway.py --campaign test1 --niche trading --quota 100 --batch-max 3

  # Pre-generate messages only (no sending)
  python run_throwaway.py --campaign test1 --niche crypto --generate-only --count 500

  # Check campaign / pool status
  python run_throwaway.py --campaign test1 --status

  # Import new sessions before running
  python run_throwaway.py --import-sessions ./new_sessions/ --campaign test1 --niche crypto
"""

import argparse
import asyncio
import os
import sys

from loguru import logger


async def _show_status(campaign_id: str) -> None:
    """Print session pool, target, and message pool statistics."""
    from outreach.session_pool import SessionPool
    from outreach.target_scraper import TargetScraper
    from outreach.message_engine import MessageEngine

    pool = SessionPool()
    await pool.init_db()
    session_stats = await pool.get_stats()

    scraper = TargetScraper()
    await scraper.init_db()
    target_stats = await scraper.get_stats()

    engine = MessageEngine()
    await engine.init_db()
    pool_stats = await engine.get_pool_stats(campaign_id)

    print("\n📊 System Status")
    print("─" * 30)

    print("\n📱 Session Pool:")
    for key, val in session_stats.items():
        print(f"  {key}: {val}")

    print("\n🎯 Targets:")
    for key, val in target_stats.items():
        print(f"  {key}: {val}")

    print(f"\n💬 Message Pool (campaign: {campaign_id}):")
    for key, val in pool_stats.items():
        print(f"  {key}: {val}")

    print()


async def _import_sessions(directory: str) -> None:
    """Import .session files from a directory."""
    from outreach.session_pool import SessionPool

    pool = SessionPool(sessions_dir=directory)
    await pool.init_db()
    result = await pool.import_sessions(directory)
    logger.info("Import result: {}", result)


async def _generate_only(
    campaign_id: str,
    niche: str,
    count: int,
    style: str,
    language: str,
    spintax: str,
) -> None:
    """Pre-generate messages without sending."""
    from outreach.message_engine import MessageEngine

    engine = MessageEngine()
    await engine.init_db()

    result = await engine.pre_generate_llm_batch(
        campaign_id,
        niche,
        count,
        style=style,
        language=language,
    )
    logger.info("LLM generation result: {}", result)

    if spintax and result.get("generated", 0) < count:
        remaining = count - result["generated"]
        spintax_result = await engine.pre_generate_spintax_batch(
            campaign_id, spintax, remaining,
        )
        logger.info("Spintax supplement: {}", spintax_result)

    stats = await engine.get_pool_stats(campaign_id)
    logger.info("Message pool stats: {}", stats)


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Throwaway TG Outreach Engine",
    )

    # Campaign settings
    parser.add_argument(
        "--campaign", required=True, help="Campaign ID (unique name)",
    )
    parser.add_argument("--niche", default="crypto", help="Target niche")
    parser.add_argument(
        "--quota", type=int, default=2000, help="Daily message quota",
    )
    parser.add_argument(
        "--batch-min", type=int, default=1, help="Min messages per session",
    )
    parser.add_argument(
        "--batch-max", type=int, default=5, help="Max messages per session",
    )
    parser.add_argument(
        "--country", default="US", help="Proxy country code",
    )
    parser.add_argument(
        "--language", default="en", help="Message language",
    )
    parser.add_argument(
        "--style", default="casual",
        help="Message style (casual/professional)",
    )

    # Message generation
    parser.add_argument(
        "--generate-only", action="store_true",
        help="Only pre-generate messages, don't send",
    )
    parser.add_argument(
        "--count", type=int, default=500, help="Messages to pre-generate",
    )
    parser.add_argument(
        "--spintax", default="", help="Spintax template (fallback)",
    )

    # Session management
    parser.add_argument(
        "--import-sessions", default="",
        help="Import .session files from directory",
    )

    # Status
    parser.add_argument(
        "--status", action="store_true", help="Show pool/campaign status",
    )

    args = parser.parse_args()

    # Load .env
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    # ── Handle --status ─────────────────────────────────────────────────
    if args.status:
        await _show_status(args.campaign)
        return

    # ── Handle --import-sessions ────────────────────────────────────────
    if args.import_sessions:
        await _import_sessions(args.import_sessions)
        if not args.generate_only and args.niche == "crypto":
            # Import-only mode: if no other action requested, exit
            return

    # ── Handle --generate-only ──────────────────────────────────────────
    if args.generate_only:
        await _generate_only(
            args.campaign,
            args.niche,
            args.count,
            args.style,
            args.language,
            args.spintax,
        )
        return

    # ── Build campaign config and run ───────────────────────────────────
    from outreach.throwaway_engine import ThrowawayEngine, CampaignConfig

    config = CampaignConfig(
        campaign_id=args.campaign,
        niche=args.niche,
        daily_quota=args.quota,
        micro_batch_min=args.batch_min,
        micro_batch_max=args.batch_max,
        proxy_country=args.country,
        message_language=args.language,
        message_style=args.style,
        pre_generate_count=args.count,
        spintax_template=args.spintax,
        admin_chat_id=os.getenv("ADMIN_CHAT_ID", ""),
        bot_token=os.getenv("BOT_TOKEN", ""),
    )

    engine = ThrowawayEngine(config)
    await engine.setup()
    await engine.run()


if __name__ == "__main__":
    asyncio.run(main())
