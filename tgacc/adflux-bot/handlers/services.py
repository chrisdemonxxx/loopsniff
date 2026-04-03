from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.enums import ParseMode

from middlewares.i18n import t
from keyboards.inline import services_kb, service_detail_kb

router = Router()

SERVICE_KEYS = ["google", "meta", "taboola", "outbrain", "mediago", "campaign", "rental"]


@router.callback_query(F.data == "menu:services")
async def cb_services(callback: CallbackQuery) -> None:
    uid = callback.from_user.id
    _t = lambda k, **kw: t(uid, k, **kw)
    await callback.message.edit_text(
        _t("services_title"),
        parse_mode=ParseMode.HTML,
        reply_markup=services_kb(_t),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("svc:"))
async def cb_service_detail(callback: CallbackQuery) -> None:
    uid = callback.from_user.id
    svc_key = callback.data.split(":")[1]
    _t = lambda k, **kw: t(uid, k, **kw)
    text_key = f"svc_{svc_key}_detail"
    await callback.message.edit_text(
        _t(text_key),
        parse_mode=ParseMode.HTML,
        reply_markup=service_detail_kb(_t, svc_key),
    )
    await callback.answer()
