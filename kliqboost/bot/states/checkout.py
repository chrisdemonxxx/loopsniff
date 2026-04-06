"""Checkout FSM states."""

from aiogram.fsm.state import State, StatesGroup


class CheckoutStates(StatesGroup):
    confirm_order = State()
    select_payment = State()
    awaiting_payment = State()
    awaiting_tx_hash = State()
    verifying = State()
