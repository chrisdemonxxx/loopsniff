#!/usr/bin/env python3
"""Auto warmup runner for all connected TG accounts.

Runs the 14-day warming schedule for all accounts that haven't completed
their full warming cycle yet. Designed to be called daily by systemd timer.

Usage:
    python run_warmup.py              # warm all accounts
    python run_warmup.py --dry-run    # show what would be warmed
"""

import asyncio
import logging
import sys
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("warmup-runner")


async def main(dry_run: bool = False) -> None:
    from outreach import db, config
    from outreach.warming_engine import WarmingEngine

    await db.init_db()
    engine = WarmingEngine()

    # Get ALL accounts (not just 'warming' status)
    all_accounts = await db.get_accounts()
    log.info("Total accounts in DB: %d", len(all_accounts))

    # Determine which accounts need warming
    to_warm = []
    already_done = []
    for acct in all_accounts:
        last_day = await db.get_warming_day(acct.phone)
        if last_day >= config.WARMING_DAYS:
            already_done.append((acct.phone, last_day))
        else:
            # Check for REAL activity (not zero-activity placeholder entries)
            import aiosqlite
            async with aiosqlite.connect(str(config.DB_PATH)) as conn:
                cur = await conn.execute(
                    """SELECT COALESCE(MAX(day), 0) FROM warming_log
                       WHERE phone = ? AND (groups_joined > 0 OR messages_sent > 0
                             OR channels_read > 0 OR reactions > 0)""",
                    (acct.phone,),
                )
                row = await cur.fetchone()
                real_day = row[0] if row and row[0] else 0
            to_warm.append((acct, real_day))

    log.info("Already fully warmed: %d", len(already_done))
    log.info("Need warming: %d", len(to_warm))

    if dry_run:
        for acct, real_day in to_warm:
            next_day = real_day + 1
            plan = engine._get_plan(next_day)
            log.info(
                "  [DRY RUN] %s: real_day=%d, next=%d, plan=join=%d msg=%d read=%d react=%d",
                acct.phone, real_day, next_day, *plan,
            )
        return

    if not to_warm:
        log.info("All accounts fully warmed. Nothing to do.")
        return

    results = []
    for acct, real_day in to_warm:
        next_day = real_day + 1
        if next_day > config.WARMING_DAYS:
            log.info("Account %s completed warming (day %d)", acct.phone, real_day)
            continue

        try:
            log.info("=== Warming %s: day %d/%d ===", acct.phone, next_day, config.WARMING_DAYS)
            result = await engine.warm_account(acct.phone, next_day)
            results.append(result)
            total_activity = (
                result.get("groups_joined", 0)
                + result.get("messages_sent", 0)
                + result.get("channels_read", 0)
                + result.get("reactions", 0)
            )
            log.info(
                "  ✓ %s day %d: %d total activities (groups=%d msgs=%d reads=%d reacts=%d)",
                acct.phone,
                next_day,
                total_activity,
                result.get("groups_joined", 0),
                result.get("messages_sent", 0),
                result.get("channels_read", 0),
                result.get("reactions", 0),
            )
        except Exception as exc:
            log.error("  ✗ %s day %d FAILED: %s", acct.phone, next_day, exc)
            results.append({"phone": acct.phone, "day": next_day, "error": str(exc)})

        # Stagger between accounts (30-90s) to avoid rate limits
        import random
        delay = random.uniform(30, 90)
        log.info("  Sleeping %.0fs before next account...", delay)
        await asyncio.sleep(delay)

    # Summary
    succeeded = [r for r in results if "error" not in r]
    failed = [r for r in results if "error" in r]
    log.info("=" * 60)
    log.info("WARMUP COMPLETE: %d succeeded, %d failed out of %d", len(succeeded), len(failed), len(results))
    for f in failed:
        log.error("  FAILED: %s day %d — %s", f["phone"], f["day"], f["error"])


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    asyncio.run(main(dry_run=dry_run))
