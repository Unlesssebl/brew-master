from datetime import UTC
from decimal import Decimal

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import Batch, Player, Resource, Staff, StaffStatus, TavernTier

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

    async def update_tutorial_step(self, tg_id: int, new_step: int) -> Player:
        """
        Обновляет шаг обучения игрока.
        """
        player = await self.get_player(tg_id)
        player.tutorial_step = new_step
        await self.session.commit()
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

    async def upgrade_tavern_level(self, player_id: int) -> TavernTier:
        """
        Улучшить уровень таверны игрока, списав золото.
        """
        player = await self.get_player_by_id(player_id)

        NEXT_TIER = {
            TavernTier.garage: TavernTier.tavern,
            TavernTier.tavern: TavernTier.brewery,
            TavernTier.brewery: TavernTier.factory,
            TavernTier.factory: TavernTier.guild,
        }

        UPGRADE_COSTS = {
            TavernTier.garage: Decimal("500.00"),
            TavernTier.tavern: Decimal("2000.00"),
            TavernTier.brewery: Decimal("10000.00"),
            TavernTier.factory: Decimal("50000.00"),
        }

        current_tier = player.tavern_level
        if current_tier not in NEXT_TIER:
            raise ValueError("Таверна уже улучшена до максимального уровня!")

        cost = UPGRADE_COSTS[current_tier]
        next_tier = NEXT_TIER[current_tier]

        # Списываем золото
        await self.change_gold(player_id, -cost)

        # Обновляем уровень
        stmt = (
            update(Player)
            .where(Player.player_id == player_id)
            .values(tavern_level=next_tier)
        )
        await self.session.execute(stmt)
        return next_tier

    async def update_player_stats(
        self, player_id: int, gold_change: float | Decimal, reputation_change: int, influence_change: int
    ) -> None:
        """
        Атомарно обновляет золото, репутацию и влияние игрока.
        Проверяет, чтобы золото не стало отрицательным.
        Применяет Clamp к репутации [-100, 100] и влиянию [0, 100].
        """
        player = await self.get_player_by_id(player_id)

        # Сначала проверим и спишем золото
        if gold_change != 0:
            await self.change_gold(player_id, gold_change)

        new_reputation = max(-100, min(100, player.reputation + reputation_change))
        new_influence = max(0, min(100, player.influence + influence_change))

        stmt = (
            update(Player)
            .where(Player.player_id == player_id)
            .values(reputation=new_reputation, influence=new_influence)
        )
        await self.session.execute(stmt)

    async def create_staff(self, player_id: int, name: str, role: str, skill: int) -> Staff:
        """
        Создать (нанять) нового сотрудника для игрока.
        """
        staff = Staff(
            player_id=player_id,
            name=name,
            role=role,
            skill=skill,
            loyalty=100,
            fatigue=0,
            status=StaffStatus.healthy
        )
        self.session.add(staff)
        await self.session.flush()
        return staff

    async def get_player_staff(self, player_id: int) -> list[Staff]:
        """
        Получить список всего персонала игрока.
        """
        stmt = select(Staff).where(Staff.player_id == player_id)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def get_alerts_summary(self, player_id: int) -> dict[str, int]:
        """
        Собирает сводку важных уведомлений для игрока.
        """
        stmt_batches = select(func.count(Batch.batch_id)).where(
            Batch.player_id == player_id,
            Batch.quantity_barrels > 0,
        )
        batches_res = await self.session.execute(stmt_batches)
        ready_batches = batches_res.scalar_one_or_none() or 0

        stmt_staff = select(func.count(Staff.staff_id)).where(
            Staff.player_id == player_id,
            Staff.fatigue > 50,
            Staff.status != StaffStatus.dead,
        )
        staff_res = await self.session.execute(stmt_staff)
        tired_staff = staff_res.scalar_one_or_none() or 0

        return {
            "ready_batches": ready_batches,
            "tired_staff": tired_staff,
        }

    async def get_resources(self, player_id: int) -> dict[str, Decimal]:
        """
        Получить количество базовых ресурсов игрока.
        Если ресурсы не инициализированы, инициализирует их с нулевым количеством.
        """
        stmt = select(Resource).where(Resource.player_id == player_id)
        res = await self.session.execute(stmt)
        resources_list = res.scalars().all()

        res_dict = {str(r.resource_type): Decimal(str(r.quantity)) for r in resources_list}

        # Инициализируем отсутствующие типы ресурсов
        required_types = ["malt", "water", "hops", "yeast"]
        updated = False
        for r_type in required_types:
            if r_type not in res_dict:
                new_res = Resource(player_id=player_id, resource_type=r_type, quantity=Decimal("0.00"))
                self.session.add(new_res)
                res_dict[r_type] = Decimal("0.00")
                updated = True

        if updated:
            await self.session.flush()

        return res_dict

    async def buy_resources_pack(self, player_id: int, cost: Decimal = Decimal("100.00"), amount: Decimal = Decimal("50.00")) -> None:
        """
        Списывает золото и начисляет пачку ресурсов (malt, water, hops, yeast) по amount единиц.
        """
        # Списываем золото
        await self.change_gold(player_id, -cost)

        # Получаем/инициализируем ресурсы
        await self.get_resources(player_id)

        # Обновляем количество
        stmt = (
            update(Resource)
            .where(Resource.player_id == player_id)
            .values(quantity=Resource.quantity + amount)
        )
        await self.session.execute(stmt)
