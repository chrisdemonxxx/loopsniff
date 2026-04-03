from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.enums import ParseMode

from middlewares.i18n import t, set_lang
from keyboards.inline import language_kb, main_menu_kb

router = Router()


@router.callback_query(F.data == "menu:lang")
async def cb_language_menu(callback: CallbackQuery) -> None:
    uid = callback.from_user.id
    _t = lambda k, **kw: t(uid, k, **kw)
    await callback.message.edit_text(
        _t("lang_title"),
        parse_mode=ParseMode.HTML,
        reply_markup=language_kb(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("lang:"))
async def cb_set_language(callback: CallbackQuery) -> None:
    uid = callback.from_user.id
    lang = callback.data.split(":")[1]
    set_lang(uid, lang)
    _t = lambda k, **kw: t(uid, k, **kw)
    await callback.message.edit_text(
        _t("lang_set"),
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu_kb(_t),
    )
    await callback.answer()
