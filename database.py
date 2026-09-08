from collections.abc import AsyncIterator
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, String, Text, func, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str | None] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    items: Mapped[list["Item"]] = relationship(back_populates="user")


class Item(Base):
    __tablename__ = "items"
    __table_args__ = (
        CheckConstraint("type IN ('lost', 'found')", name="ck_items_type"),
        CheckConstraint("status IN ('active', 'closed')", name="ck_items_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.telegram_id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(10), index=True)
    photo_file_id: Mapped[str] = mapped_column(String(512))
    title: Mapped[str] = mapped_column(String(120), default="Без заголовка", server_default="Без заголовка")
    description: Mapped[str] = mapped_column(Text)
    city: Mapped[str] = mapped_column(String(255), index=True)
    campus: Mapped[str] = mapped_column(String(100), default="Другое место", server_default="Другое место", index=True)
    contact: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(10), default="active", server_default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    user: Mapped[User] = relationship(back_populates="items")


class Database:
    def __init__(self, url: str) -> None:
        self.engine = create_async_engine(url, pool_pre_ping=True)
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)

    async def create_tables(self) -> None:
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
            if self.engine.dialect.name == "sqlite":
                columns = await connection.execute(text("PRAGMA table_info(items)"))
                if "campus" not in {row[1] for row in columns}:
                    await connection.execute(
                        text("ALTER TABLE items ADD COLUMN campus VARCHAR(100) NOT NULL DEFAULT 'Другое место'")
                    )
                columns = await connection.execute(text("PRAGMA table_info(items)"))
                if "title" not in {row[1] for row in columns}:
                    await connection.execute(
                        text("ALTER TABLE items ADD COLUMN title VARCHAR(120) NOT NULL DEFAULT 'Без заголовка'")
                    )

    async def sessions(self) -> AsyncIterator[AsyncSession]:
        async with self.session_factory() as session:
            yield session

    async def close(self) -> None:
        await self.engine.dispose()
