from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_, select, update

from database import Database, Item, User


class Repository:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def upsert_user(self, telegram_id: int, username: str | None, full_name: str) -> None:
        async with self.database.session_factory() as session:
            user = await session.get(User, telegram_id)
            if user is None:
                session.add(User(telegram_id=telegram_id, username=username, full_name=full_name))
            else:
                user.username = username
                user.full_name = full_name
            await session.commit()

    async def create_item(self, user_id: int, data: dict[str, str]) -> Item:
        async with self.database.session_factory() as session:
            recent = datetime.now(timezone.utc) - timedelta(minutes=2)
            recent_count = await session.scalar(
                select(func.count(Item.id)).where(Item.user_id == user_id, Item.created_at >= recent)
            ) or 0
            if recent_count >= 3:
                raise ValueError("Слишком много объявлений. Попробуйте снова через пару минут.")
            duplicate = await session.scalar(
                select(Item.id).where(
                    Item.user_id == user_id,
                    Item.status == "active",
                    Item.title == data["title"],
                    Item.description == data["description"],
                ).limit(1)
            )
            if duplicate:
                raise ValueError("Такое активное объявление уже опубликовано.")
            item = Item(user_id=user_id, **data)
            session.add(item)
            await session.commit()
            await session.refresh(item)
            return item

    async def active_items(
        self, page: int, per_page: int, city: str | None = None,
        campus: str | None = None, query: str | None = None,
    ) -> tuple[list[Item], int]:
        await self.close_expired_items()
        filters = [Item.status == "active"]
        if city:
            filters.append(Item.city.ilike(f"%{city}%"))
        if campus:
            filters.append(Item.campus == campus)
        if query:
            words = [word.strip() for word in query.split() if len(word.strip()) >= 2]
            for word in words:
                patterns = {f"%{word}%", f"%{word.capitalize()}%", f"%{word.upper()}%"}
                filters.append(or_(*[
                    column.like(pattern)
                    for column in (Item.title, Item.description, Item.city, Item.campus)
                    for pattern in patterns
                ]))
        async with self.database.session_factory() as session:
            total = await session.scalar(select(func.count(Item.id)).where(*filters)) or 0
            result = await session.scalars(
                select(Item)
                .where(*filters)
                .order_by(Item.created_at.desc())
                .offset(page * per_page)
                .limit(per_page)
            )
            return list(result), total

    async def close_expired_items(self) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        async with self.database.session_factory() as session:
            result = await session.execute(
                update(Item).where(Item.status == "active", Item.created_at < cutoff).values(status="closed")
            )
            await session.commit()
            return result.rowcount or 0

    async def user_items(self, user_id: int) -> list[Item]:
        await self.close_expired_items()
        async with self.database.session_factory() as session:
            result = await session.scalars(
                select(Item).where(Item.user_id == user_id).order_by(Item.created_at.desc())
            )
            return list(result)

    async def close_item(self, item_id: int, user_id: int) -> bool:
        async with self.database.session_factory() as session:
            result = await session.execute(
                update(Item)
                .where(Item.id == item_id, Item.user_id == user_id, Item.status == "active")
                .values(status="closed")
            )
            await session.commit()
            return bool(result.rowcount)
