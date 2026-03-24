#!/usr/bin/env python3
"""CLI entry point for the CRM sync module.

Usage:
    python -m outreach.crm.run_crm {setup,sync,watch}

Commands:
    setup  — Create/configure Google Sheet + Notion database properties
    sync   — One-time sync from outreach DB to Sheets + Notion
    watch  — Continuous sync every 5 minutes
"""

from __future__ import annotations

import argparse
import sys

from .sync_manager import CRMSync


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AdFlux CRM — sync outreach leads to Sheets & Notion",
    )
    parser.add_argument(
        "command",
        choices=["setup", "sync", "watch"],
        help="setup | sync | watch",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=300,
        help="Sync interval in seconds for 'watch' mode (default: 300)",
    )
    args = parser.parse_args()

    crm = CRMSync()

    if args.command == "setup":
        crm.setup()
    elif args.command == "sync":
        crm.sync_from_db()
    elif args.command == "watch":
        crm.run_continuous(interval=args.interval)


if __name__ == "__main__":
    main()
