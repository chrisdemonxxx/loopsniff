#!/usr/bin/env python3
"""
Telegram Bulk Account Creator — Telethon-based.

Usage:
    # Check balance and number availability
    python3 create_accounts.py --check-only

    # Create 5 accounts using US numbers
    python3 create_accounts.py --count 5 --country-id 5 --country us

    # Create accounts with Burundi numbers (cheapest fresh numbers)
    python3 create_accounts.py --count 5 --country-id 197 --country bi

    # Single account test with max 20 number probes
    python3 create_accounts.py --count 1 --country-id 5 --country us --max-probes 20

SMS-Man Country IDs:
    5   = USA ($84.63)
    7   = Indonesia ($22.38)
    14  = India ($80.13)
    197 = Burundi ($29.88)
    313 = Tanzania ($31.25)
    113 = South Africa ($31.25)
    265 = Rwanda ($31.25)

NOTE: Most SMS-Man numbers are recycled (already have TG accounts).
The script automatically screens for fresh numbers (SentCodeTypeSms)
and rejects recycled ones (SentCodeTypeApp). This may require many
probes per successful account.
"""
import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv
from loguru import logger

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.sms_client import SMSManClient
from core.telethon_creator import TelethonAccountCreator


async def check_status(sms: SMSManClient):
    """Check SMS-Man balance and number availability."""
    bal = await sms.get_balance()
    logger.info("SMS-Man Balance: ${:.2f}", bal)

    # Check countries for Telegram (with correct SMS-Man country_ids)
    countries = [
        ("5", "US", "USA"),
        ("7", "ID", "Indonesia"),
        ("14", "IN", "India"),
        ("197", "BI", "Burundi"),
        ("113", "ZA", "South Africa"),
        ("313", "TZ", "Tanzania"),
        ("265", "RW", "Rwanda"),
        ("105", "EG", "Egypt"),
    ]
    for cid, code, name in countries:
        try:
            data = await sms._request("get-prices", {
                "country_id": cid,
                "application_id": "3",
            })
            if isinstance(data, dict) and "3" in data:
                info = data["3"]
                cost = float(info.get("cost", 0))
                count = info.get("count", 0)
                logger.info("  {} ({}): ${:.2f}/number, {} available", name, code, cost, count)
        except Exception as e:
            logger.warning("  {} ({}): error - {}", name, code, e)

    return bal


async def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="Telegram Bulk Account Creator (Telethon)")
    parser.add_argument("--count", type=int, default=5, help="Number of accounts to create")
    parser.add_argument("--country", default="us", help="Country code (default: us)")
    parser.add_argument("--country-id", default="5", help="SMS-Man country_id (default: 5 = USA)")
    parser.add_argument("--delay", type=int, default=30, help="Delay between accounts in seconds")
    parser.add_argument("--sms-timeout", type=int, default=300, help="SMS wait timeout in seconds")
    parser.add_argument("--max-probes", type=int, default=10, help="Max numbers to try per account")
    parser.add_argument("--check-only", action="store_true", help="Only check balance/availability")
    parser.add_argument("--output", default="account_results.jsonl", help="Results output file")
    args = parser.parse_args()

    # Configure logging
    logger.remove()
    logger.add(sys.stderr, level="INFO",
               format="<green>{time:HH:mm:ss}</green> | <level>{level:7s}</level> | <level>{message}</level>")

    # Load config
    sms_key = os.getenv("SMS_MAN_API_KEY")
    api_id = int(os.getenv("TELEGRAM_API_ID", "2040"))
    api_hash = os.getenv("TELEGRAM_API_HASH", "b18441a1ff607e10a989891a5462e627")

    if not sms_key:
        logger.error("SMS_MAN_API_KEY not set in .env")
        sys.exit(1)

    sms = SMSManClient(sms_key)

    try:
        if args.check_only:
            await check_status(sms)
            return

        # Check balance first
        bal = await check_status(sms)

        # Create accounts
        creator = TelethonAccountCreator(
            api_id=api_id,
            api_hash=api_hash,
            sms_client=sms,
            sessions_dir=os.path.join(os.path.dirname(__file__), "sessions"),
        )

        logger.info("Starting batch creation: {} accounts, country={} (id={})",
                     args.count, args.country, args.country_id)

        results = await creator.create_batch(
            count=args.count,
            country=args.country,
            country_id=args.country_id,
            delay_between=args.delay,
            sms_timeout=args.sms_timeout,
            max_probes_per_account=args.max_probes,
        )

        # Save results
        output_file = os.path.join(os.path.dirname(__file__), args.output)
        with open(output_file, "a") as f:
            for r in results:
                # Don't log string_session to file (keep it secure)
                r_safe = {k: v for k, v in r.items() if k != "string_session"}
                f.write(json.dumps(r_safe) + "\n")

        # Summary
        successes = [r for r in results if r["status"] == "success"]
        failures = [r for r in results if r["status"] != "success"]

        logger.info("═══ SUMMARY ═══")
        logger.info("Total: {} | Success: {} | Failed: {}", len(results), len(successes), len(failures))

        if successes:
            logger.info("Created accounts:")
            for r in successes:
                logger.info("  ✓ {} (id={}, session={})",
                            r.get("phone"), r.get("user_id"), r.get("session_file"))

        if failures:
            logger.info("Failed attempts:")
            for r in failures:
                logger.info("  ✗ {} - {}", r.get("phone", "?"), r.get("error", "unknown"))

        # Save string sessions separately (secure backup)
        sessions_backup = os.path.join(os.path.dirname(__file__), "sessions", "string_sessions.json")
        existing = {}
        if os.path.exists(sessions_backup):
            with open(sessions_backup) as f:
                existing = json.load(f)

        for r in successes:
            if "string_session" in r:
                existing[r["phone"]] = {
                    "string_session": r["string_session"],
                    "user_id": r.get("user_id"),
                    "created_at": r.get("timestamp"),
                }

        with open(sessions_backup, "w") as f:
            json.dump(existing, f, indent=2)

        logger.info("Results saved to: {}", output_file)
        logger.info("Sessions saved to: {}", os.path.join(os.path.dirname(__file__), "sessions"))

    finally:
        await sms.close()


if __name__ == "__main__":
    asyncio.run(main())
