from aiogram import Dispatcher
from sqlalchemy.ext.asyncio import async_sessionmaker

from .handlers.basic import basic_router
from .handlers.craft import craft_router
from .middlewares.db import DbSessionMiddleware


def setup_routers(dp: Dispatcher, session_maker: async_sessionmaker) -> None:
    """
    Настройка роутеров и регистрация middleware для диспетчера aiogram.
    """
    # Подключаем роутеры
    dp.include_router(basic_router)
    dp.include_router(craft_router)

    # Регистрируем middleware для сессий БД
    db_middleware = DbSessionMiddleware(session_maker)
    dp.message.middleware(db_middleware)
    dp.callback_query.middleware(db_middleware)
