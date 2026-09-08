import math
from html import escape

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from database import Item
from keyboards import (
    CAMPUSES,
    campus_keyboard,
    close_keyboard,
    confirm_keyboard,
    contact_keyboard,
    main_menu,
    pagination_keyboard,
)
from repository import Repository
from states import CityFilter, CreateItem, KeywordSearch

router = Router()
PER_PAGE = 5


def item_caption(item: Item, include_contact: bool = True) -> str:
    item_type = "Потеряно" if item.type == "lost" else "Найдено"
    lines = [
        f"<b>{item_type}</b>",
        f"<b>{escape(item.title)}</b>",
        escape(item.description),
        f"📍 {escape(item.city)}",
        f"🏫 {escape(item.campus)}",
        f"📅 {item.created_at:%d.%m.%Y}",
    ]
    if include_contact:
        lines.append(f"Контакт: {escape(item.contact)}")
    return "\n\n".join(lines)


@router.message(CommandStart())
async def start(message: Message, state: FSMContext, repo: Repository) -> None:
    await state.clear()
    user = message.from_user
    if user:
        await repo.upsert_user(user.id, user.username, user.full_name)
    await message.answer(
        "Добро пожаловать в «Потеряшки»! Здесь можно разместить и найти объявления о потерянных вещах.",
        reply_markup=main_menu(),
    )


@router.message(F.text.in_({"Загрузить потеряшку", "Загрузить находку"}))
async def begin_item(message: Message, state: FSMContext, repo: Repository) -> None:
    user = message.from_user
    if not user:
        return
    await repo.upsert_user(user.id, user.username, user.full_name)
    await state.clear()
    await state.update_data(type="lost" if message.text == "Загрузить потеряшку" else "found")
    await state.set_state(CreateItem.campus)
    await message.answer(
        "Выберите кампус или площадку УрФУ.",
        reply_markup=campus_keyboard("create_campus"),
    )


@router.callback_query(CreateItem.campus, F.data.startswith("create_campus:"))
async def select_item_campus(callback: CallbackQuery, state: FSMContext) -> None:
    code = callback.data.split(":", 1)[1]
    campus = CAMPUSES.get(code)
    if not campus:
        await callback.answer("Неизвестная площадка", show_alert=True)
        return
    await state.update_data(campus=campus)
    await state.set_state(CreateItem.photo)
    if callback.message:
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer("Отправьте одну фотографию вещи.", reply_markup=ReplyKeyboardRemove())
    await callback.answer()


@router.message(CreateItem.photo, F.photo)
async def receive_photo(message: Message, state: FSMContext) -> None:
    await state.update_data(photo_file_id=message.photo[-1].file_id)
    await state.set_state(CreateItem.title)
    await message.answer("Введите короткий заголовок объявления (до 120 символов).")


@router.message(CreateItem.title, F.text)
async def receive_title(message: Message, state: FSMContext) -> None:
    title = message.text.strip()
    if not 3 <= len(title) <= 120:
        await message.answer("Заголовок должен содержать от 3 до 120 символов.")
        return
    await state.update_data(title=title)
    await state.set_state(CreateItem.description)
    await message.answer("Введите описание вещи.")


@router.message(CreateItem.photo)
async def photo_required(message: Message) -> None:
    await message.answer("Фотография обязательна. Пожалуйста, отправьте фото как изображение.")


@router.message(CreateItem.description, F.text)
async def receive_description(message: Message, state: FSMContext) -> None:
    description = message.text.strip()
    if not 10 <= len(description) <= 1500:
        await message.answer("Описание должно содержать от 10 до 1500 символов.")
        return
    await state.update_data(description=description)
    await state.set_state(CreateItem.city)
    await message.answer("Укажите город / район.")


@router.message(CreateItem.city, F.text)
async def receive_city(message: Message, state: FSMContext) -> None:
    await state.update_data(city=message.text.strip())
    await state.set_state(CreateItem.contact)
    await message.answer("Введите телефон или нажмите «Написать в бот».", reply_markup=contact_keyboard())


@router.message(CreateItem.contact, F.text)
async def receive_contact(message: Message, state: FSMContext) -> None:
    contact = message.text.strip()
    if contact == "Написать в бот":
        user = message.from_user
        contact = f"@{user.username}" if user and user.username else f"tg://user?id={user.id}"
    await state.update_data(contact=contact)
    data = await state.get_data()
    preview = Item(
        user_id=message.from_user.id,
        type=data["type"],
        photo_file_id=data["photo_file_id"],
        title=data["title"],
        description=data["description"],
        city=data["city"],
        campus=data["campus"],
        contact=contact,
    )
    from datetime import datetime
    preview.created_at = datetime.now()
    await state.set_state(CreateItem.confirm)
    await message.answer_photo(
        data["photo_file_id"], caption=item_caption(preview), reply_markup=confirm_keyboard()
    )


@router.callback_query(CreateItem.confirm, F.data == "item:publish")
async def publish_item(callback: CallbackQuery, state: FSMContext, repo: Repository) -> None:
    data = await state.get_data()
    try:
        await repo.create_item(callback.from_user.id, {
            key: data[key] for key in (
                "type", "photo_file_id", "title", "description", "city", "campus", "contact"
            )
        })
    except ValueError as error:
        await callback.answer(str(error), show_alert=True)
        return
    await state.clear()
    if callback.message:
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer("Объявление опубликовано.", reply_markup=main_menu())
    await callback.answer()


