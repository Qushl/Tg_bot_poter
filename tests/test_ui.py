import unittest

from handlers import router
from keyboards import CAMPUSES, campus_keyboard, main_menu, pagination_keyboard


class UiTests(unittest.TestCase):
    def test_expected_campuses_are_available(self) -> None:
        campus_names = set(CAMPUSES.values())
        for expected in ("ГУК (Мира, 19)", "Теплофак (С. Ковалевской, 5)", "Радиофак (Мира, 32)"):
            self.assertIn(expected, campus_names)

    def test_all_callback_data_fits_telegram_limit(self) -> None:
        markups = [
            campus_keyboard("create_campus"),
            campus_keyboard("browse_campus"),
            pagination_keyboard(1, 3, "Екатеринбург", "ГУК (Мира, 19)"),
        ]
        callback_values = [
            button.callback_data
            for markup in markups
            for row in markup.inline_keyboard
            for button in row
            if button.callback_data
        ]
        self.assertTrue(callback_values)
        self.assertTrue(all(len(value.encode()) <= 64 for value in callback_values))

    def test_main_menu_contains_required_actions(self) -> None:
        labels = {button.text for row in main_menu().keyboard for button in row}
        self.assertEqual(
            labels,
            {"Загрузить потеряшку", "Загрузить находку", "Смотреть объявления", "Мои объявления"},
        )

    def test_router_has_handlers(self) -> None:
        self.assertGreaterEqual(len(router.message.handlers), 10)
        self.assertGreaterEqual(len(router.callback_query.handlers), 10)

