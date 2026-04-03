from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.enums import ParseMode

from middlewares.i18n import t
from keyboards.inline import faq_kb, faq_detail_kb

router = Router()


@router.callback_query(F.data == "menu:faq")
async def cb_faq(callback: CallbackQuery) -> None:
    uid = callback.from_user.id
    _t = lambda k, **kw: t(uid, k, **kw)
    await callback.message.edit_text(
        _t("faq_title"),
        parse_mode=ParseMode.HTML,
        reply_markup=faq_kb(_t),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("faq:"))
async def cb_faq_detail(callback: CallbackQuery) -> None:
    uid = callback.from_user.id
    faq_num = callback.data.split(":")[1]
    _t = lambda k, **kw: t(uid, k, **kw)
    text_key = f"faq_{faq_num}"
    await callback.message.edit_text(
        _t(text_key),
        parse_mode=ParseMode.HTML,
        reply_markup=faq_detail_kb(_t),
    )
    await callback.answer()
