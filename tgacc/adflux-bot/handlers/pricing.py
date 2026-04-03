from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.enums import ParseMode

from middlewares.i18n import t
from keyboards.inline import pricing_kb, pricing_detail_kb

router = Router()


@router.callback_query(F.data == "menu:pricing")
async def cb_pricing_menu(callback: CallbackQuery) -> None:
    uid = callback.from_user.id
    _t = lambda k, **kw: t(uid, k, **kw)
    await callback.message.edit_text(
        _t("pricing_title"),
        parse_mode=ParseMode.HTML,
        reply_markup=pricing_kb(_t),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("price:"))
async def cb_pricing_detail(callback: CallbackQuery) -> None:
    uid = callback.from_user.id
    price_key = callback.data.split(":")[1]
    _t = lambda k, **kw: t(uid, k, **kw)
    text_key = f"pricing_{price_key}"
    await callback.message.edit_text(
        _t(text_key),
        parse_mode=ParseMode.HTML,
        reply_markup=pricing_detail_kb(_t),
    )
    await callback.answer()
