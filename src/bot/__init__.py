from aiogram import Dispatcher
from sqlalchemy.ext.asyncio import async_sessionmaker

from .handlers.basic import basic_router
from .handlers.menu import menu_router
from .handlers.brewing import brewing_router
from .handlers.buildings import buildings_router
from .handlers.events import events_router
from .handlers.craft import craft_router
from .middlewares.db import DbSessionMiddleware


def setup_routers(dp: Dispatcher, session_maker: async_sessionmaker) -> None:
    """
    Настройка роутеров и регистрация middleware для диспетчера aiogram.
    """
    # Подключаем роутеры
    dp.include_router(basic_router)
    dp.include_router(menu_router)
    dp.include_router(brewing_router)
    dp.include_router(buildings_router)
    dp.include_router(events_router)
    dp.include_router(craft_router)

    # Регистрируем middleware для сессий БД
    db_middleware = DbSessionMiddleware(session_maker)
    dp.message.middleware(db_middleware)
    dp.callback_query.middleware(db_middleware)


async def run_bot() -> None:
    """
    Запуск бота в изолированном режиме.
    """
    from aiogram import Bot
    from aiogram.fsm.storage.memory import MemoryStorage

    from config import settings
    from src.database.connection import async_session_factory

    bot = Bot(token=settings.BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    setup_routers(dp, async_session_factory)
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
