#!/usr/bin/env python3
"""Daily automated outreach — runs all active accounts, 1-2 DMs each.

Designed to run via cron once or twice per day. Handles PeerFlood
gracefully by marking accounts as resting and moving to the next.
Sends a summary report to admin bot when done.

Usage:
    python daily_outreach.py              # normal run
    python daily_outreach.py --dry-run    # preview what would happen
    python daily_outreach.py --limit 5    # limit accounts used
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

import aiohttp

sys.path.insert(0, str(Path(__file__).resolve().parent))

from outreach import config
from outreach import db
from outreach.models import Lead, Account, Message
from outreach.message_templates import TemplateEngine, SOURCE_FRIENDLY_NAMES
from telethon import TelegramClient
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
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("daily_outreach")

SESSIONS_DIR = config.SESSIONS_DIR
DMS_PER_ACCOUNT = 2
DELAY_MIN = 25
DELAY_MAX = 90
STAGGER_MIN = 3
STAGGER_MAX = 10

tpl = TemplateEngine()


async def send_dm(client: TelegramClient, acct_phone: str, lead: Lead) -> str:
    """Send a single DM. Returns status string."""
    msgs = await db.get_messages(lead.username)
    outbound = [m for m in msgs if m.direction == "outbound"]
    attempt = len(outbound) + 1

    template_id, lang = tpl.select_template(lead, attempt)
    text = tpl.render(
        template_id,
        lang,
        name=lead.username,
        source=lead.source,
        source_friendly=SOURCE_FRIENDLY_NAMES.get(lead.source, "the community"),
        niche=lead.niche or "",
    )

    try:
        await client.send_message(lead.username, text)
    except FloodWaitError as e:
        log.warning("FloodWait %ds on %s", e.seconds, acct_phone)
        return "flood"
    except PeerFloodError:
        log.warning("PeerFlood on %s — marking resting", acct_phone)
        await db.update_account(acct_phone, status="resting")
        return "peer_flood"
    except (UserPrivacyRestrictedError, ChatWriteForbiddenError):
        log.info("@%s privacy-restricted — marking blocked", lead.username)
        await db.update_lead(lead.username, status="blocked")
        return "blocked"
    except (UsernameNotOccupiedError, UsernameInvalidError, InputUserDeactivatedError):
        log.info("@%s dead/invalid — marking dead", lead.username)
        await db.update_lead(lead.username, status="dead")
        return "dead"
    except Exception as exc:
        log.error("DM @%s via %s failed: %s", lead.username, acct_phone, str(exc)[:120])
        return "error"

    now = datetime.now(timezone.utc)
    await db.add_message(
        Message(
            lead_username=lead.username,
            account_phone=acct_phone,
            direction="outbound",
            text=text,
            sent_at=now,
            template_id=template_id,
        )
    )
    await db.update_lead(
        lead.username,
        status="contacted",
        contacted_at=now,
        contacted_by=acct_phone,
    )
    await db.update_account(
        acct_phone,
        dms_sent_today=attempt,
        total_dms_sent=attempt,
        last_used=now,
    )
    log.info("✅ DM #%d → @%s via +%s", attempt, lead.username, acct_phone)
    return "sent"


async def run_account(acct: Account, leads: list[Lead]) -> dict:
    """Run one account's DM batch. Sequential: connect → send → disconnect."""
    session_path = str(SESSIONS_DIR / acct.phone)
    result = {"phone": acct.phone, "sent": 0, "blocked": 0, "dead": 0,
              "errors": 0, "peer_flood": False}

    try:
        client = TelegramClient(session_path, config.API_ID, config.API_HASH)
        await client.connect()

        if not await client.is_user_authorized():
            log.warning("+%s not authorized — skipping", acct.phone)
            await db.update_account(acct.phone, status="unauthorized")
            result["errors"] = 1
            await client.disconnect()
            return result

        for lead in leads:
            status = await send_dm(client, acct.phone, lead)

            if status == "sent":
                result["sent"] += 1
            elif status in ("flood", "peer_flood"):
                result["peer_flood"] = True
                break
            elif status == "blocked":
                result["blocked"] += 1
            elif status == "dead":
                result["dead"] += 1
            else:
                result["errors"] += 1

            # Random delay between DMs
            delay = random.uniform(DELAY_MIN, DELAY_MAX)
            await asyncio.sleep(delay)

        await client.disconnect()

    except (AuthKeyUnregisteredError, UserDeactivatedBanError, PhoneNumberBannedError) as e:
        log.error("+%s banned/deactivated: %s", acct.phone, e)
        await db.update_account(acct.phone, status="banned")
        result["errors"] = 1
    except Exception as e:
        log.error("+%s crashed: %s", acct.phone, str(e)[:120])
        result["errors"] = 1

    return result


