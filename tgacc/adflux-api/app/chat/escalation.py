import logging
import aiohttp
import asyncio
from app.config import get_settings

log = logging.getLogger(__name__)
settings = get_settings()


async def _fire_and_forget(coro):
    try:
        await coro
    except Exception as e:
        log.error("Escalation error: %s (type: %s)", e, type(e).__name__)


async def send_telegram(message: str):
    if not settings.TG_BOT_TOKEN or not settings.TG_ALERT_CHAT_ID:
        log.debug("Telegram escalation skipped: missing config (TG_BOT_TOKEN or TG_ALERT_CHAT_ID)")
        return
    url = f"https://api.telegram.org/bot{settings.TG_BOT_TOKEN}/sendMessage"
    try:
        async with aiohttp.ClientSession() as session:
            response = await session.post(url, json={
                "chat_id": settings.TG_ALERT_CHAT_ID,
                "text": message,
                "parse_mode": "HTML",
            }, timeout=aiohttp.ClientTimeout(total=10))
            if response.status == 200:
                log.info("Telegram alert delivered successfully to chat_id=%s", settings.TG_ALERT_CHAT_ID)
            else:
                log.warning("Telegram alert failed with status %d: %s", response.status, await response.text())
    except Exception as e:
        log.error("Telegram escalation failed: %s (type: %s)", e, type(e).__name__)


async def send_ntfy(message: str, title: str = "AdFlux Alert"):
    if not settings.NTFY_TOPIC:
        log.debug("ntfy escalation skipped: missing config (NTFY_TOPIC)")
        return
    try:
        async with aiohttp.ClientSession() as session:
            response = await session.post(
                f"{settings.NTFY_URL}/{settings.NTFY_TOPIC}",
                data=message.encode(),
                headers={"Title": title, "Priority": "high"},
                timeout=aiohttp.ClientTimeout(total=10),
            )
            if response.status == 200:
                log.info("ntfy alert delivered successfully to topic=%s", settings.NTFY_TOPIC)
            else:
                log.warning("ntfy alert failed with status %d: %s", response.status, await response.text())
    except Exception as e:
        log.error("ntfy escalation failed: %s (type: %s)", e, type(e).__name__)


async def send_sms(message: str):
    if not settings.TWILIO_SID or not settings.TWILIO_TOKEN or not settings.ALERT_PHONE:
        log.debug("SMS escalation skipped: missing config (TWILIO_SID, TWILIO_TOKEN, or ALERT_PHONE)")
        return
    url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.TWILIO_SID}/Messages.json"
    try:
        async with aiohttp.ClientSession() as session:
            response = await session.post(url, data={
                "From": settings.TWILIO_FROM,
                "To": settings.ALERT_PHONE,
                "Body": message,
            }, auth=aiohttp.BasicAuth(settings.TWILIO_SID, settings.TWILIO_TOKEN),
            timeout=aiohttp.ClientTimeout(total=10))
            if response.status == 201:
                log.info("SMS alert delivered successfully to phone=%s", settings.ALERT_PHONE)
            else:
                log.warning("SMS alert failed with status %d: %s", response.status, await response.text())
    except Exception as e:
        log.error("SMS escalation failed: %s (type: %s)", e, type(e).__name__)


async def send_whatsapp(message: str):
    if not settings.TWILIO_SID or not settings.WHATSAPP_FROM or not settings.WHATSAPP_TO:
        log.debug("WhatsApp escalation skipped: missing config (TWILIO_SID, WHATSAPP_FROM, or WHATSAPP_TO)")
        return
    url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.TWILIO_SID}/Messages.json"
    try:
        async with aiohttp.ClientSession() as session:
            response = await session.post(url, data={
                "From": settings.WHATSAPP_FROM,
                "To": settings.WHATSAPP_TO,
                "Body": message,
            }, auth=aiohttp.BasicAuth(settings.TWILIO_SID, settings.TWILIO_TOKEN),
            timeout=aiohttp.ClientTimeout(total=10))
            if response.status == 201:
                log.info("WhatsApp alert delivered successfully to recipient=%s", settings.WHATSAPP_TO)
            else:
                log.warning("WhatsApp alert failed with status %d: %s", response.status, await response.text())
    except Exception as e:
        log.error("WhatsApp escalation failed: %s (type: %s)", e, type(e).__name__)


async def send_email(subject: str, body: str):
    if not settings.SENDGRID_API_KEY:
        log.debug("Email escalation skipped: missing config (SENDGRID_API_KEY)")
        return
    try:
        async with aiohttp.ClientSession() as session:
            response = await session.post(
                "https://api.sendgrid.com/v3/mail/send",
                headers={
                    "Authorization": f"Bearer {settings.SENDGRID_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "personalizations": [{"to": [{"email": settings.ALERT_EMAIL_TO}]}],
                    "from": {"email": settings.ALERT_EMAIL_FROM},
                    "subject": subject,
                    "content": [{"type": "text/plain", "value": body}],
                },
                timeout=aiohttp.ClientTimeout(total=10),
            )
            if response.status == 202:
                log.info("Email alert delivered successfully to recipient=%s", settings.ALERT_EMAIL_TO)
            else:
                log.warning("Email alert failed with status %d: %s", response.status, await response.text())
    except Exception as e:
        log.error("Email escalation failed: %s (type: %s)", e, type(e).__name__)


async def escalate_all(message: str, title: str = "AdFlux Escalation"):
    """Fire all escalation channels concurrently, fire-and-forget."""
    log.info("Escalation initiated: title=%s, message_len=%d", title, len(message))
    tasks = [
        asyncio.create_task(_fire_and_forget(send_telegram(f"🚨 <b>{title}</b>\n{message}"))),
        asyncio.create_task(_fire_and_forget(send_ntfy(message, title))),
        asyncio.create_task(_fire_and_forget(send_sms(f"{title}: {message}"))),
        asyncio.create_task(_fire_and_forget(send_whatsapp(f"{title}: {message}"))),
        asyncio.create_task(_fire_and_forget(send_email(title, message))),
    ]
    await asyncio.gather(*tasks, return_exceptions=True)
    log.debug("Escalation all channels initiated (fire-and-forget mode)")
