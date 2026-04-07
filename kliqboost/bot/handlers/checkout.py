"""Checkout FSM — end-to-end payment flow for Kliqboost bot.

Flow: Order summary → Payment method → Show address → TX hash → Verify → Confirm
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import time
from typing import Dict

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.enums import ParseMode, ChatAction

from states.checkout import CheckoutStates
from keyboards.inline import (
    checkout_confirm_kb,
    payment_method_kb,
    payment_sent_kb,
    admin_verify_kb,
)

import sys
sys.path.insert(0, "/home/cjs/kliqboost")
from payments.crypto_verifier import verify_transaction, get_crypto_price, TxResult
from payments.order_manager import (
    create_order, update_payment, submit_tx_hash, confirm_payment,
    set_admin_review, get_order, get_active_order, get_pending_verifications,
    STATUS_SUBMITTED,
)

log = logging.getLogger(__name__)
router = Router()

# ── Config ───────────────────────────────────────────────────────────────
BTC_ADDRESS = os.getenv("BTC_ADDRESS", "")
ETH_ADDRESS = os.getenv("ETH_ADDRESS", "")
USDT_ERC20_ADDRESS = os.getenv("USDT_ERC20_ADDRESS", "")
AUTO_CONFIRM_THRESHOLD = float(os.getenv("AUTO_CONFIRM_THRESHOLD", "5000"))
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))

WALLET_MAP: Dict[str, str] = {
    "BTC": BTC_ADDRESS,
    "ETH": ETH_ADDRESS,
    "USDT": USDT_ERC20_ADDRESS,
}

NETWORK_NAMES = {
    "BTC": "Bitcoin Mainnet",
    "ETH": "Ethereum Mainnet",
    "USDT": "Ethereum Mainnet (ERC-20)",
}

TX_HASH_RE = re.compile(r"^(0x)?[a-fA-F0-9]{64}$")

# Track active verification tasks
_verification_tasks: Dict[str, asyncio.Task] = {}


# ── Helpers ──────────────────────────────────────────────────────────────

def _shorten(h: str) -> str:
    if len(h) > 16:
        return h[:8] + "..." + h[-8:]
    return h


def _explorer_link(tx_hash: str, currency: str) -> str:
    if currency == "BTC":
        return f"https://blockstream.info/tx/{tx_hash}"
    return f"https://etherscan.io/tx/{tx_hash}"


async def _notify_admin_payment(bot, order: dict, tx_result: TxResult):
    if not ADMIN_CHAT_ID:
        return
    auto = "✅ Auto-verified" if order.get("amount_usd", 0) <= AUTO_CONFIRM_THRESHOLD else "⚠️ Manual review required"
    text = (
        f"💰 <b>NEW PAYMENT RECEIVED</b>\n\n"
        f"🎫 Order: <code>{order['order_code']}</code>\n"
        f"👤 @{order.get('username', 'N/A')} (id: {order['user_id']})\n"
        f"📦 {order.get('platform', '?')} — {order.get('niche', '?')}\n"
        f"💰 ${tx_result.amount_usd:,.2f} ({tx_result.amount_crypto:.6f} {tx_result.currency})\n"
        f"🔗 TX: <code>{_shorten(order.get('tx_hash', ''))}</code>\n"
        f"✅ Confirmations: {tx_result.confirmations}\n"
        f"{auto}\n\n"
        f"⏱ Client told: 2 hours delivery"
    )
    markup = None
    if order.get("amount_usd", 0) > AUTO_CONFIRM_THRESHOLD:
        markup = admin_verify_kb(order["order_code"])
    try:
        await bot.send_message(ADMIN_CHAT_ID, text, parse_mode=ParseMode.HTML, reply_markup=markup)
    except Exception as exc:
        log.error("Admin payment notify failed: %s", exc)


# ── Step 1: Start checkout (from "Ready to Order" button) ───────────────

@router.callback_query(F.data == "checkout:start")
async def cb_checkout_start(callback: CallbackQuery, state: FSMContext) -> None:
    uid = callback.from_user.id
    username = callback.from_user.username or ""
    full_name = callback.from_user.full_name or ""

    # Check for existing active order
    active = get_active_order(uid)
    if active:
        await callback.message.edit_text(
            f"⚡ You already have an active order: <code>{active['order_code']}</code>\n"
            f"Status: {active['status'].replace('_', ' ').title()}\n\n"
            f"Complete this one first, or DM @Chris_Darton for help.",
            parse_mode=ParseMode.HTML,
        )
        await callback.answer()
        return

    # Pull BANT data from the ai_chat module's state
    from db.persistence import get_history
    history = get_history(uid, limit=30)
    user_msgs = [m["content"] for m in history if m.get("role") == "user"]

    from scoring.bant_scorer import BANTScorer
    scorer = BANTScorer()
    bant = scorer.score_from_conversation(user_msgs)
    extracted = bant.get("extracted", {})

    platform = extracted.get("platform") or "Ad accounts"
    niche = extracted.get("niche") or "General"
    budget_str = extracted.get("budget")

    # If budget wasn't detected, don't default to $1000 — show "TBD" and let user modify
    if budget_str:
        budget_num = _parse_budget_amount(budget_str)
    else:
        budget_num = 0  # Will prompt user to set via Modify button

    # Create the order
    order = create_order(
        user_id=uid,
        username=username,
        full_name=full_name,
        platform=platform,
        niche=niche,
        amount_usd=budget_num,
    )

    await state.set_state(CheckoutStates.confirm_order)
    await state.update_data(order_code=order["order_code"])

    budget_display = f"${budget_num:,.0f}" if budget_num > 0 else "TBD — tap Modify to set"

    summary = (
        f"📋 <b>ORDER SUMMARY</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🎫 Order: <code>{order['order_code']}</code>\n"
        f"🔧 Platform: {platform}\n"
        f"🏷 Niche: {niche}\n"
        f"💰 Amount: <b>{budget_display}</b>\n\n"
        f"Review your order above. Hit <b>Confirm</b> to proceed to payment."
    )

    await callback.message.edit_text(
        summary,
        parse_mode=ParseMode.HTML,
        reply_markup=checkout_confirm_kb(order["order_code"]),
    )
    await callback.answer()


# ── Step 2: Confirm order → payment method selection ─────────────────────

@router.callback_query(F.data.startswith("checkout:confirm:"))
async def cb_checkout_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    order_code = callback.data.split(":", 2)[2]
    await state.set_state(CheckoutStates.select_payment)
    await state.update_data(order_code=order_code)

    text = (
        f"💳 <b>SELECT PAYMENT METHOD</b>\n\n"
        f"Order: <code>{order_code}</code>\n\n"
        f"Choose your crypto payment method below.\n"
        f"All payments are final — accounts delivered within 2 hours."
    )
    await callback.message.edit_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=payment_method_kb(order_code),
    )
    await callback.answer()


# ── Step 3: Payment method selected → show wallet address ────────────────

@router.callback_query(F.data.startswith("pay:"))
async def cb_payment_method(callback: CallbackQuery, state: FSMContext) -> None:
    parts = callback.data.split(":", 2)
    currency = parts[1]  # BTC, ETH, USDT
    order_code = parts[2]

    wallet = WALLET_MAP.get(currency)
    if not wallet:
        await callback.answer("⚠️ Payment method not configured", show_alert=True)
        return

    order = get_order(order_code)
    if not order:
        await callback.answer("⚠️ Order not found", show_alert=True)
        return

    amount_usd = order["amount_usd"]

    # Get crypto conversion
    crypto_amount = amount_usd  # Default for USDT
    if currency == "BTC":
        price = await get_crypto_price("bitcoin")
        crypto_amount = amount_usd / price if price > 0 else 0
        amount_display = f"{crypto_amount:.8f} BTC"
    elif currency == "ETH":
        price = await get_crypto_price("ethereum")
        crypto_amount = amount_usd / price if price > 0 else 0
        amount_display = f"{crypto_amount:.6f} ETH"
    else:  # USDT
        amount_display = f"{amount_usd:,.2f} USDT"

    update_payment(order_code, currency, crypto_amount, wallet)
    await state.set_state(CheckoutStates.awaiting_payment)
    await state.update_data(order_code=order_code, currency=currency)

    network = NETWORK_NAMES.get(currency, currency)

    text = (
        f"💎 <b>PAYMENT DETAILS</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"🎫 Order: <code>{order_code}</code>\n"
        f"💰 Amount: <b>{amount_display}</b> (${amount_usd:,.0f})\n"
        f"🌐 Network: {network}\n\n"
        f"📬 Send to this address:\n"
        f"<code>{wallet}</code>\n\n"
        f"⚠️ <b>Important:</b>\n"
        f"• Send <b>exactly</b> {amount_display}\n"
        f"• Use <b>{network}</b> — wrong network = lost funds\n"
        f"• After sending, tap <b>\"I've Sent Payment\"</b> below\n\n"
        f"💡 Tap the address above to copy it."
    )

    await callback.message.edit_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=payment_sent_kb(order_code),
    )
    await callback.answer()


# ── Step 4: User says they sent payment → ask for tx hash ────────────────

@router.callback_query(F.data.startswith("checkout:sent:"))
async def cb_payment_sent(callback: CallbackQuery, state: FSMContext) -> None:
    order_code = callback.data.split(":", 2)[2]
    await state.set_state(CheckoutStates.awaiting_tx_hash)
    await state.update_data(order_code=order_code)

    text = (
        f"🔍 <b>VERIFY PAYMENT</b>\n\n"
        f"Order: <code>{order_code}</code>\n\n"
        f"Paste your <b>transaction hash</b> below.\n"
        f"I'll verify it on the blockchain instantly.\n\n"
        f"💡 You can find the TX hash in your wallet's transaction history."
    )

    await callback.message.edit_text(text, parse_mode=ParseMode.HTML)
    await callback.answer()


# ── Step 5: User pastes tx hash → verify on-chain ────────────────────────

@router.message(CheckoutStates.awaiting_tx_hash)
async def msg_tx_hash(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()

    # Clean up common copy-paste issues
    text = text.replace(" ", "").replace("\n", "")

    if not TX_HASH_RE.match(text):
        await message.answer(
            "⚠️ That doesn't look like a valid transaction hash.\n\n"
            "A TX hash is 64 hex characters (letters a-f and numbers 0-9).\n"
            "Example: <code>0xabc123...def456</code>\n\n"
            "Paste the correct hash or DM @Chris_Darton for help.",
            parse_mode=ParseMode.HTML,
        )
        return

    data = await state.get_data()
    order_code = data.get("order_code", "")
    currency = data.get("currency", "")

    order = get_order(order_code)
    if not order:
        await message.answer("⚠️ Order not found. Please start again or DM @Chris_Darton.")
        await state.clear()
        return

    # Save tx hash
    submit_tx_hash(order_code, text)

    await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    await message.answer(
        f"🔍 Verifying transaction on {NETWORK_NAMES.get(currency, currency)}...\n"
        f"TX: <code>{_shorten(text)}</code>",
        parse_mode=ParseMode.HTML,
    )

    wallet = WALLET_MAP.get(currency, "")
    amount_usd = order.get("amount_usd", 0)

    result = await verify_transaction(
        tx_hash=text,
        currency=currency,
        expected_address=wallet,
        min_amount_usd=amount_usd,
    )

    await _handle_verification_result(message, state, order_code, order, result, text, currency)


async def _handle_verification_result(
    message: Message,
    state: FSMContext,
    order_code: str,
    order: dict,
    result: TxResult,
    tx_hash: str,
    currency: str,
):
    """Process verification result and send appropriate response."""
    if result.status == "confirmed" and result.verified:
        # Check auto-confirm threshold
        if result.amount_usd > AUTO_CONFIRM_THRESHOLD:
            set_admin_review(order_code)
            await message.answer(
                f"✅ <b>Payment Detected!</b>\n\n"
                f"🎫 Order: <code>{order_code}</code>\n"
                f"💰 {result.amount_crypto:.6f} {result.currency} (${result.amount_usd:,.2f})\n"
                f"🔗 <a href=\"{_explorer_link(tx_hash, currency)}\">View on Explorer</a>\n\n"
                f"⏳ This order requires admin confirmation (amount > ${AUTO_CONFIRM_THRESHOLD:,.0f}).\n"
                f"Our team has been notified — you'll hear back shortly.",
                parse_mode=ParseMode.HTML,
            )
            # Refresh order for admin notification
            order = get_order(order_code) or order
            await _notify_admin_payment(message.bot, order, result)
        else:
            # Auto-confirm
            confirm_payment(order_code, result.amount_crypto, result.amount_usd)
            await message.answer(
                f"✅ <b>Payment Confirmed!</b>\n\n"
                f"🎫 Order: <code>{order_code}</code>\n"
                f"📦 {order.get('platform', 'Ad')} accounts — {order.get('niche', '')} niche\n"
                f"💰 {result.amount_crypto:.6f} {result.currency} (${result.amount_usd:,.2f})\n"
                f"🔗 <a href=\"{_explorer_link(tx_hash, currency)}\">View on Explorer</a>\n\n"
                f"⏱ <b>Your accounts will be ready within 2 hours.</b>\n"
                f"Our team has been notified and is preparing your order.\n\n"
                f"Need anything? Message here or DM @Chris_Darton.",
                parse_mode=ParseMode.HTML,
            )
            order = get_order(order_code) or order
            await _notify_admin_payment(message.bot, order, result)

        await state.clear()

    elif result.status == "pending":
        # Payment detected but not enough confirmations
        await message.answer(
            f"⏳ <b>Payment Detected — Awaiting Confirmations</b>\n\n"
            f"🎫 Order: <code>{order_code}</code>\n"
            f"💰 {result.amount_crypto:.6f} {result.currency}\n"
            f"🔄 Confirmations: {result.confirmations}/6\n\n"
            f"I'll check automatically every 2 minutes and notify you\n"
            f"when it's confirmed. Usually takes 10-30 minutes.\n\n"
            f"You can close this chat — I'll message you when it's done.",
            parse_mode=ParseMode.HTML,
        )
        await state.clear()
        # Start auto-recheck task
        _start_recheck(message.bot, message.chat.id, order_code, currency, tx_hash)

    elif result.status == "amount_mismatch":
        await message.answer(
            f"⚠️ <b>Amount Mismatch</b>\n\n"
            f"{result.error}\n\n"
            f"Please send the correct amount and paste the new TX hash,\n"
            f"or DM @Chris_Darton with order <code>{order_code}</code> for help.",
            parse_mode=ParseMode.HTML,
        )
        # Stay in awaiting_tx_hash state

    elif result.status == "not_found":
        await message.answer(
            f"❌ <b>Transaction Not Found</b>\n\n"
            f"TX <code>{_shorten(tx_hash)}</code> was not found on the blockchain.\n\n"
            f"This can happen if:\n"
            f"• The transaction is still broadcasting (wait a few minutes)\n"
            f"• The TX hash was copied incorrectly\n"
            f"• The wrong network was used\n\n"
            f"Try again in a few minutes, or paste a different TX hash.\n"
            f"Need help? DM @Chris_Darton with order <code>{order_code}</code>.",
            parse_mode=ParseMode.HTML,
        )
        # Stay in awaiting_tx_hash state

    else:
        await message.answer(
            f"⚠️ <b>Verification Error</b>\n\n"
            f"{result.error or 'Unknown error during verification'}\n\n"
            f"DM @Chris_Darton with order <code>{order_code}</code> and your TX hash\n"
            f"for manual verification.",
            parse_mode=ParseMode.HTML,
        )


# ── Cancel handler ───────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("checkout:cancel:"))
async def cb_checkout_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    order_code = callback.data.split(":", 2)[2]
    from payments.order_manager import get_order as _get
    order = _get(order_code)
    if order and order["status"] in ("pending_payment",):
        from payments.order_manager import _conn
        conn = _conn()
        conn.execute("UPDATE orders SET status = 'cancelled' WHERE order_code = ?", (order_code,))
        conn.commit()
        conn.close()
    await state.clear()
    await callback.message.edit_text(
        f"❌ Order <code>{order_code}</code> cancelled.\n\n"
        f"No worries — just message me when you're ready to order.",
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


# ── Modify handler ───────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("checkout:modify:"))
async def cb_checkout_modify(callback: CallbackQuery, state: FSMContext) -> None:
    order_code = callback.data.split(":", 2)[2]
    await state.clear()
    # Cancel the current order
    from payments.order_manager import _conn
    conn = _conn()
    conn.execute("UPDATE orders SET status = 'cancelled' WHERE order_code = ?", (order_code,))
    conn.commit()
    conn.close()
    await callback.message.edit_text(
        f"✏️ Order <code>{order_code}</code> cancelled.\n\n"
        f"Tell me what you'd like to change — platform, budget, niche — "
        f"and I'll set up a new order for you.",
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


# ── Admin approve/reject ─────────────────────────────────────────────────

@router.callback_query(F.data.startswith("admin:approve:"))
async def cb_admin_approve(callback: CallbackQuery) -> None:
    order_code = callback.data.split(":", 2)[2]
    from payments.order_manager import admin_confirm as _confirm, get_order as _get
    _confirm(order_code, confirmed=True)
    order = _get(order_code)

    await callback.message.edit_text(
        callback.message.text + "\n\n✅ <b>APPROVED</b> by admin",
        parse_mode=ParseMode.HTML,
    )
    await callback.answer("Order approved ✅")

    # Notify the client
    if order:
        try:
            await callback.bot.send_message(
                order["user_id"],
                f"✅ <b>Payment Confirmed!</b>\n\n"
                f"🎫 Order: <code>{order_code}</code>\n"
                f"⏱ <b>Your accounts will be ready within 2 hours.</b>\n"
                f"Our team is preparing your order now.\n\n"
                f"Need anything? DM @Chris_Darton.",
                parse_mode=ParseMode.HTML,
            )
        except Exception as exc:
            log.warning("Failed to notify client uid=%s: %s", order.get("user_id"), exc)


@router.callback_query(F.data.startswith("admin:reject:"))
async def cb_admin_reject(callback: CallbackQuery) -> None:
    order_code = callback.data.split(":", 2)[2]
    from payments.order_manager import admin_confirm as _confirm, get_order as _get
    _confirm(order_code, confirmed=False)
    order = _get(order_code)

    await callback.message.edit_text(
        callback.message.text + "\n\n❌ <b>REJECTED</b> by admin",
        parse_mode=ParseMode.HTML,
    )
    await callback.answer("Order rejected ❌")

    if order:
        try:
            await callback.bot.send_message(
                order["user_id"],
                f"⚠️ <b>Order Update</b>\n\n"
                f"Order <code>{order_code}</code> could not be confirmed.\n"
                f"Please DM @Chris_Darton to resolve this.",
                parse_mode=ParseMode.HTML,
            )
        except Exception as exc:
            log.warning("Failed to notify client uid=%s: %s", order.get("user_id"), exc)


# ── Auto-recheck loop for pending transactions ──────────────────────────

def _start_recheck(bot, chat_id: int, order_code: str, currency: str, tx_hash: str):
    """Start a background task to recheck a pending tx every 2 minutes."""
    key = f"{order_code}:{tx_hash}"
    if key in _verification_tasks:
        return
    task = asyncio.create_task(_recheck_loop(bot, chat_id, order_code, currency, tx_hash))
    _verification_tasks[key] = task


async def _recheck_loop(bot, chat_id: int, order_code: str, currency: str, tx_hash: str):
    """Check pending tx every 2 min for up to 30 min."""
    key = f"{order_code}:{tx_hash}"
    wallet = WALLET_MAP.get(currency, "")
    order = get_order(order_code)
    amount_usd = order.get("amount_usd", 0) if order else 0

    for attempt in range(15):  # 15 × 2min = 30 min
        await asyncio.sleep(120)

        result = await verify_transaction(tx_hash, currency, wallet, amount_usd)

        if result.status == "confirmed" and result.verified:
            # Payment confirmed!
            if amount_usd <= AUTO_CONFIRM_THRESHOLD:
                confirm_payment(order_code, result.amount_crypto, result.amount_usd)
                try:
                    await bot.send_message(
                        chat_id,
                        f"✅ <b>Payment Confirmed!</b>\n\n"
                        f"🎫 Order: <code>{order_code}</code>\n"
                        f"💰 {result.amount_crypto:.6f} {result.currency} (${result.amount_usd:,.2f})\n\n"
                        f"⏱ <b>Your accounts will be ready within 2 hours.</b>\n"
                        f"Our team has been notified.\n\n"
                        f"Need anything? DM @Chris_Darton.",
                        parse_mode=ParseMode.HTML,
                    )
                except Exception:
                    pass
            else:
                set_admin_review(order_code)
                try:
                    await bot.send_message(
                        chat_id,
                        f"✅ Payment detected for <code>{order_code}</code>!\n"
                        f"Admin confirmation in progress — you'll hear back shortly.",
                        parse_mode=ParseMode.HTML,
                    )
                except Exception:
                    pass

            order = get_order(order_code) or order or {}
            await _notify_admin_payment(bot, order, result)
            break

    _verification_tasks.pop(key, None)


# ── Budget parser ────────────────────────────────────────────────────────

def _parse_budget_amount(budget_str: str) -> float:
    """Parse BANT budget string to a numeric USD amount."""
    s = budget_str.lower().replace(",", "").replace("$", "").strip()

    # Direct number
    m = re.search(r"(\d+(?:\.\d+)?)\s*k", s)
    if m:
        return float(m.group(1)) * 1000

    m = re.search(r"(\d+(?:\.\d+)?)", s)
    if m:
        val = float(m.group(1))
        return val if val > 100 else val * 1000

    # Range midpoints
    ranges = {
        "< $1k": 500, "<1k": 500, "under 1k": 500,
        "$1k-$5k": 3000, "1k-5k": 3000,
        "$5k-$10k": 7500, "5k-10k": 7500,
        "$10k-$50k": 25000, "10k-50k": 25000,
        "$50k+": 50000, "50k+": 50000,
    }
    for key, val in ranges.items():
        if key in budget_str.lower():
            return val

    return 0  # Unknown budget — let user specify
