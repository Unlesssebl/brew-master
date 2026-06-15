from datetime import UTC
from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import Player, Staff, StaffStatus

from .exceptions import InsufficientFundsError, PlayerNotFoundError


class PlayerDAL:
    """
    Data Access Layer (DAL) для работы с данными игроков.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_player_by_id(self, player_id: int) -> Player:
        """
        Получить игрока по его уникальному ID в базе данных.
        """
        stmt = select(Player).where(Player.player_id == player_id)
        result = await self.session.execute(stmt)
        player = result.scalar_one_or_none()
        if player is None:
            raise PlayerNotFoundError(f"Player with ID {player_id} not found.")
        return player

    async def get_player_by_tg_id(self, tg_id: int) -> Player:
        """
        Получить игрока по его Telegram ID.
        """
        stmt = select(Player).where(Player.tg_id == tg_id)
        result = await self.session.execute(stmt)
        player = result.scalar_one_or_none()
        if player is None:
            raise PlayerNotFoundError(f"Player with Telegram ID {tg_id} not found.")
        return player

    async def get_player(self, tg_id: int) -> Player:
        """
        Получить игрока по Telegram ID. Сохранено для совместимости с хэндлерами aiogram.
        """
        return await self.get_player_by_tg_id(tg_id)

    async def create_player(self, tg_id: int) -> Player:
        """
        Создать нового игрока с начальным капиталом в 1000 gold.
        """
        player = Player(tg_id=tg_id, gold=Decimal("1000.00"))
        self.session.add(player)
        await self.session.flush()
        return player

    async def get_active_staff(self, player_id: int, role: str) -> Staff | None:
        """
        Найти активного сотрудника с заданной ролью для игрока.
        Активным считается сотрудник со статусом, отличным от 'dead',
        и не заблокированный (blocked_until в прошлом или отсутствует).
        """
        from datetime import datetime

        stmt = select(Staff).where(
            Staff.player_id == player_id, Staff.role == role, Staff.status != StaffStatus.dead
        )
        result = await self.session.execute(stmt)
        staff_list = result.scalars().all()

        now = datetime.now(UTC)
        for s in staff_list:
            if s.blocked_until is None or s.blocked_until <= now:
                return s
        return None

    async def change_gold(self, player_id: int, amount: float | Decimal) -> None:
        """
        Изменить количество золота у игрока (атомарная операция).
        """
        decimal_amount = Decimal(str(amount)) if isinstance(amount, (float, int)) else amount

        stmt = (
            update(Player)
            .where(Player.player_id == player_id, Player.gold >= -decimal_amount)
            .values(gold=Player.gold + decimal_amount)
        )
        result = await self.session.execute(stmt)

        if result.rowcount == 0:
            # Выясняем причину: игрока нет или не хватает золота
            stmt_check = select(Player.gold).where(Player.player_id == player_id)
            check_res = await self.session.execute(stmt_check)
            current_gold = check_res.scalar_one_or_none()

            if current_gold is None:
                raise PlayerNotFoundError(f"Player with ID {player_id} not found.")
            else:
                raise InsufficientFundsError(
                    f"Insufficient funds for player {player_id}. "
                    f"Current: {current_gold}, required change: {decimal_amount}."
                )
