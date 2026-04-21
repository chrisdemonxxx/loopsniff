from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from aiogram.enums import ParseMode

from db.persistence import record_user_visit

router = Router()

WELCOME = (
    "<b>Kliqboost Media — Advertising Solutions</b>\n\n"
    "We partner with media buyers to provide verified advertising "
    "infrastructure across Google, Meta, TikTok, and Taboola.\n\n"
    "Tell us your platform and goals — we'll find the right solution for you."
)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    record_user_visit(message.from_user.id)
    await message.answer(WELCOME, parse_mode=ParseMode.HTML)
