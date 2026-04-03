"""Outreach message execution engine.

Processes campaign sequence steps and sends messages via configured channels.
Currently supports: Telegram bot API, email (via SendGrid).
"""

import aiohttp
import logging
from datetime import datetime
from typing import Optional
from app.config import get_settings

logger = logging.getLogger(__name__)


async def send_telegram_message(chat_id: str, message: str) -> bool:
    """Send a message via Telegram Bot API."""
    settings = get_settings()
    token = settings.TELEGRAM_BOT_TOKEN or settings.TG_BOT_TOKEN
    if not token:
        logger.warning("TELEGRAM_BOT_TOKEN not set — message logged only")
        logger.info(f"[OUTREACH-LOG] Telegram to {chat_id}: {message[:100]}...")
        return True

    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json={
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "HTML",
            }) as resp:
                if resp.status == 200:
                    return True
                logger.error(f"Telegram API returned {resp.status}")
                return False
    except Exception as e:
        logger.error(f"Telegram send failed: {e}")
        return False


async def execute_sequence_step(step: dict, lead: dict) -> dict:
    """Execute a single sequence step for a lead.

    Returns: {"success": bool, "channel": str, "error": str|None}
    """
    channel = step.get("channel", "telegram")
    message = step.get("message", "")

    # Template variable substitution
    message = message.replace("{{name}}", lead.get("name", ""))
    message = message.replace("{{company}}", lead.get("company", ""))
    message = message.replace("{{username}}", lead.get("tg_username", ""))

    if channel == "telegram":
        contact = lead.get("telegram_id") or lead.get("tg_user_id") or lead.get("contact")
        if not contact:
            return {"success": False, "channel": channel, "error": "No telegram contact for lead"}
        success = await send_telegram_message(str(contact), message)
        return {"success": success, "channel": channel, "error": None if success else "Send failed"}

    elif channel == "email":
        try:
            from app.email.service import _send_email
            success = await _send_email(
                lead.get("email", ""),
                f"From AdFlux: {step.get('subject', 'Message')}",
                message,
            )
            return {"success": success, "channel": channel, "error": None if success else "Email send failed"}
        except ImportError:
            logger.warning("Email service not available for outreach")
            return {"success": False, "channel": channel, "error": "Email service not configured"}

    return {"success": False, "channel": channel, "error": f"Unknown channel: {channel}"}
