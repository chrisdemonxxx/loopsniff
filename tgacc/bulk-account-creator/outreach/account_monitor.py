"""Account health monitoring — detect spam flags, bans, flood waits."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import List

from telethon.errors import (
    AuthKeyUnregisteredError,
    UserDeactivatedBanError,
    PhoneNumberBannedError,
    FloodWaitError,
)

from . import db
from .session_manager import SessionManager

log = logging.getLogger(__name__)


class AccountMonitor:
    """Periodically check every account's health and report issues."""

    def __init__(self) -> None:
        self.sm = SessionManager()

    async def check_all_accounts(self) -> List[dict]:
        """Validate every known account and return status list."""
        accounts = await db.get_accounts()
        results: list[dict] = []

        for acct in accounts:
            status = acct.status
            detail = "ok"
            try:
                client = await self.sm.get_client(acct.phone)
                try:
                    if not await client.is_user_authorized():
                        status = "banned"
                        detail = "not_authorized"
                    else:
                        me = await client.get_me()
                        if me.restricted:
                            status = "banned"
                            detail = "restricted"
                        else:
                            detail = f"user_id={me.id}"
                finally:
                    await client.disconnect()
            except (AuthKeyUnregisteredError, UserDeactivatedBanError,
                    PhoneNumberBannedError) as exc:
                status = "banned"
                detail = str(exc)
            except FloodWaitError as e:
                detail = f"flood_wait_{e.seconds}s"
            except Exception as exc:
                detail = f"error: {exc}"

            if status != acct.status:
                await db.update_account(acct.phone, status=status)

            results.append({
                "phone": acct.phone,
                "previous_status": acct.status,
                "current_status": status,
                "detail": detail,
                "dms_today": acct.dms_sent_today,
                "total_dms": acct.total_dms_sent,
                "spam_reports": acct.spam_reports,
            })

        return results

    async def handle_ban(self, phone: str) -> None:
        """Move an account to 'banned' and try to activate a replacement."""
        await db.update_account(phone, status="banned")
        log.warning("Account %s marked as BANNED", phone)

        # Try to promote a resting account
        resting = await db.get_accounts(status="resting")
        if resting:
            replacement = resting[0]
            await db.update_account(replacement.phone, status="active")
            log.info("Activated replacement account %s", replacement.phone)

    async def daily_report(self) -> str:
        """Generate a human-readable daily health report."""
        accounts = await db.get_accounts()
        stats = await db.get_daily_stats()

        lines = [
            "═══════════════════════════════════════",
            "       DAILY OUTREACH HEALTH REPORT",
            f"       {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
            "═══════════════════════════════════════",
            "",
        ]

        # Account breakdown
        status_counts: dict[str, int] = {}
        for a in accounts:
            status_counts[a.status] = status_counts.get(a.status, 0) + 1

        lines.append("📱 ACCOUNTS")
        for s, c in sorted(status_counts.items()):
            emoji = {"ready": "✅", "active": "🟢", "warming": "🔄",
                     "fresh": "🆕", "banned": "🚫", "resting": "💤"}.get(s, "❓")
            lines.append(f"  {emoji} {s:12s}: {c}")
        lines.append(f"  Total: {len(accounts)}")
        lines.append("")

        # DM stats
        lines.append("📨 TODAY'S ACTIVITY")
        lines.append(f"  DMs sent:       {stats['dms_sent_today']}")
        lines.append(f"  Replies:        {stats['replies_today']}")
        lines.append(f"  Leads qualified: {stats['leads_qualified']}")
        lines.append(f"  Hot leads:      {stats['leads_hot']}")
        lines.append("")

        # Totals
        lines.append("📊 TOTALS")
        lines.append(f"  Total leads:    {stats['total_leads']}")
        lines.append(f"  Total accounts: {stats['total_accounts']}")
        lines.append(f"  Banned:         {stats['accounts_banned']}")
        lines.append("")
        lines.append("═══════════════════════════════════════")

        report = "\n".join(lines)
        return report
