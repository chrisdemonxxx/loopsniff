from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from aiogram.enums import ParseMode

from db.persistence import record_user_visit

router = Router()

WELCOME = (
    "<b>Kliqboost Media</b>\n\n"
    "Agency ad accounts for Google, Meta, TikTok, Taboola and more.\n\n"
    "Tell me what you need — platform, budget, timeline — "
    "and I'll get you sorted. Ready when you are."
)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    record_user_visit(message.from_user.id)
    await message.answer(WELCOME, parse_mode=ParseMode.HTML)
