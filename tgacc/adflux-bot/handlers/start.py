from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.enums import ParseMode

from middlewares.i18n import t
from keyboards.inline import main_menu_kb
from db.persistence import record_user_visit

router = Router()


def _track_user(user_id: int) -> None:
    record_user_visit(user_id)


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
