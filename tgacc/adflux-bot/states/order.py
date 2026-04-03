from aiogram.fsm.state import State, StatesGroup


class OrderStates(StatesGroup):
    platform = State()
    niche = State()
    budget = State()
    timing = State()
    contact = State()
