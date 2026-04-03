"""Pre-launch campaign setup — run this ONCE before starting a campaign."""

import asyncio
import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from outreach.session_pool import SessionPool
from outreach.message_engine import MessageEngine
from outreach.anti_ban import ApiIdPool
from loguru import logger


async def setup_campaign(campaign_id: str, niche: str):
    """Full pre-launch setup."""

    logger.info("=" * 60)
    logger.info(f"Setting up campaign: {campaign_id}")
    logger.info("=" * 60)

    # Step 1: Import sessions into pool
    logger.info("\n📱 Step 1: Importing sessions into pool...")
    pool = SessionPool(
        sessions_dir="outreach/sessions/telethon",
        profiles_path="outreach/data/device_profiles.json",
    )
    await pool.init_db()
    import_result = await pool.import_sessions()
    logger.info(f"Import result: {import_result}")

    # Step 2: Show pool stats
    stats = await pool.get_stats()
    logger.info(f"Pool stats: {stats}")

    # Step 3: Initialize API ID pool
    logger.info("\n🔑 Step 3: Initializing API ID pool...")
    api_pool = ApiIdPool()
    api_pool.add(2040, "b18441a1ff607e10a989891a5462e627")
    api_pool.add(6, "eb06d4abfb49dc3eeb1aeb98ae0f581e")
    api_pool.add(10840, "33c45224029d59cb3ad0c16134215aeb")
    api_pool.add(21724, "3e0cb5efcd52300aec5994fdfc5bdc16")
    logger.info(f"API ID pool: {len(api_pool.pool)} entries loaded")

    # Step 4: Pre-generate messages (Spintax first, then LLM)
    logger.info("\n✉️ Step 4: Pre-generating messages...")
    engine = MessageEngine()
    await engine.init_db()

    # Load spintax templates
    templates_path = "outreach/data/spintax_templates.txt"
    if os.path.exists(templates_path):
        with open(templates_path) as f:
            content = f.read()

        templates = [t.strip() for t in content.split("---TEMPLATE---") if t.strip()]
        logger.info(f"Loaded {len(templates)} Spintax templates")

        # Generate from each template
        total_generated = 0
        for i, template in enumerate(templates):
            logger.info(f"  Generating from template {i+1}/{len(templates)}...")
            result = await engine.pre_generate_spintax_batch(
                campaign_id=campaign_id,
                template=template,
                count=20,  # 20 per template = 100 total from spintax
            )
            total_generated += result.get("generated", 0)
            logger.info(f"  Template {i+1}: {result}")

        logger.info(f"Total Spintax messages: {total_generated}")
    else:
        logger.warning(f"No spintax templates at {templates_path}")

    # Step 5: Show final stats
    pool_stats = await engine.get_pool_stats(campaign_id)
    logger.info(f"\n📊 Message pool stats: {pool_stats}")

    # Show pool breakdown
    stats = await pool.get_stats()
    logger.info(f"\n📱 Session pool: {stats}")

    logger.info("\n" + "=" * 60)
    logger.info("✅ Campaign setup complete!")
    logger.info(f"Run: python run_throwaway.py --campaign {campaign_id} --niche {niche}")
    logger.info("=" * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Pre-launch campaign setup")
    parser.add_argument("--campaign", default="adflux-launch-1", help="Campaign ID")
    parser.add_argument("--niche", default="ad-accounts", help="Campaign niche")
    args = parser.parse_args()

    asyncio.run(setup_campaign(args.campaign, args.niche))