async def send_admin_report(results: list[dict], total_leads_left: int) -> None:
    """Send daily summary to admin bot."""
    total_sent = sum(r["sent"] for r in results)
    total_blocked = sum(r["blocked"] for r in results)
    total_dead = sum(r["dead"] for r in results)
    total_errors = sum(r["errors"] for r in results)
    peer_flooded = sum(1 for r in results if r["peer_flood"])
    active_accts = sum(1 for r in results if r["sent"] > 0)

    text = (
        f"📊 DAILY OUTREACH REPORT\n"
        f"{'─' * 30}\n"
        f"✅ DMs sent: {total_sent}\n"
        f"🚫 Blocked (privacy): {total_blocked}\n"
        f"💀 Dead usernames: {total_dead}\n"
        f"⚠️ PeerFlooded accts: {peer_flooded}/{len(results)}\n"
        f"❌ Errors: {total_errors}\n"
        f"{'─' * 30}\n"
        f"📱 Active senders: {active_accts}\n"
        f"📋 Leads remaining: {total_leads_left}\n"
        f"🕐 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
    )

    url = f"https://api.telegram.org/bot{config.ADMIN_BOT_TOKEN}/sendMessage"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json={"chat_id": config.ADMIN_CHAT_ID, "text": text},
                                    timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    log.info("Admin report sent to TG")
                else:
                    log.warning("Admin report failed: HTTP %s", resp.status)
    except Exception as e:
        log.warning("Admin report error: %s", e)


async def main(dry_run: bool = False, limit: int | None = None) -> None:
    await db.init_db()

    # Reset daily DM counters
    await db.reset_daily_dm_counts()

    # Un-rest accounts peer-flooded from previous run
    all_accounts = await db.get_accounts()
    for a in all_accounts:
        if a.status == "resting":
            await db.update_account(a.phone, status="active")

    # Get active accounts (status = 'active' or 'ready')
    active = [a for a in all_accounts if a.status in ("active", "ready")]
    random.shuffle(active)
    if limit:
        active = active[:limit]
    log.info("Active accounts: %d", len(active))

    # Get new leads
    leads = await db.get_leads(status="new")
    log.info("New leads available: %d", len(leads))

    if not leads or not active:
        log.info("Nothing to do — %d accounts, %d leads", len(active), len(leads))
        return

    random.shuffle(leads)

    total_needed = len(active) * DMS_PER_ACCOUNT
    target_leads = leads[:total_needed]

    if dry_run:
        print(f"\n  DRY RUN: {len(target_leads)} DMs via {len(active)} accounts")
        print(f"  First 5 leads: {[l.username for l in target_leads[:5]]}")
        print(f"  First 5 accounts: {[a.phone for a in active[:5]]}\n")
        return

    log.info("Starting outreach: %d accounts × %d DMs/acct = %d max DMs",
             len(active), DMS_PER_ACCOUNT, total_needed)

    results = []
    lead_idx = 0
    for acct in active:
        batch = target_leads[lead_idx:lead_idx + DMS_PER_ACCOUNT]
        if not batch:
            break
        lead_idx += DMS_PER_ACCOUNT

        result = await run_account(acct, batch)
        results.append(result)

        # Stagger between account launches
        stagger = random.uniform(STAGGER_MIN, STAGGER_MAX)
        await asyncio.sleep(stagger)

    # Send report
    remaining = await db.get_leads(status="new")
    await send_admin_report(results, len(remaining))

    total_sent = sum(r["sent"] for r in results)
    log.info("🏁 Outreach complete: %d DMs sent, %d leads remaining",
             total_sent, len(remaining))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Daily automated outreach")
    parser.add_argument("--dry-run", action="store_true", help="Preview without sending")
    parser.add_argument("--limit", type=int, help="Limit number of accounts to use")
    args = parser.parse_args()
    asyncio.run(main(dry_run=args.dry_run, limit=args.limit))
