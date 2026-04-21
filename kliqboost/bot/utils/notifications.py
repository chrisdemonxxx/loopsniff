import logging

from aiogram import Bot
from aiogram.enums import ParseMode

from config import ADMIN_CHAT_ID

logger = logging.getLogger(__name__)


async def notify_admin(bot: Bot, text: str) -> None:
    try:
        await bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=text,
            parse_mode=ParseMode.HTML,
        )
    except Exception as exc:
        logger.error("Failed to notify admin: %s", exc)
