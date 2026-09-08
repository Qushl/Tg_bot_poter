import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiohttp_socks import ProxyConnector

from config import load_config
from database import Database
from handlers import router
from repository import Repository


async def main() -> None:
    config = load_config()
    database = Database(config.database_url)
    await database.create_tables()

    session = AiohttpSession()
    if config.proxy_url:
        session._connector_type = lambda **kwargs: ProxyConnector.from_url(config.proxy_url)
    bot = Bot(
        token=config.bot_token,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dispatcher = Dispatcher()
    dispatcher.include_router(router)


    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dispatcher.start_polling(bot, repo=Repository(database))
    finally:
        await bot.session.close()
        await database.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
