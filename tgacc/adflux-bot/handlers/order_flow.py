from datetime import date

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.enums import ParseMode

from config import ADMIN_USERNAME
from middlewares.i18n import t
from keyboards.inline import (
    order_platform_kb,
    order_niche_kb,
    order_budget_kb,
    order_timing_kb,
    main_menu_kb,
)
from states.order import OrderStates
from utils.notifications import notify_admin

router = Router()

# In-memory leads storage
leads: list = []
leads_today: dict = {}  # date_str -> count


def _record_lead(data: dict) -> None:
    leads.append(data)
    today = str(date.today())
    leads_today[today] = leads_today.get(today, 0) + 1


@router.callback_query(F.data == "menu:order")
async def cb_order_start(callback: CallbackQuery, state: FSMContext) -> None:
    uid = callback.from_user.id
    _t = lambda k, **kw: t(uid, k, **kw)
    await state.set_state(OrderStates.platform)
    await callback.message.edit_text(
        _t("order_step1"),
        parse_mode=ParseMode.HTML,
        reply_markup=order_platform_kb(_t),
    )
    await callback.answer()


@router.callback_query(OrderStates.platform, F.data.startswith("order:plat:"))
async def cb_order_platform(callback: CallbackQuery, state: FSMContext) -> None:
    uid = callback.from_user.id
    value = callback.data.split(":", 2)[2]
    await state.update_data(platform=value)
    _t = lambda k, **kw: t(uid, k, **kw)
    await state.set_state(OrderStates.niche)
    await callback.message.edit_text(
        _t("order_step2"),
        parse_mode=ParseMode.HTML,
        reply_markup=order_niche_kb(_t),
    )
    await callback.answer()


@router.callback_query(OrderStates.niche, F.data.startswith("order:niche:"))
async def cb_order_niche(callback: CallbackQuery, state: FSMContext) -> None:
    uid = callback.from_user.id
    value = callback.data.split(":", 2)[2]
    await state.update_data(niche=value)
    _t = lambda k, **kw: t(uid, k, **kw)
    await state.set_state(OrderStates.budget)
    await callback.message.edit_text(
        _t("order_step3"),
        parse_mode=ParseMode.HTML,
        reply_markup=order_budget_kb(_t),
    )
    await callback.answer()


@router.callback_query(OrderStates.budget, F.data.startswith("order:budget:"))
async def cb_order_budget(callback: CallbackQuery, state: FSMContext) -> None:
    uid = callback.from_user.id
    value = callback.data.split(":", 2)[2]
    await state.update_data(budget=value)
    _t = lambda k, **kw: t(uid, k, **kw)
    await state.set_state(OrderStates.timing)
    await callback.message.edit_text(
        _t("order_step4"),
        parse_mode=ParseMode.HTML,
        reply_markup=order_timing_kb(_t),
    )
    await callback.answer()


@router.callback_query(OrderStates.timing, F.data.startswith("order:timing:"))
async def cb_order_timing(callback: CallbackQuery, state: FSMContext) -> None:
    uid = callback.from_user.id
    value = callback.data.split(":", 2)[2]
    await state.update_data(timing=value)
    _t = lambda k, **kw: t(uid, k, **kw)
    await state.set_state(OrderStates.contact)
    await callback.message.edit_text(
        _t("order_step5"),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


@router.message(OrderStates.contact)
async def msg_order_contact(message: Message, state: FSMContext) -> None:
    uid = message.from_user.id
    contact = message.text or ""
    await state.update_data(contact=contact)
    data = await state.get_data()
    await state.clear()

    _t = lambda k, **kw: t(uid, k, **kw)

    lead_data = {
        "user_id": uid,
        "user_name": message.from_user.full_name,
        "username": message.from_user.username or "N/A",
        "platform": data.get("platform", ""),
        "niche": data.get("niche", ""),
        "budget": data.get("budget", ""),
        "timing": data.get("timing", ""),
        "contact": contact,
    }
    _record_lead(lead_data)

    # Confirm to user
    await message.answer(
        _t(
            "order_confirm",
            admin=ADMIN_USERNAME,
            platform=lead_data["platform"],
            niche=lead_data["niche"],
            budget=lead_data["budget"],
            timing=lead_data["timing"],
            contact=lead_data["contact"],
        ),
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu_kb(_t),
    )

    # Notify admin
    admin_text = t(
        uid,
        "admin_lead_card",
        user_name=lead_data["user_name"],
        user_id=lead_data["user_id"],
        username=lead_data["username"],
        platform=lead_data["platform"],
        niche=lead_data["niche"],
        budget=lead_data["budget"],
        timing=lead_data["timing"],
        contact=lead_data["contact"],
    )
    await notify_admin(message.bot, admin_text)
