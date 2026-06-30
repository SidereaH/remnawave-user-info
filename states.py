from aiogram.fsm.state import State, StatesGroup


class ExtendStates(StatesGroup):
    waiting_for_date = State()
