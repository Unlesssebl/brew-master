from decimal import Decimal
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import Player
from .exceptions import InsufficientFundsError, PlayerNotFoundError


class PlayerDAL:
    """
    Data Access Layer (DAL) для работы с данными игроков.
    """

    @staticmethod
    async def get_player(session: AsyncSession, player_id: int) -> Player:
        """
        Получить игрока по его ID.
        Если игрок не найден, вызывает PlayerNotFoundError.
        """
        stmt = select(Player).where(Player.player_id == player_id)
        result = await session.execute(stmt)
        player = result.scalar_one_or_none()
        if player is None:
            raise PlayerNotFoundError(f"Player with ID {player_id} not found.")
        return player

    @staticmethod
    async def change_gold(session: AsyncSession, player_id: int, amount: float | Decimal) -> None:
        """
        Изменить количество золота у игрока (атомарная операция).
        
        Для списания передается отрицательное значение amount.
        Если баланса недостаточно или игрок не найден, вызывается соответствующее исключение.
        """
        decimal_amount = Decimal(str(amount)) if isinstance(amount, float) else amount

        stmt = (
            update(Player)
            .where(Player.player_id == player_id, Player.gold >= -decimal_amount)
            .values(gold=Player.gold + decimal_amount)
        )
        result = await session.execute(stmt)

        if result.rowcount == 0:
            # Выясняем причину: игрока нет или не хватает золота
            stmt_check = select(Player.gold).where(Player.player_id == player_id)
            check_res = await session.execute(stmt_check)
            current_gold = check_res.scalar_one_or_none()
            
            if current_gold is None:
                raise PlayerNotFoundError(f"Player with ID {player_id} not found.")
            else:
                raise InsufficientFundsError(
                    f"Insufficient funds for player {player_id}. "
                    f"Current: {current_gold}, required change: {decimal_amount}."
                )
