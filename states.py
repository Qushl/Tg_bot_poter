from aiogram.fsm.state import State, StatesGroup


class CreateItem(StatesGroup):
    campus = State()
    photo = State()
    description = State()
    city = State()
    contact = State()
    confirm = State()


class CityFilter(StatesGroup):
    city = State()
