from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


CAMPUSES = {
    "guk": "ГУК (Мира, 19)",
    "electro": "Электрофак (Мира, 19)",
    "stroy": "Стройфак (Мира, 17)",
    "teplo": "Теплофак (С. Ковалевской, 5)",
    "radio": "Радиофак (Мира, 32)",
    "phys": "Физтех (Мира, 21)",
    "third": "Третий учебный (Мира, 28)",
    "upish": "УПИШ (С. Ковалевской, 6Б)",
    "kuba": "Куба (Куйбышева, 48)",
    "novokol": "Новокольцовский",
    "center": "Другой корпус в центре",
    "dorms": "Общежития УрФУ",
    "sport": "Спортивные корпуса УрФУ",
    "other": "Другое место",
}


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Загрузить потеряшку"), KeyboardButton(text="Загрузить находку")],
            [KeyboardButton(text="Смотреть объявления"), KeyboardButton(text="Умный поиск")],
            [KeyboardButton(text="Мои объявления")],
        ],
        resize_keyboard=True,
    )


def contact_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Написать в бот")]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Опубликовать", callback_data="item:publish"),
                InlineKeyboardButton(text="Отмена", callback_data="item:cancel"),
            ]
        ]
    )


def campus_keyboard(prefix: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for code, title in CAMPUSES.items():
        builder.button(text=title, callback_data=f"{prefix}:{code}")
    builder.adjust(1)
    return builder.as_markup()


def pagination_keyboard(
    page: int, total_pages: int, city: str | None, campus: str | None
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if page > 0:
        builder.button(text="← Назад", callback_data=f"browse:{page - 1}")
    if page + 1 < total_pages:
        builder.button(text="Вперёд →", callback_data=f"browse:{page + 1}")
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="Выбрать кампус УрФУ", callback_data="filter:campus"))
    builder.row(InlineKeyboardButton(text="Доп. фильтр по городу/району", callback_data="filter:city"))
    if campus:
        builder.row(InlineKeyboardButton(text="Сбросить кампус", callback_data="filter:campus_reset"))
    if city:
        builder.row(InlineKeyboardButton(text="Сбросить фильтр", callback_data="filter:reset"))
    return builder.as_markup()


def close_keyboard(item_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Закрыть объявление", callback_data=f"close:{item_id}")]]
    )
