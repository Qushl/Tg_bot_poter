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
    item_type = "📌 Потеряно" if item.type == "lost" else "🎁 Найдено"
    lines = [
        f"<b>{item_type}</b>",
        f"<b>{escape(item.title)}</b>",
        escape(item.description),
        f"📍 <b>Локация:</b> {escape(item.city)}",
        f"🏫 <b>Корпус/Площадка:</b> {escape(item.campus)}",
        f"📅 <b>Дата публикации:</b> {item.created_at:%d.%m.%Y}",
    ]
    if include_contact:
        lines.append(f"📞 <b>Контакт для связи:</b> {escape(item.contact)}")
    return "\n\n".join(lines)


@router.message(CommandStart())
async def start(message: Message, state: FSMContext, repo: Repository) -> None:
    await state.clear()
    user = message.from_user
    if user:
        await repo.upsert_user(user.id, user.username, user.full_name)
    await message.answer(
        "Добро пожаловать в бот <b>«Потеряшки УрФУ»</b>! 👋✨\n\n"
        "Потеряли ключи по дороге в аудиторию? Нашли чью-то студенческую карту, "
        "наушники или любимую толстовку? Не волнуйтесь — вы попали по адресу! "
        "Наш бот создан для того, чтобы помочь студентам, преподавателям и "
        "сотрудникам университета быстро находить потерянные вещи и возвращать их владельцам.\n\n"
        "<b>Чем я могу вам помочь?</b>\n"
        "• <b>📦 Добавить находку:</b> Нашли чужую вещь? Внесите её в базу за пару шагов, чтобы хозяин мог легко с вами связаться.\n"
        "• <b>🔍 Найти потерянное:</b> Проверьте список недавних находок или воспользуйтесь поиском по корпусам — возможно, ваша вещь уже ждёт вас!\n"
        "• <b>🏫 Навигация по корпусам:</b> Все объявления удобно разделены по учебным зданиям и территории УрФУ.\n\n"
        "Выберите нужное действие в меню ниже, чтобы начать! 👇",
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
        "🏫 <b>Шаг 1 из 6: Локация</b>\n\n"
        "Укажите, в каком корпусе или на какой площадке УрФУ была найдена (или потеряна) вещь:",
        reply_markup=campus_keyboard("create_campus"),
    )


@router.callback_query(CreateItem.campus, F.data.startswith("create_campus:"))
async def select_item_campus(callback: CallbackQuery, state: FSMContext) -> None:
    code = callback.data.split(":", 1)[1]
    campus = CAMPUSES.get(code)
    if not campus:
        await callback.answer("⚠️ Ой, кажется, эта площадка не найдена. Попробуйте выбрать ещё раз!", show_alert=True)
        return
    await state.update_data(campus=campus)
    await state.set_state(CreateItem.photo)
    if callback.message:
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(
            "📸 <b>Шаг 2 из 6: Фотография</b>\n\n"
            "Отправьте <b>одно чёткое фото</b> вещи. Это сильно поможет владельцу быстрее её узнать!",
            reply_markup=ReplyKeyboardRemove()
        )
    await callback.answer()


@router.message(CreateItem.photo, F.photo)
async def receive_photo(message: Message, state: FSMContext) -> None:
    await state.update_data(photo_file_id=message.photo[-1].file_id)
    await state.set_state(CreateItem.title)
    await message.answer(
        "✏️ <b>Шаг 3 из 6: Заголовок</b>\n\n"
        "Напишите короткое название объявления (до 120 символов).\n"
        "<i>Пример: «Найдены чёрные ключи с синим брелоком»</i>"
    )


@router.message(CreateItem.title, F.text)
async def receive_title(message: Message, state: FSMContext) -> None:
    title = message.text.strip()
    if not 3 <= len(title) <= 120:
        await message.answer("⚠️ Пожалуйста, сделайте заголовок немного информативнее — от 3 до 120 символов.")
        return
    await state.update_data(title=title)
    await state.set_state(CreateItem.description)
    await message.answer(
        "📝 <b>Шаг 4 из 6: Подробности</b>\n\n"
        "Опишите вещь подробнее. Укажите этаж, номер аудитории или ориентиры места, где она находится."
    )


@router.message(CreateItem.photo)
async def photo_required(message: Message) -> None:
    await message.answer("📸 Нам очень нужно фото вещи, чтобы всё получилось! Пожалуйста, отправьте его как обычное изображение.")


@router.message(CreateItem.description, F.text)
async def receive_description(message: Message, state: FSMContext) -> None:
    description = message.text.strip()
    if not 10 <= len(description) <= 1500:
        await message.answer("⚠️ Напишите чуть подробнее (хотя бы 10 символов), чтобы описания хватило для распознавания вещи!")
        return
    await state.update_data(description=description)
    await state.set_state(CreateItem.city)
    await message.answer(
        "📍 <b>Шаг 5 из 6: Город и район</b>\n\n"
        "Уточните город и район (например: <i>Екатеринбург, Втузгородок</i>)."
    )


