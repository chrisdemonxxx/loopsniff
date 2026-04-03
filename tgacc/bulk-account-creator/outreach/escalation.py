"""Multi-channel escalation manager.

Fires alerts on ALL configured channels concurrently when the AI sales
bot cannot resolve a client issue and human intervention is needed.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Optional

import aiohttp

from . import config as outreach_config

log = logging.getLogger(__name__)

# ── Env-based configuration ────────────────────────────────────────────────

_NTFY_SERVER = os.getenv("NTFY_SERVER", "https://ntfy.sh")
_NTFY_TOPIC = os.getenv("NTFY_TOPIC", "adflux-escalations")

_TWILIO_SID = os.getenv("TWILIO_SID", "")
_TWILIO_TOKEN = os.getenv("TWILIO_TOKEN", "")
_TWILIO_FROM = os.getenv("TWILIO_FROM", "")
_TWILIO_WA_FROM = os.getenv("TWILIO_WA_FROM", "")
_ADMIN_PHONE = os.getenv("ADMIN_PHONE", "")

_SENDGRID_KEY = os.getenv("SENDGRID_KEY", "")
_ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "")
_FROM_EMAIL = os.getenv("FROM_EMAIL", "alerts@adflux.media")


class EscalationManager:
    """Fire alerts on every configured channel when escalation is needed."""

    def __init__(
        self,
        tg_token: str | None = None,
        admin_chat_id: str | None = None,
        ntfy_server: str | None = None,
        ntfy_topic: str | None = None,
        twilio_sid: str | None = None,
        twilio_token: str | None = None,
        twilio_from: str | None = None,
        twilio_wa_from: str | None = None,
        admin_phone: str | None = None,
        sendgrid_key: str | None = None,
        admin_email: str | None = None,
        from_email: str | None = None,
    ):
        self.tg_token = tg_token or outreach_config.ADMIN_BOT_TOKEN
        self.admin_chat_id = admin_chat_id or outreach_config.ADMIN_CHAT_ID
        self.ntfy_server = ntfy_server or _NTFY_SERVER
        self.ntfy_topic = ntfy_topic or _NTFY_TOPIC
        self.twilio_sid = twilio_sid or _TWILIO_SID
        self.twilio_token = twilio_token or _TWILIO_TOKEN
        self.twilio_from = twilio_from or _TWILIO_FROM
        self.twilio_wa_from = twilio_wa_from or _TWILIO_WA_FROM
        self.admin_phone = admin_phone or _ADMIN_PHONE
        self.sendgrid_key = sendgrid_key or _SENDGRID_KEY
        self.admin_email = admin_email or _ADMIN_EMAIL
        self.from_email = from_email or _FROM_EMAIL

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def escalate(
        self,
        client_name: str,
        issue: str,
        session_id: str,
        priority: str = "high",
    ) -> dict:
        """Fire alerts on ALL channels simultaneously.

        Returns a dict mapping channel name → success bool.
        """
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        short_msg = (
            f"🚨 ESCALATION [{priority.upper()}]\n"
            f"Client: {client_name}\n"
            f"Issue: {issue}\n"
            f"Session: {session_id}\n"
            f"Time: {ts}"
        )

        results = await asyncio.gather(
            self._tg_alert(short_msg),
            self._ntfy_push(short_msg, priority),
            self._sms_alert(short_msg),
            self._whatsapp_alert(short_msg),
            self._email_alert(client_name, issue, session_id),
            return_exceptions=True,
        )

        channel_names = ["telegram", "ntfy", "sms", "whatsapp", "email"]
        report: dict[str, bool] = {}
        for name, result in zip(channel_names, results):
            if isinstance(result, Exception):
                log.error("Escalation channel %s failed: %s", name, result)
                report[name] = False
            else:
                report[name] = result

        succeeded = sum(1 for v in report.values() if v)
        log.info(
            "Escalation for %s fired on %d/%d channels: %s",
            client_name, succeeded, len(report), report,
        )
        return report

    # ------------------------------------------------------------------
    # Channel implementations
    # ------------------------------------------------------------------

    async def _tg_alert(self, message: str) -> bool:
        """Send alert via Telegram Bot API."""
        if not self.tg_token or not self.admin_chat_id:
            log.debug("Telegram not configured — skipping")
            return False

        url = f"https://api.telegram.org/bot{self.tg_token}/sendMessage"
        payload = {
            "chat_id": self.admin_chat_id,
            "text": message,
            "parse_mode": "HTML",
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url, json=payload,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status == 200:
                        log.info("TG escalation sent")
                        return True
                    body = await resp.text()
                    log.warning("TG escalation failed (%d): %s", resp.status, body)
                    return False
        except Exception as exc:
            log.error("TG escalation error: %s", exc)
            return False

    async def _ntfy_push(self, message: str, priority: str) -> bool:
        """Push notification via ntfy.sh."""
        if not self.ntfy_server or not self.ntfy_topic:
            log.debug("ntfy not configured — skipping")
            return False

        ntfy_priority_map = {
            "low": "2",
            "medium": "3",
            "high": "4",
            "urgent": "5",
        }

        url = f"{self.ntfy_server.rstrip('/')}/{self.ntfy_topic}"
        headers = {
            "Title": "AdFlux Escalation",
            "Priority": ntfy_priority_map.get(priority.lower(), "4"),
            "Tags": "warning,rotating_light",
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url, data=message.encode(), headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status == 200:
                        log.info("ntfy escalation sent")
                        return True
                    body = await resp.text()
                    log.warning("ntfy escalation failed (%d): %s", resp.status, body)
                    return False
        except Exception as exc:
            log.error("ntfy escalation error: %s", exc)
            return False

    async def _sms_alert(self, message: str) -> bool:
        """Send SMS alert via Twilio."""
        if not all([self.twilio_sid, self.twilio_token,
                    self.twilio_from, self.admin_phone]):
            log.debug("Twilio SMS not configured — skipping")
            return False

        url = (
            f"https://api.twilio.com/2010-04-01/Accounts/"
            f"{self.twilio_sid}/Messages.json"
        )
        payload = {
            "From": self.twilio_from,
            "To": self.admin_phone,
            "Body": message[:1600],
        }
        auth = aiohttp.BasicAuth(self.twilio_sid, self.twilio_token)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url, data=payload, auth=auth,
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    if resp.status == 201:
                        log.info("SMS escalation sent")
                        return True
                    body = await resp.text()
                    log.warning("SMS escalation failed (%d): %s", resp.status, body)
                    return False
        except Exception as exc:
            log.error("SMS escalation error: %s", exc)
            return False

    async def _whatsapp_alert(self, message: str) -> bool:
        """Send WhatsApp alert via Twilio."""
        if not all([self.twilio_sid, self.twilio_token,
                    self.twilio_wa_from, self.admin_phone]):
            log.debug("Twilio WhatsApp not configured — skipping")
            return False

        url = (
            f"https://api.twilio.com/2010-04-01/Accounts/"
            f"{self.twilio_sid}/Messages.json"
        )
        wa_to = (
            self.admin_phone
            if self.admin_phone.startswith("whatsapp:")
            else f"whatsapp:{self.admin_phone}"
        )
        wa_from = (
            self.twilio_wa_from
            if self.twilio_wa_from.startswith("whatsapp:")
            else f"whatsapp:{self.twilio_wa_from}"
        )

        payload = {
            "From": wa_from,
            "To": wa_to,
            "Body": message[:1600],
        }
        auth = aiohttp.BasicAuth(self.twilio_sid, self.twilio_token)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url, data=payload, auth=auth,
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    if resp.status == 201:
                        log.info("WhatsApp escalation sent")
                        return True
                    body = await resp.text()
                    log.warning("WhatsApp escalation failed (%d): %s",
                                resp.status, body)
                    return False
        except Exception as exc:
            log.error("WhatsApp escalation error: %s", exc)
            return False

    async def _email_alert(
        self, client_name: str, issue: str, session_id: str,
    ) -> bool:
        """Send email alert via SendGrid."""
        if not self.sendgrid_key or not self.admin_email:
            log.debug("SendGrid not configured — skipping")
            return False

        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        url = "https://api.sendgrid.com/v3/mail/send"
        payload = {
            "personalizations": [{"to": [{"email": self.admin_email}]}],
            "from": {"email": self.from_email, "name": "AdFlux Alerts"},
            "subject": f"🚨 Escalation: {client_name} — {issue[:50]}",
            "content": [
                {
                    "type": "text/html",
                    "value": (
                        f"<h2>🚨 Client Escalation</h2>"
                        f"<p><b>Client:</b> {client_name}</p>"
                        f"<p><b>Issue:</b> {issue}</p>"
                        f"<p><b>Session:</b> <code>{session_id}</code></p>"
                        f"<p><b>Time:</b> {ts}</p>"
                        f"<hr>"
                        f"<p><i>Auto-generated by the AdFlux AI sales bot.</i></p>"
                    ),
                }
            ],
        }
        headers = {
            "Authorization": f"Bearer {self.sendgrid_key}",
            "Content-Type": "application/json",
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url, json=payload, headers=headers,
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    if resp.status in (200, 201, 202):
                        log.info("Email escalation sent")
                        return True
                    body = await resp.text()
                    log.warning("Email escalation failed (%d): %s",
                                resp.status, body)
                    return False
        except Exception as exc:
            log.error("Email escalation error: %s", exc)
            return False
