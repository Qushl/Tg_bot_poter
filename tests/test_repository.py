import tempfile
import unittest
from pathlib import Path

from database import Database
from repository import Repository


class RepositoryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(self.temp_dir.name) / "test.db"
        self.database = Database(f"sqlite+aiosqlite:///{db_path}")
        await self.database.create_tables()
        self.repo = Repository(self.database)
        await self.repo.upsert_user(1, "owner", "Owner")
        await self.repo.upsert_user(2, "stranger", "Stranger")

    async def asyncTearDown(self) -> None:
        await self.database.close()
        self.temp_dir.cleanup()

    async def create_item(
        self, *, campus: str = "Радиофак (Мира, 32)", city: str = "Екатеринбург",
        user_id: int = 1,
    ):
        return await self.repo.create_item(
            user_id,
            {
                "type": "lost",
                "photo_file_id": "telegram-file-id",
                "title": f"Рюкзак {campus} {city}",
                "description": "Чёрный рюкзак",
                "city": city,
                "campus": campus,
                "contact": "@owner",
            },
        )

    async def test_create_and_read_item(self) -> None:
        created = await self.create_item()
        items, total = await self.repo.active_items(0, 5)
        self.assertGreater(created.id, 0)
        self.assertEqual(total, 1)
        self.assertEqual(items[0].campus, "Радиофак (Мира, 32)")

    async def test_filters_by_campus_and_city(self) -> None:
        await self.create_item()
        await self.create_item(campus="ГУК (Мира, 19)", city="Екатеринбург, Втузгородок")
        _, radio_total = await self.repo.active_items(0, 5, campus="Радиофак (Мира, 32)")
        _, city_total = await self.repo.active_items(0, 5, city="Втузгородок")
        _, missing_total = await self.repo.active_items(0, 5, campus="Куба (Куйбышева, 48)")
        self.assertEqual((radio_total, city_total, missing_total), (1, 1, 0))

    async def test_keyword_search(self) -> None:
        await self.create_item(campus="Радиофак (Мира, 32)")
        _, found = await self.repo.active_items(0, 5, query="чёрный радиофак")
        _, missing = await self.repo.active_items(0, 5, query="красный зонт")
        self.assertEqual((found, missing), (1, 0))

    async def test_duplicate_is_rejected(self) -> None:
        await self.create_item()
        with self.assertRaisesRegex(ValueError, "уже опубликовано"):
            await self.create_item()

    async def test_pagination(self) -> None:
        for user_id in range(10, 16):
            await self.repo.upsert_user(user_id, f"user{user_id}", f"User {user_id}")
            await self.create_item(user_id=user_id)
        first, total = await self.repo.active_items(0, 5)
        second, _ = await self.repo.active_items(1, 5)
        self.assertEqual(total, 6)
        self.assertEqual((len(first), len(second)), (5, 1))

    async def test_only_owner_can_close_item(self) -> None:
        item = await self.create_item()
        self.assertFalse(await self.repo.close_item(item.id, 2))
        self.assertTrue(await self.repo.close_item(item.id, 1))
        self.assertFalse(await self.repo.close_item(item.id, 1))
        _, active_total = await self.repo.active_items(0, 5)
        self.assertEqual(active_total, 0)

    async def test_user_update_and_own_items(self) -> None:
        await self.create_item()
        await self.repo.upsert_user(1, "new_owner", "New Owner")
        items = await self.repo.user_items(1)
        self.assertEqual(len(items), 1)
