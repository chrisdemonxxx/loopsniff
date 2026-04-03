#!/usr/bin/env python3
"""CLI entry point for the Telegram outreach engine.

Usage (from bulk-account-creator/):
    python -m outreach.run --help
    python -m outreach.run sessions --list
    python -m outreach.run leads --load-all
    python -m outreach.run outreach --start
    python -m outreach.run stats
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys

# ── logging setup ───────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("outreach")


# ── async wrappers ──────────────────────────────────────────────────────────

async def _init() -> None:
    """Ensure the database schema exists."""
    from .db import init_db
    await init_db()


# ── sessions ────────────────────────────────────────────────────────────────

async def cmd_sessions(args: argparse.Namespace) -> None:
    from .session_manager import SessionManager
    sm = SessionManager()

    if args.create:
        if not args.phone:
            log.error("--phone is required for --create")
            return
        path = await sm.create_session(args.phone)
        print(f"Session created: {path}")
    elif args.validate:
        from . import db
        accounts = await db.get_accounts()
        for acct in accounts:
            ok = await sm.validate_session(acct.phone)
            print(f"  {acct.phone}: {'✅ valid' if ok else '❌ invalid'}")
    elif args.export_browser:
        await sm.export_sessions_from_browser()
    else:
        # Default: list
        sessions = await sm.list_sessions()
        if not sessions:
            print("No sessions found.")
        for s in sessions:
            print(f"  {s['phone']:16s}  status={s['status']:10s}  "
                  f"dms_today={s['dms_today']}  total={s['total_dms']}  "
                  f"file_exists={s['session_exists']}")


# ── warming ─────────────────────────────────────────────────────────────────

async def cmd_warm(args: argparse.Namespace) -> None:
    from .warming_engine import WarmingEngine
    engine = WarmingEngine()

    if args.phone:
        from . import db as _db
        day = await _db.get_warming_day(args.phone)
        result = await engine.warm_account(args.phone, day + 1)
        print(json.dumps(result, indent=2))
    else:
        results = await engine.run_daily_warming()
        promoted = await engine.check_warming_complete()
        print(f"Warming done for {len(results)} account(s).")
        if promoted:
            print(f"Promoted to 'ready': {promoted}")
        for r in results:
            print(f"  {r}")


# ── leads ───────────────────────────────────────────────────────────────────

async def cmd_leads(args: argparse.Namespace) -> None:
    from .lead_loader import LeadLoader
    loader = LeadLoader()

    if args.load_all:
        count = await loader.load_all()
        print(f"Loaded {count} leads from all sources.")
    elif args.load_bhw:
        count = await loader.load_bhw()
        print(f"Loaded {count} BHW leads.")
    elif args.load_aw:
        count = await loader.load_aw()
        print(f"Loaded {count} AW leads.")
    elif args.load_hackforums:
        count = await loader.load_hackforums()
        print(f"Loaded {count} HackForums leads.")
    elif args.load_exploit:
        count = await loader.load_exploit()
        print(f"Loaded {count} Exploit leads.")
    elif args.validate:
        result = await loader.validate_leads()
        print(json.dumps(result, indent=2))
    else:
        stats = await loader.get_stats()
        print(json.dumps(stats, indent=2))


# ── outreach ────────────────────────────────────────────────────────────────

async def cmd_outreach(args: argparse.Namespace) -> None:
    from .dispatcher import OutreachDispatcher
    dispatcher = OutreachDispatcher()

    if args.start:
        print("Starting outreach cycle…")
        result = await dispatcher.run_outreach_cycle()
        print(json.dumps(result, indent=2))
    elif args.status:
        from . import db as _db
        stats = await _db.get_daily_stats()
        print(json.dumps(stats, indent=2))
    elif args.pause:
        print("Outreach paused (set all active accounts to resting).")
        from . import db as _db
        accounts = await _db.get_accounts(status="active")
        for a in accounts:
            await _db.update_account(a.phone, status="resting")
        print(f"Paused {len(accounts)} account(s).")
    else:
        log.error("Specify --start, --status, or --pause")


# ── follow-ups ──────────────────────────────────────────────────────────────

async def cmd_followup(args: argparse.Namespace) -> None:
    from .followup_scheduler import FollowupScheduler
    scheduler = FollowupScheduler()

    if args.send:
        result = await scheduler.send_followups()
        print(json.dumps(result, indent=2))
    else:
        due = await scheduler.check_followups_due()
        if not due:
            print("No follow-ups due.")
        for item in due:
            print(f"  @{item['lead'].username}  attempt={item['attempt']}  "
                  f"template={item['template_id']}")


# ── monitor ─────────────────────────────────────────────────────────────────

async def cmd_monitor(args: argparse.Namespace) -> None:
    from .account_monitor import AccountMonitor
    monitor = AccountMonitor()

    if args.health:
        results = await monitor.check_all_accounts()
        for r in results:
            emoji = "✅" if r["current_status"] not in ("banned",) else "🚫"
            print(f"  {emoji} {r['phone']:16s}  {r['current_status']:10s}  {r['detail']}")
    elif args.report:
        report = await monitor.daily_report()
        print(report)
    else:
        report = await monitor.daily_report()
        print(report)


# ── bot probe ───────────────────────────────────────────────────────────────

async def cmd_probe(args: argparse.Namespace) -> None:
    from .bot_probe import BotProbe
    prober = BotProbe()
    result = await prober.probe_bot(
        args.bot.lstrip("@"),
        depth=args.depth,
    )
    print(json.dumps(result, indent=2, default=str, ensure_ascii=False))


# ── stats ───────────────────────────────────────────────────────────────────

async def cmd_stats(_args: argparse.Namespace) -> None:
    from . import db as _db
    stats = await _db.get_daily_stats()
    from .lead_loader import LeadLoader
    lead_stats = await LeadLoader().get_stats()
    print("═══════════════════════════════════════")
    print("        OUTREACH DASHBOARD")
    print("═══════════════════════════════════════")
    print()
    print("📨 Today")
    print(f"  DMs sent:        {stats['dms_sent_today']}")
    print(f"  Replies:         {stats['replies_today']}")
    print(f"  Hot leads:       {stats['leads_hot']}")
    print(f"  Qualified:       {stats['leads_qualified']}")
    print()
    print("📊 Totals")
    print(f"  Total leads:     {stats['total_leads']}")
    print(f"  Total accounts:  {stats['total_accounts']}")
    print(f"  Banned:          {stats['accounts_banned']}")
    print()
    print("📁 Leads by source")
    for source, breakdown in lead_stats.items():
        if source.startswith("_"):
            continue
        print(f"  {source}:")
        if isinstance(breakdown, dict):
            for status, cnt in breakdown.items():
                print(f"    {status}: {cnt}")
    print()
    print("═══════════════════════════════════════")


# ── argument parser ─────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="outreach",
        description="Telegram Outreach Engine — DMs, warming, follow-ups",
    )
    sub = parser.add_subparsers(dest="command")

    # sessions
    p = sub.add_parser("sessions", help="Manage Telethon sessions")
    p.add_argument("--create", action="store_true", help="Create a new session")
    p.add_argument("--list", action="store_true", help="List all sessions")
    p.add_argument("--validate", action="store_true", help="Validate all sessions")
    p.add_argument("--export-browser", action="store_true",
                   help="Export sessions from Roxy Browser (stub)")
    p.add_argument("--phone", type=str, help="Phone number (for --create)")

    # warm
    p = sub.add_parser("warm", help="Run account warming")
    p.add_argument("--all", action="store_true", default=True,
                   help="Warm all accounts needing it")
    p.add_argument("--phone", type=str, help="Warm a specific account")

    # leads
    p = sub.add_parser("leads", help="Load and manage leads")
    p.add_argument("--load-all", action="store_true", help="Load from all sources")
    p.add_argument("--load-bhw", action="store_true", help="Load BHW leads")
    p.add_argument("--load-aw", action="store_true", help="Load AW leads")
    p.add_argument("--load-hackforums", action="store_true",
                   help="Load HackForums leads")
    p.add_argument("--load-exploit", action="store_true", help="Load exploit leads")
    p.add_argument("--validate", action="store_true",
                   help="Validate lead usernames via TG API")
    p.add_argument("--stats", action="store_true", help="Show lead statistics")

    # outreach
    p = sub.add_parser("outreach", help="Run outreach dispatcher")
    p.add_argument("--start", action="store_true", help="Start outreach cycle")
    p.add_argument("--status", action="store_true", help="Show outreach status")
    p.add_argument("--pause", action="store_true", help="Pause all outreach")

    # followup
    p = sub.add_parser("followup", help="Follow-up management")
    p.add_argument("--check", action="store_true", help="Check due follow-ups")
    p.add_argument("--send", action="store_true", help="Send due follow-ups")

    # monitor
    p = sub.add_parser("monitor", help="Account health monitoring")
    p.add_argument("--health", action="store_true", help="Check all accounts")
    p.add_argument("--report", action="store_true", help="Generate daily report")

    # probe
    p = sub.add_parser("probe", help="Probe a competitor bot")
    p.add_argument("--bot", type=str, required=True, help="Bot username (e.g. @SomeBot)")
    p.add_argument("--depth", type=int, default=3, help="Recursion depth")

    # stats
    sub.add_parser("stats", help="Show overall statistics dashboard")

    return parser


# ── main ────────────────────────────────────────────────────────────────────

HANDLERS = {
    "sessions": cmd_sessions,
    "warm": cmd_warm,
    "leads": cmd_leads,
    "outreach": cmd_outreach,
    "followup": cmd_followup,
    "monitor": cmd_monitor,
    "probe": cmd_probe,
    "stats": cmd_stats,
}


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    handler = HANDLERS.get(args.command)
    if handler is None:
        parser.print_help()
        sys.exit(1)

    async def _run():
        await _init()
        await handler(args)

    asyncio.run(_run())


if __name__ == "__main__":
    main()
