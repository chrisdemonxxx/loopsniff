"""Core outreach dispatcher — sends DMs, listens for replies, auto-responds with AI."""

from __future__ import annotations

import asyncio
import logging
import random
import sys
from datetime import datetime
from typing import List

from telethon import TelegramClient, events
from telethon.errors import (
    FloodWaitError,
    PeerFloodError,
    UserBannedInChannelError,
    UserPrivacyRestrictedError,
    ChatWriteForbiddenError,
    InputUserDeactivatedError,
    UsernameNotOccupiedError,
    UsernameInvalidError,
)

# Ensure RAG module is importable
sys.path.insert(0, "/home/cjs/tgacc/adflux-rag")

from . import config, db
from .models import Account, Lead, Message
from .session_manager import SessionManager
from .message_templates import TemplateEngine, SOURCE_FRIENDLY_NAMES
from .response_handler import ResponseHandler
from .ai_responder import AIResponder

log = logging.getLogger(__name__)


class OutreachDispatcher:
    """Send DMs and listen for replies using Telethon clients."""

    def __init__(self) -> None:
        self.sm = SessionManager()
        self.tpl = TemplateEngine()
        self.response_handler = ResponseHandler()
        self.ai_responder = AIResponder()
        self._running = True

    # ── sending ─────────────────────────────────────────────────────────────

    async def send_dm(
        self, client: TelegramClient, account: Account, lead: Lead
    ) -> bool:
        """Send a single DM. Returns True on success."""
        # Determine attempt number based on previous outbound messages
        msgs = await db.get_messages(lead.username)
        outbound = [m for m in msgs if m.direction == "outbound"]
        attempt = len(outbound) + 1

        template_id, lang = self.tpl.select_template(lead, attempt)
        text = self.tpl.render(
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
            log.warning("FloodWait %ds — pausing account %s", e.seconds, account.phone)
            await asyncio.sleep(e.seconds + 5)
            return False
        except PeerFloodError:
            log.error("PeerFlood on %s — resting account", account.phone)
            await db.update_account(account.phone, status="resting")
            return False
        except (UserPrivacyRestrictedError, ChatWriteForbiddenError):
            log.info("Cannot DM @%s — privacy restricted", lead.username)
            await db.update_lead(lead.username, status="blocked")
            return False
        except (InputUserDeactivatedError, UsernameNotOccupiedError,
                UsernameInvalidError):
            log.info("Lead @%s is invalid / deactivated", lead.username)
            await db.update_lead(lead.username, status="dead")
            return False
        except Exception as exc:
            log.error("Failed to DM @%s via %s: %s", lead.username, account.phone, exc)
            return False

        # Success — persist
        now = datetime.utcnow()
        await db.add_message(
            Message(
                lead_username=lead.username,
                account_phone=account.phone,
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
            contacted_by=account.phone,
        )
        await db.update_account(
            account.phone,
            dms_sent_today=account.dms_sent_today + 1,
            total_dms_sent=account.total_dms_sent + 1,
            last_used=now,
            status="active",
        )
        account.dms_sent_today += 1
        account.total_dms_sent += 1
        log.info("DM sent → @%s via %s (template=%s)", lead.username, account.phone,
                 template_id)
        return True

    # ── reply handler ───────────────────────────────────────────────────────

    async def setup_reply_handler(
        self, client: TelegramClient, account: Account
    ) -> None:
        """Register an incoming-message event handler with AI auto-response."""

        @client.on(events.NewMessage(incoming=True))
        async def _on_reply(event):
            sender = await event.get_sender()
            if sender is None or getattr(sender, "bot", False):
                return

            # Use username if available, fall back to user_id
            username = getattr(sender, "username", None)
            if username:
                username = username.lower()
            else:
                username = f"id_{sender.id}"
            sender_name = getattr(sender, "first_name", "") or username

            text = event.message.text or ""
            if not text.strip():
                return

            log.info(
                "[%s] Incoming DM from @%s (%s): %s",
                account.phone, username, sender_name, text[:120],
            )

            now = datetime.utcnow()

            # Check if sender is a known lead — if not, auto-create
            lead = await db.get_lead_by_username(username)
            if lead is None:
                lead = Lead(
                    username=username,
                    source="inbound_dm",
                    status="replied",
                    language="en",
                )
                await db.add_lead(lead)
                lead = await db.get_lead_by_username(username)
                if lead is None:
                    log.error("Failed to create lead for @%s", username)
                    return
                log.info("Auto-created lead for inbound DM from @%s", username)

            # Log inbound message
            await db.add_message(
                Message(
                    lead_username=username,
                    account_phone=account.phone,
                    direction="inbound",
                    text=text,
                    sent_at=now,
                )
            )
            await db.update_lead(
                username,
                status="replied",
                reply_count=lead.reply_count + 1,
            )
            log.info("Reply from @%s: %s", username, text[:80])

            # Generate AI response
            try:
                result = await self.ai_responder.handle_reply(lead, text)

                if result["auto_respond"] and result["response"]:
                    # Natural delay before replying (5-25 seconds)
                    delay = random.uniform(5, 25)
                    log.debug("Typing delay %.0fs before replying to @%s", delay, username)
                    await asyncio.sleep(delay)

                    # Send AI reply
                    try:
                        await client.send_message(sender, result["response"])
                        log.info(
                            "AI replied to @%s (stage=%s, bant=%d)",
                            username,
                            result["stage"],
                            result["bant"].get("total", 0),
                        )

                        # Log outbound message
                        await db.add_message(
                            Message(
                                lead_username=username,
                                account_phone=account.phone,
                                direction="outbound",
                                text=result["response"],
                                sent_at=datetime.utcnow(),
                                template_id="ai_auto",
                            )
                        )
                    except Exception as send_exc:
                        log.error("Failed to send AI reply to @%s: %s", username, send_exc)

                elif not result["auto_respond"]:
                    log.info(
                        "AI opted out of auto-reply to @%s (negative intent or escalation)",
                        username,
                    )

            except Exception as exc:
                log.error("AI responder error for @%s: %s", username, exc)
                # Fall back to BANT scoring only
                await self.response_handler.process_reply(lead, text)

    # ── per-account worker ──────────────────────────────────────────────────

    async def run_single_account(
        self, account: Account, leads: List[Lead]
    ) -> int:
        """Send DMs from *account* to *leads*, then listen for replies.

        Returns the number of DMs successfully sent.
        """
        client = await self.sm.get_client(account.phone)
        sent = 0
        try:
            if not await client.is_user_authorized():
                log.warning("Account %s not authorised — skipping", account.phone)
                return 0

            await self.setup_reply_handler(client, account)

            for lead in leads:
                if not self._running:
                    break
                if account.dms_sent_today >= config.ULTRA_SAFE_DM_LIMIT:
                    log.info("Daily limit reached for %s", account.phone)
                    break

                ok = await self.send_dm(client, account, lead)
                if ok:
                    sent += 1

                delay = random.uniform(
                    config.MIN_DELAY_BETWEEN_DMS, config.MAX_DELAY_BETWEEN_DMS
                )
                log.debug("Sleeping %.0fs before next DM", delay)
                await asyncio.sleep(delay)

            # Keep client alive briefly to catch any immediate replies
            log.info("DM batch done for %s (%d sent). Listening for replies 60s…",
                     account.phone, sent)
            await asyncio.sleep(60)
        finally:
            await client.disconnect()
        return sent

    # ── main cycle ──────────────────────────────────────────────────────────

    async def run_outreach_cycle(self) -> dict:
        """Execute one full outreach cycle across available accounts."""
        # Reset daily DM counters at the start of each cycle
        all_accounts = await db.get_accounts()
        for a in all_accounts:
            if a.dms_sent_today > 0:
                await db.update_account(a.phone, dms_sent_today=0)

        phones = await self.sm.rotate_sessions()
        if not phones:
            log.warning("No accounts available for outreach")
            return {"accounts_used": 0, "dms_sent": 0}

        new_leads = await db.get_leads(status="new")
        if not new_leads:
            log.info("No new leads to contact")
            return {"accounts_used": 0, "dms_sent": 0}

        # Distribute leads across accounts
        chunk_size = max(1, len(new_leads) // len(phones))
        accounts = await db.get_accounts()
        acct_map = {a.phone: a for a in accounts}
        tasks = []
        for i, phone in enumerate(phones):
            account = acct_map.get(phone)
            if account is None:
                continue

            start = i * chunk_size
            end = start + chunk_size if i < len(phones) - 1 else len(new_leads)
            batch = new_leads[start:end]
            if not batch:
                continue
            tasks.append(self.run_single_account(account, batch))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        total_sent = sum(r for r in results if isinstance(r, int))
        errors = [r for r in results if isinstance(r, Exception)]
        for err in errors:
            log.error("Account worker error: %s", err)

        return {
            "accounts_used": len(tasks),
            "dms_sent": total_sent,
            "errors": len(errors),
        }

    def stop(self) -> None:
        self._running = False