@router.callback_query(CreateItem.confirm, F.data == "item:cancel")
async def cancel_item(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if callback.message:
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer("Создание объявления отменено.", reply_markup=main_menu())
    await callback.answer()


async def send_items(message: Message, repo: Repository, state: FSMContext, page: int) -> None:
    data = await state.get_data()
    city = data.get("filter_city")
    campus = data.get("filter_campus")
    query = data.get("search_query")
    items, total = await repo.active_items(page, PER_PAGE, city, campus, query)
    total_pages = max(1, math.ceil(total / PER_PAGE))
    if page >= total_pages:
        page = total_pages - 1
        items, total = await repo.active_items(page, PER_PAGE, city, campus, query)
    if not items:
        if campus:
            empty_text = (
                f"В месте «{escape(campus)}» пока нет опубликованных "
                "объявлений о потерянных или найденных вещах."
            )
        elif city:
            empty_text = (
                f"В городе или районе «{escape(city)}» пока нет опубликованных "
                "объявлений о потерянных или найденных вещах."
            )
        elif query:
            empty_text = f"По запросу «{escape(query)}» ничего не найдено."
        else:
            empty_text = "Пока нет опубликованных объявлений о потерянных или найденных вещах."
        await message.answer(
            empty_text,
            reply_markup=pagination_keyboard(0, 1, city, campus),
        )
        return
    for item in items:
        await message.answer_photo(item.photo_file_id, caption=item_caption(item))
    filters = [value for value in (campus, city, query) if value]
    suffix = f" · фильтр: {', '.join(filters)}" if filters else ""
    await message.answer(
        f"Страница {page + 1} из {total_pages}{suffix}",
        reply_markup=pagination_keyboard(page, total_pages, city, campus),
    )


@router.message(F.text == "Смотреть объявления")
async def browse(message: Message, state: FSMContext, repo: Repository) -> None:
    await state.clear()
    await send_items(message, repo, state, 0)


@router.message(F.text == "Умный поиск")
async def request_search(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(KeywordSearch.query)
    await message.answer(
        "Введите ключевые слова, например: «чёрный рюкзак радиофак» или «студенческий билет»."
    )


@router.message(KeywordSearch.query, F.text)
async def apply_search(message: Message, state: FSMContext, repo: Repository) -> None:
    query = message.text.strip()
    if len(query) < 2:
        await message.answer("Введите хотя бы два символа для поиска.")
        return
    await state.update_data(search_query=query)
    await state.set_state(None)
    await send_items(message, repo, state, 0)


@router.callback_query(F.data.startswith("browse:"))
async def browse_page(callback: CallbackQuery, state: FSMContext, repo: Repository) -> None:
    page = int(callback.data.split(":")[1])
    if callback.message:
        await callback.message.delete()
        await send_items(callback.message, repo, state, page)
    await callback.answer()


@router.callback_query(F.data == "filter:city")
async def request_city(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(CityFilter.city)
    if callback.message:
        await callback.message.answer("Введите город или район для фильтра.")
    await callback.answer()


@router.callback_query(F.data == "filter:campus")
async def request_campus(callback: CallbackQuery) -> None:
    if callback.message:
        await callback.message.answer(
            "Выберите кампус или площадку УрФУ:",
            reply_markup=campus_keyboard("browse_campus"),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("browse_campus:"))
async def apply_campus(callback: CallbackQuery, state: FSMContext, repo: Repository) -> None:
    code = callback.data.split(":", 1)[1]
    campus = CAMPUSES.get(code)
    if not campus:
        await callback.answer("Неизвестная площадка", show_alert=True)
        return
    await state.update_data(filter_campus=campus)
    if callback.message:
        await callback.message.delete()
        await send_items(callback.message, repo, state, 0)
    await callback.answer()


@router.callback_query(F.data == "filter:campus_reset")
async def reset_campus(callback: CallbackQuery, state: FSMContext, repo: Repository) -> None:
    await state.update_data(filter_campus=None)
    if callback.message:
        await callback.message.delete()
        await send_items(callback.message, repo, state, 0)
    await callback.answer("Фильтр кампуса сброшен")


@router.message(CityFilter.city, F.text)
async def apply_city(message: Message, state: FSMContext, repo: Repository) -> None:
    await state.update_data(filter_city=message.text.strip())
    await state.set_state(None)
    await send_items(message, repo, state, 0)


@router.callback_query(F.data == "filter:reset")
async def reset_city(callback: CallbackQuery, state: FSMContext, repo: Repository) -> None:
    await state.update_data(filter_city=None)
    if callback.message:
        await callback.message.delete()
        await send_items(callback.message, repo, state, 0)
    await callback.answer("Фильтр сброшен")


@router.message(F.text == "Мои объявления")
async def my_items(message: Message, repo: Repository) -> None:
    items = await repo.user_items(message.from_user.id)
    if not items:
        await message.answer("У вас пока нет объявлений.")
        return
    for item in items:
        status = "активно" if item.status == "active" else "закрыто"
        markup = close_keyboard(item.id) if item.status == "active" else None
        await message.answer_photo(item.photo_file_id, caption=f"{item_caption(item)}\n\nСтатус: {status}", reply_markup=markup)


@router.callback_query(F.data.startswith("close:"))
async def close_item(callback: CallbackQuery, repo: Repository) -> None:
    item_id = int(callback.data.split(":")[1])
    closed = await repo.close_item(item_id, callback.from_user.id)
    if closed and callback.message:
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer("Объявление закрыто.")
    await callback.answer("Готово" if closed else "Объявление уже закрыто", show_alert=not closed)
