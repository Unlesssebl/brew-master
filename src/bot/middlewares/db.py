from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, CallbackQuery
from sqlalchemy.ext.asyncio import async_sessionmaker
from src.database.dal.player_dal import PlayerDAL


class DbSessionMiddleware(BaseMiddleware):
    """
    Middleware для управления жизненным циклом сессии SQLAlchemy в хэндлерах aiogram.
    Внедряет сессию в словарь handler_data под ключом 'session'.
    И синхронизирует hud_message_id при взаимодействии через CallbackQuery.
    """

    def __init__(self, sessionmaker: async_sessionmaker) -> None:
        super().__init__()
        self.sessionmaker = sessionmaker

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with self.sessionmaker() as session:
            data["session"] = session
            
            # Если это CallbackQuery, синхронизируем hud_message_id, чтобы все редактирования
            # сообщений происходили именно с тем сообщением, на котором кликнули кнопку.
            if isinstance(event, CallbackQuery) and event.message and event.from_user:
                try:
                    player_dal = PlayerDAL(session)
                    player = await player_dal.get_player(event.from_user.id)
                    if player.hud_message_id != event.message.message_id:
                        player.hud_message_id = event.message.message_id
                        session.add(player)
                        await session.flush()
                except Exception:
                    pass

            try:
                result = await handler(event, data)
                await session.commit()
                return result
            except Exception as e:
                await session.rollback()
                raise e