@router.message(CreateItem.city, F.text)
async def receive_city(message: Message, state: FSMContext) -> None:
    await state.update_data(city=message.text.strip())
    await state.set_state(CreateItem.contact)
    await message.answer(
        "📞 <b>Шаг 6 из 6: Контакты</b>\n\n"
        "Как с вами связаться? Напишите номер телефона или нажмите кнопку ниже, "
        "чтобы пользователи могли написать вам прямо через бота.",
        reply_markup=contact_keyboard()
    )


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
    await message.answer(
        "✨ <b>Почти готово! Проверьте, всё ли верно:</b>",
        reply_markup=ReplyKeyboardRemove()
    )
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
        await callback.answer(f"⚠️ Ошибка публикации: {error}", show_alert=True)
        return
    await state.clear()
    if callback.message:
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(
            "🎉 <b>Ура! Ваше объявление успешно опубликовано!</b>\n\n"
            "Надеемся, вещь очень быстро найдёт своего хозяина. Спасибо за помощь!",
            reply_markup=main_menu()
        )
    await callback.answer()


@router.callback_query(CreateItem.confirm, F.data == "item:cancel")
async def cancel_item(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if callback.message:
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(
            "👌 Публикация отменена. Ничего страшного, вы всегда можете попробовать снова!",
            reply_markup=main_menu()
        )
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
                f"🌱 В локации <b>«{escape(campus)}»</b> пока нет активных объявлений. "
                "Если вы что-то нашли там — будьте первыми, кто добавит!"
            )
        elif city:
            empty_text = (
                f"🏙️ По запросу в районе/городе <b>«{escape(city)}»</b> ничего не найдено. "
                "Попробуйте сбросить фильтр или заглянуть позже."
            )
        elif query:
            empty_text = f"🔍 По ключевому слову <b>«{escape(query)}»</b> совпадений не найдено. Попробуйте сформулировать иначе."
        else:
            empty_text = "✨ Здесь пока пустует! Пока нет активных объявлений о потерянных или найденных вещах."
        await message.answer(
            empty_text,
            reply_markup=pagination_keyboard(0, 1, city, campus),
        )
        return
    for item in items:
        await message.answer_photo(item.photo_file_id, caption=item_caption(item))
    filters = [value for value in (campus, city, query) if value]
    suffix = f" · 🔍 фильтр: {', '.join(filters)}" if filters else ""
    await message.answer(
        f"📖 <b>Страница {page + 1} из {total_pages}</b>{suffix}",
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
        "🔎 <b>Умный поиск</b>\n\n"
        "Напишите ключевые слова для поиска (например: <i>«чёрный рюкзак радиофак»</i> или <i>«студенческий билет»</i>):"
    )


@router.message(KeywordSearch.query, F.text)
async def apply_search(message: Message, state: FSMContext, repo: Repository) -> None:
    query = message.text.strip()
    if len(query) < 2:
        await message.answer("⚠️ Пожалуйста, введите хотя бы 2 символа для точного поиска.")
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
        await callback.message.answer("📍 Напишите название города или района для фильтрации результатов:")
    await callback.answer()


@router.callback_query(F.data == "filter:campus")
async def request_campus(callback: CallbackQuery) -> None:
    if callback.message:
        await callback.message.answer(
            "🏫 Нажмите на корпус или площадки УрФУ, чтобы отфильтровать объявления:",
            reply_markup=campus_keyboard("browse_campus"),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("browse_campus:"))
async def apply_campus(callback: CallbackQuery, state: FSMContext, repo: Repository) -> None:
    code = callback.data.split(":", 1)[1]
    campus = CAMPUSES.get(code)
    if not campus:
        await callback.answer("⚠️ Выбранная площадка не найдена", show_alert=True)
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
    await callback.answer("✅ Фильтр по корпусу сброшен")


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
    await callback.answer("✅ Фильтр по городу сброшен")


@router.message(F.text == "Мои объявления")
async def my_items(message: Message, repo: Repository) -> None:
    items = await repo.user_items(message.from_user.id)
    if not items:
        await message.answer(
            "📋 <b>У вас пока нет публикаций.</b>\n\n"
            "Если вы что-то потеряли или нашли, нажмите кнопку отправки в главном меню!"
        )
        return
    for item in items:
        status = "🟢 Активно" if item.status == "active" else "🔴 Закрыто"
        markup = close_keyboard(item.id) if item.status == "active" else None
        await message.answer_photo(
            item.photo_file_id,
            caption=f"{item_caption(item)}\n\n⚙️ <b>Статус:</b> {status}",
            reply_markup=markup
        )


@router.callback_query(F.data.startswith("close:"))
async def close_item(callback: CallbackQuery, repo: Repository) -> None:
    item_id = int(callback.data.split(":")[1])
    closed = await repo.close_item(item_id, callback.from_user.id)
    if closed and callback.message:
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer("🎉 Объявление успешно закрыто! Рады, что вещь вернулась на своё место.")
    await callback.answer("Готово!" if closed else "Объявление уже было закрыто ранее", show_alert=not closed)