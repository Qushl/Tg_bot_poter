from sqlalchemy import func, select, update

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
            item = Item(user_id=user_id, **data)
            session.add(item)
            await session.commit()
            await session.refresh(item)
            return item

    async def active_items(
        self, page: int, per_page: int, city: str | None = None, campus: str | None = None
    ) -> tuple[list[Item], int]:
        filters = [Item.status == "active"]
        if city:
            filters.append(Item.city.ilike(f"%{city}%"))
        if campus:
            filters.append(Item.campus == campus)
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

    async def user_items(self, user_id: int) -> list[Item]:
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
