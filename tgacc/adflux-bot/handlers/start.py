from datetime import date

from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.enums import ParseMode

from middlewares.i18n import t
from keyboards.inline import main_menu_kb

router = Router()

# In-memory stats
stats: dict = {
    "users": set(),
    "today_users": {},  # date_str -> set of user ids
}


def _track_user(user_id: int) -> None:
    stats["users"].add(user_id)
    today = str(date.today())
    stats["today_users"].setdefault(today, set()).add(user_id)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    uid = message.from_user.id
    _track_user(uid)
    await message.answer(
        t(uid, "welcome"),
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu_kb(lambda k, **kw: t(uid, k, **kw)),
    )


@router.callback_query(F.data == "menu:main")
async def cb_main_menu(callback: CallbackQuery) -> None:
    uid = callback.from_user.id
    _track_user(uid)
    await callback.message.edit_text(
        t(uid, "welcome"),
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu_kb(lambda k, **kw: t(uid, k, **kw)),
    )
    await callback.answer()
