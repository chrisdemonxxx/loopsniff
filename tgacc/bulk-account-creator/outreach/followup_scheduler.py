"""Follow-up cadence management.

Checks which contacted leads have not replied and schedules follow-up
messages according to the template delay rules.
"""

from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime, timedelta
from typing import List

from . import config, db
from .models import Lead, Message
from .message_templates import TEMPLATES
from .session_manager import SessionManager
from .dispatcher import OutreachDispatcher

log = logging.getLogger(__name__)


class FollowupScheduler:
    """Identify and send follow-up messages on schedule."""

    def __init__(self) -> None:
        self.sm = SessionManager()

    async def check_followups_due(self) -> List[dict]:
        """Return leads that are due for a follow-up.

        Rules:
        - Lead status is 'contacted' (no reply yet).
        - followup_1: contacted > 48 h ago AND followup_1 not yet sent.
        - followup_2: contacted > 120 h ago AND followup_2 not yet sent.
        """
        contacted_leads = await db.get_leads(status="contacted")
        now = datetime.utcnow()
        due: list[dict] = []

        for lead in contacted_leads:
            if lead.contacted_at is None:
                continue

            messages = await db.get_messages(lead.username)
            sent_template_ids = {
                m.template_id for m in messages if m.direction == "outbound" and m.template_id
            }

            hours_since = (now - lead.contacted_at).total_seconds() / 3600

            # Check followup_1 (48 h)
            lang = lead.language if lead.language in TEMPLATES else "en"
            fu1_id = TEMPLATES[lang]["followup_1"]["id"]
            fu2_id = TEMPLATES[lang]["followup_2"]["id"]

            if hours_since >= 48 and fu1_id not in sent_template_ids:
                due.append({"lead": lead, "attempt": 2, "template_id": fu1_id})
            elif hours_since >= 120 and fu2_id not in sent_template_ids:
                due.append({"lead": lead, "attempt": 3, "template_id": fu2_id})

        log.info("Follow-ups due: %d", len(due))
        return due

    async def send_followups(self) -> dict:
        """Send all due follow-up messages."""
        due = await self.check_followups_due()
        if not due:
            return {"sent": 0}

        dispatcher = OutreachDispatcher()
        sent = 0
        errors = 0

        for item in due:
            lead: Lead = item["lead"]
            # Use the same account that originally contacted the lead
            if not lead.contacted_by:
                continue

            accounts = await db.get_accounts()
            acct_map = {a.phone: a for a in accounts}
            account = acct_map.get(lead.contacted_by)
            if account is None or account.status in ("banned", "resting"):
                # Try another available account
                account = await db.get_account_for_outreach()
                if account is None:
                    log.warning("No accounts available for follow-ups")
                    break

            try:
                client = await self.sm.get_client(account.phone)
                try:
                    ok = await dispatcher.send_dm(client, account, lead)
                    if ok:
                        sent += 1
                    else:
                        errors += 1
                finally:
                    await client.disconnect()
            except Exception as exc:
                log.error("Follow-up error for @%s: %s", lead.username, exc)
                errors += 1

            # Delay between follow-ups
            await asyncio.sleep(random.uniform(
                config.MIN_DELAY_BETWEEN_DMS, config.MAX_DELAY_BETWEEN_DMS
            ))

        result = {"sent": sent, "errors": errors}
        log.info("Follow-up results: %s", result)
        return result
