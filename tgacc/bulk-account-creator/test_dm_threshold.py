#!/usr/bin/env python3
"""Test PeerFlood DM threshold per account with longer delays.

Picks 3 active accounts and attempts up to 5 DMs each, using 90-180s
delays between messages. Records exactly how many DMs succeed before
PeerFloodError hits.

Usage:
    python test_dm_threshold.py              # dry-run (resolves usernames only)
    python test_dm_threshold.py --live       # ACTUALLY sends DMs
    python test_dm_threshold.py --accounts 5 # test with 5 accounts
    python test_dm_threshold.py --dms 10     # attempt up to 10 DMs per account
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import random
import sys
import json
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from outreach import config, db
from outreach.models import Lead, Message
from outreach.message_templates import TemplateEngine, SOURCE_FRIENDLY_NAMES
from telethon import TelegramClient
from telethon.tl.functions.contacts import ResolveUsernameRequest
from telethon.errors import (
    FloodWaitError,
    PeerFloodError,
    UserPrivacyRestrictedError,
    ChatWriteForbiddenError,
    UsernameNotOccupiedError,
    UsernameInvalidError,
    InputUserDeactivatedError,
    AuthKeyUnregisteredError,
    UserDeactivatedBanError,
    PhoneNumberBannedError,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("dm_threshold")

SESSIONS_DIR = config.SESSIONS_DIR
DELAY_MIN = 90   # seconds — much longer than daily_outreach's 25s
DELAY_MAX = 180  # seconds
RESULTS_FILE = Path(__file__).resolve().parent / "dm_threshold_results.txt"

tpl = TemplateEngine()


async def resolve_username(client: TelegramClient, username: str) -> bool:
    """Try to resolve a username. Returns True if the user exists."""
    try:
        await client(ResolveUsernameRequest(username))
        return True
    except (UsernameNotOccupiedError, UsernameInvalidError):
        return False
    except FloodWaitError as e:
        log.warning("FloodWait %ds while resolving @%s", e.seconds, username)
        raise
    except Exception as e:
        log.warning("Resolve @%s failed: %s", username, str(e)[:80])
        return False


async def test_account(
    phone: str,
    leads: list[Lead],
    max_dms: int,
    live: bool,
) -> dict:
    """Test one account's DM threshold. Returns results dict."""
    session_path = str(SESSIONS_DIR / phone)
    result = {
        "phone": phone,
        "attempted": 0,
        "sent": 0,
        "resolved": 0,
        "peer_flood_at": None,
        "flood_wait_at": None,
        "errors": [],
        "live": live,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        client = TelegramClient(session_path, config.API_ID, config.API_HASH)
        await client.connect()

        if not await client.is_user_authorized():
            log.error("+%s not authorized — skipping", phone)
            result["errors"].append("not_authorized")
            await client.disconnect()
            return result

        me = await client.get_me()
        log.info("✅ Connected as +%s (user_id=%s)", phone, me.id)

        for i, lead in enumerate(leads[:max_dms]):
            result["attempted"] = i + 1
            dm_num = i + 1

            # Resolve the username first (both modes)
            log.info("[%s] DM #%d — resolving @%s ...", phone, dm_num, lead.username)
            try:
                resolved = await resolve_username(client, lead.username)
            except FloodWaitError as e:
                result["flood_wait_at"] = dm_num
                result["errors"].append(f"flood_wait_{e.seconds}s_at_resolve_{dm_num}")
                log.error("⛔ FloodWait at resolve #%d — stopping", dm_num)
                break

            if not resolved:
                log.info("  @%s — dead/invalid, skipping", lead.username)
                result["errors"].append(f"dead_username_{lead.username}")
                continue

            result["resolved"] += 1
            log.info("  @%s — resolved OK", lead.username)

            if live:
                # Build message
                msgs = await db.get_messages(lead.username)
                outbound = [m for m in msgs if m.direction == "outbound"]
                attempt = len(outbound) + 1
                template_id, lang = tpl.select_template(lead, attempt)
                text = tpl.render(
                    template_id, lang,
                    name=lead.username,
                    source=lead.source,
                    source_friendly=SOURCE_FRIENDLY_NAMES.get(lead.source, "the community"),
                    niche=lead.niche or "",
                )

                try:
                    await client.send_message(lead.username, text)
                    result["sent"] += 1
                    log.info("  ✅ DM #%d SENT to @%s", dm_num, lead.username)

                    # Record to DB
                    now = datetime.now(timezone.utc)
                    await db.add_message(Message(
                        lead_username=lead.username,
                        account_phone=phone,
                        direction="outbound",
                        text=text,
                        sent_at=now,
                        template_id=template_id,
                    ))
                    await db.update_lead(
                        lead.username, status="contacted",
                        contacted_at=now, contacted_by=phone,
                    )

                except PeerFloodError:
                    result["peer_flood_at"] = dm_num
                    log.error("⛔ PeerFlood after %d sent DMs (at DM #%d)", result["sent"], dm_num)
                    await db.update_account(phone, status="resting")
                    break

                except FloodWaitError as e:
                    result["flood_wait_at"] = dm_num
                    result["errors"].append(f"flood_wait_{e.seconds}s_at_dm_{dm_num}")
                    log.error("⛔ FloodWait %ds at DM #%d — stopping", e.seconds, dm_num)
                    break

                except (UserPrivacyRestrictedError, ChatWriteForbiddenError):
                    log.info("  @%s — privacy restricted, skipping", lead.username)
                    result["errors"].append(f"privacy_{lead.username}")
                    continue

                except Exception as e:
                    result["errors"].append(f"dm_error_{dm_num}_{str(e)[:60]}")
                    log.error("  DM #%d error: %s", dm_num, str(e)[:80])
                    continue
            else:
                log.info("  [DRY RUN] Would send DM #%d to @%s", dm_num, lead.username)
                result["sent"] += 1  # count as "would send" in dry run

            # Delay between DMs (skip after the last one)
            if i < len(leads[:max_dms]) - 1:
                delay = random.uniform(DELAY_MIN, DELAY_MAX)
                log.info("  ⏳ Waiting %.0fs before next DM...", delay)
                await asyncio.sleep(delay)

        await client.disconnect()

    except (AuthKeyUnregisteredError, UserDeactivatedBanError, PhoneNumberBannedError) as e:
        log.error("+%s banned/deactivated: %s", phone, e)
        result["errors"].append(f"banned: {e}")
    except Exception as e:
        log.error("+%s crashed: %s", phone, str(e)[:120])
        result["errors"].append(f"crash: {str(e)[:120]}")

    result["finished_at"] = datetime.now(timezone.utc).isoformat()
    return result


async def main(live: bool, num_accounts: int, max_dms: int) -> None:
    await db.init_db()

    mode = "🔴 LIVE" if live else "🟢 DRY RUN"
    log.info("=" * 60)
    log.info("DM THRESHOLD TEST — %s", mode)
    log.info("Accounts: %d | Max DMs/account: %d | Delay: %d-%ds",
             num_accounts, max_dms, DELAY_MIN, DELAY_MAX)
    log.info("=" * 60)

    all_accounts = await db.get_accounts()
    active = [a for a in all_accounts if a.status in ("active", "ready")]
    random.shuffle(active)
    test_accounts = active[:num_accounts]

    if len(test_accounts) < num_accounts:
        log.warning("Only %d active accounts available (requested %d)",
                     len(test_accounts), num_accounts)

    if not test_accounts:
        log.error("No active accounts — aborting")
        return

    leads = await db.get_leads(status="new")
    random.shuffle(leads)

    if len(leads) < num_accounts * max_dms:
        log.warning("Only %d leads available (need %d)",
                     len(leads), num_accounts * max_dms)

    log.info("Test accounts: %s", [a.phone for a in test_accounts])

    results = []
    lead_offset = 0

    for acct in test_accounts:
        batch = leads[lead_offset:lead_offset + max_dms]
        lead_offset += max_dms

        if not batch:
            log.warning("No more leads — stopping early")
            break

        log.info("\n" + "─" * 50)
        log.info("TESTING +%s (%d leads assigned)", acct.phone, len(batch))
        log.info("─" * 50)

        result = await test_account(acct.phone, batch, max_dms, live)
        results.append(result)

        log.info("Result for +%s: sent=%d, peer_flood_at=%s",
                 acct.phone, result["sent"], result["peer_flood_at"])

        # Stagger between accounts
        if acct != test_accounts[-1]:
            stagger = random.uniform(10, 30)
            log.info("⏳ Stagger %.0fs before next account...", stagger)
            await asyncio.sleep(stagger)

    # Write results
    report = {
        "test_run": datetime.now(timezone.utc).isoformat(),
        "mode": "live" if live else "dry_run",
        "config": {
            "num_accounts": num_accounts,
            "max_dms_per_account": max_dms,
            "delay_range_seconds": [DELAY_MIN, DELAY_MAX],
        },
        "results": results,
        "summary": {
            "accounts_tested": len(results),
            "total_sent": sum(r["sent"] for r in results),
            "peer_flooded": [r["phone"] for r in results if r["peer_flood_at"]],
            "avg_dms_before_flood": None,
        },
    }

    flooded = [r for r in results if r["peer_flood_at"] is not None]
    if flooded:
        report["summary"]["avg_dms_before_flood"] = (
            sum(r["sent"] for r in flooded) / len(flooded)
        )

    RESULTS_FILE.write_text(json.dumps(report, indent=2))
    log.info("\n" + "=" * 60)
    log.info("RESULTS SAVED → %s", RESULTS_FILE)
    log.info("=" * 60)

    # Print summary
    print(f"\n{'=' * 50}")
    print(f"  DM THRESHOLD TEST SUMMARY ({mode})")
    print(f"{'=' * 50}")
    for r in results:
        pf = f"PeerFlood at DM #{r['peer_flood_at']}" if r["peer_flood_at"] else "No PeerFlood"
        print(f"  +{r['phone']}: {r['sent']}/{r['attempted']} sent — {pf}")
    print(f"{'=' * 50}")
    if flooded:
        print(f"  ⚠️  Avg DMs before PeerFlood: {report['summary']['avg_dms_before_flood']:.1f}")
    else:
        print(f"  ✅ No PeerFlood hit! Safe to increase DMS_PER_ACCOUNT.")
    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test PeerFlood DM threshold")
    parser.add_argument("--live", action="store_true",
                        help="Actually send DMs (default: dry run, resolve only)")
    parser.add_argument("--accounts", type=int, default=3,
                        help="Number of accounts to test (default: 3)")
    parser.add_argument("--dms", type=int, default=5,
                        help="Max DMs per account (default: 5)")
    args = parser.parse_args()

    if args.live:
        print("\n⚠️  LIVE MODE — This will send real DMs!")
        print("Press Ctrl+C within 5 seconds to abort...\n")
        try:
            import time
            time.sleep(5)
        except KeyboardInterrupt:
            print("Aborted.")
            sys.exit(0)

    asyncio.run(main(live=args.live, num_accounts=args.accounts, max_dms=args.dms))
