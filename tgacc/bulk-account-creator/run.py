#!/usr/bin/env python3
"""
Telegram Account Creator CLI
Usage:
    # Interactive mode (prompts for proxy/SMS)
    python run.py create --country us

    # Fully automated (all params pre-supplied)
    python run.py create --country us --proxy host:port:user:pass --phone +1234567890 --code 12345

    # Batch from JSON file
    python run.py batch --file accounts.json --concurrency 3

    # List existing Roxy profiles
    python run.py profiles

    # Check SMS balance
    python run.py balance
"""
import argparse
import asyncio
import json
import os
import sys

from dotenv import load_dotenv
from loguru import logger

# Ensure package root is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.orchestrator import AccountCreator


def build_creator() -> AccountCreator:
    load_dotenv()
    return AccountCreator(
        roxy_api_key=os.getenv("ROXY_API_KEY", ""),
        roxy_api_host=os.getenv("ROXY_API_HOST", "http://127.0.0.1:50000"),
        proxy_api_key=os.getenv("PROXY_SELLER_KEY", ""),
        sms_api_key=os.getenv("SMS_MAN_API_KEY", ""),
    )


# ── Commands ─────────────────────────────────────────────────────────────────


async def cmd_create(args):
    creator = build_creator()
    try:
        if args.phone and args.code:
            # Fully automated
            result = await creator.create_account_auto(
                country=args.country,
                proxy_str=args.proxy,
                phone=args.phone,
                code=args.code,
                first_name=args.name or "User",
            )
        else:
            # Interactive
            result = await creator.create_account_interactive(
                country=args.country,
                proxy_str=args.proxy,
            )

        print(json.dumps(result, indent=2))

        # Append to results log
        _append_result(result)
    finally:
        await creator.close()


async def cmd_batch(args):
    creator = build_creator()
    try:
        with open(args.file) as f:
            accounts = json.load(f)

        logger.info("Batch creating {} accounts (concurrency={})", len(accounts), args.concurrency)
        results = await creator.create_batch(accounts, concurrency=args.concurrency)

        outfile = args.output or "batch_results.json"
        with open(outfile, "w") as f:
            json.dump(results, f, indent=2)

        ok = sum(1 for r in results if r.get("status") == "success")
        logger.info("Done: {}/{} succeeded → {}", ok, len(results), outfile)
    finally:
        await creator.close()


async def cmd_profiles(args):
    creator = build_creator()
    try:
        profiles = await creator.list_profiles()
        if not profiles:
            print("No profiles found.")
            return
        for p in profiles:
            pid = p.get("id", "?")
            name = p.get("name", "")
            status = p.get("status", "")
            print(f"  {pid}  {name}  [{status}]")
    finally:
        await creator.close()


async def cmd_balance(args):
    creator = build_creator()
    try:
        balances = await creator.check_balance()
        for svc, bal in balances.items():
            print(f"  {svc}: {bal}")
    finally:
        await creator.close()


async def cmd_proxy(args):
    creator = build_creator()
    try:
        if not creator.proxy_client:
            print("Error: PROXY_SELLER_KEY not set in .env")
            return

        if args.action == "list":
            proxies = await creator.proxy_client.get_proxy_list()
            if not proxies:
                print("No proxies. Order via: python run.py proxy order --country us")
                return
            for p in proxies:
                s = f"  {p.get('ip')}:{p.get('port_http')} [{p.get('country')}] "
                s += f"login={p.get('login')} status={p.get('status')}"
                print(s)
            print(f"\nTotal: {len(proxies)}")

        elif args.action == "order":
            country = args.country or "us"
            period = args.period or "1w"
            qty = args.quantity or 1
            logger.info("Ordering {} ipv4 proxy(s) for {} (period={})…", qty, country, period)
            cid = await creator.proxy_client.find_country_id("ipv4", country)
            if not cid:
                print(f"Error: Country '{country}' not found for ipv4 proxies")
                return
            result = await creator.proxy_client.order_make(
                country_id=cid, period_id=period, quantity=qty, proxy_type="ipv4",
            )
            print(json.dumps(result, indent=2))

        elif args.action == "balance":
            bal = await creator.proxy_client.get_balance()
            print(f"Proxy-Seller balance: ${bal}")
    finally:
        await creator.close()


# ── Helpers ──────────────────────────────────────────────────────────────────


def _append_result(result: dict):
    """Append a result to the results log file."""
    logfile = "results.jsonl"
    with open(logfile, "a") as f:
        f.write(json.dumps(result) + "\n")


# ── Arg parsing ──────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Telegram Account Creator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # create
    p_create = sub.add_parser("create", help="Create a single Telegram account")
    p_create.add_argument("--country", default="us", help="Country code (default: us)")
    p_create.add_argument("--proxy", help="Proxy as host:port:user:pass")
    p_create.add_argument("--phone", help="Phone number (skip SMS prompt)")
    p_create.add_argument("--code", help="Verification code (skip code prompt)")
    p_create.add_argument("--name", help="First name for new account (default: User)")

    # batch
    p_batch = sub.add_parser("batch", help="Batch create from JSON file")
    p_batch.add_argument("--file", required=True, help="JSON file with account list")
    p_batch.add_argument("--concurrency", type=int, default=3, help="Max concurrent (default: 3)")
    p_batch.add_argument("--output", help="Output results file (default: batch_results.json)")

    # profiles
    sub.add_parser("profiles", help="List Roxy Browser profiles")

    # balance
    sub.add_parser("balance", help="Check SMS & proxy service balances")

    # proxy
    p_proxy = sub.add_parser("proxy", help="Manage Proxy-Seller proxies")
    p_proxy.add_argument("action", choices=["list", "order", "balance"], help="Action to perform")
    p_proxy.add_argument("--country", default="us", help="Country code (default: us)")
    p_proxy.add_argument("--period", default="1w", help="Rental period: 1w, 2w, 1m, etc. (default: 1w)")
    p_proxy.add_argument("--quantity", type=int, default=1, help="Number of proxies (default: 1)")

    args = parser.parse_args()

    # Configure logging
    logger.remove()
    logger.add(sys.stderr, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{message}</level>")

    # Dispatch
    coro = {
        "create": cmd_create,
        "batch": cmd_batch,
        "profiles": cmd_profiles,
        "balance": cmd_balance,
        "proxy": cmd_proxy,
    }[args.command]

    asyncio.run(coro(args))


if __name__ == "__main__":
    main()
