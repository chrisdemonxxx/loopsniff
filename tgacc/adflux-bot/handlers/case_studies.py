from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.enums import ParseMode

from middlewares.i18n import t
from keyboards.inline import case_studies_kb, case_detail_kb

router = Router()


@router.callback_query(F.data == "menu:cases")
async def cb_case_studies(callback: CallbackQuery) -> None:
    uid = callback.from_user.id
    _t = lambda k, **kw: t(uid, k, **kw)
    await callback.message.edit_text(
        _t("case_studies_title"),
        parse_mode=ParseMode.HTML,
        reply_markup=case_studies_kb(_t),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("case:"))
async def cb_case_detail(callback: CallbackQuery) -> None:
    uid = callback.from_user.id
    case_key = callback.data.split(":")[1]
    _t = lambda k, **kw: t(uid, k, **kw)
    text_key = f"case_{case_key}"
    await callback.message.edit_text(
        _t(text_key),
        parse_mode=ParseMode.HTML,
        reply_markup=case_detail_kb(_t),
    )
    await callback.answer()
