from decimal import Decimal
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import Patent, TransactionLog, IngredientPrice, Resource, Batch
from .player_dal import PlayerDAL


class EconomyDAL:
    """
    Data Access Layer (DAL) для работы с экономическими транзакциями и патентами.
    """

    @staticmethod
    async def get_unprocessed_royalties(session: AsyncSession) -> list[dict]:
        """
        Возвращает агрегированные не обработанные роялти для legal и grey рынков.
        Возвращает список словарей вида {"recipe_id": int, "total_revenue": float}.
        """
        stmt = (
            select(
                TransactionLog.recipe_id,
                func.sum(TransactionLog.total_revenue).label("total_revenue"),
            )
            .where(
                TransactionLog.processed_for_royalty == False,  # noqa: E712
                TransactionLog.market_type.in_(["legal", "grey"]),
            )
            .group_by(TransactionLog.recipe_id)
        )
        result = await session.execute(stmt)
        rows = result.all()
        return [
            {
                "recipe_id": int(row[0]),
                "total_revenue": float(row[1]) if row[1] is not None else 0.0,
            }
            for row in rows
        ]

    @staticmethod
    async def mark_transactions_processed(session: AsyncSession, recipe_ids: list[int]) -> None:
        """
        Массовый UPDATE processed_for_royalty = True для указанных recipe_id.
        """
        if not recipe_ids:
            return

        stmt = (
            update(TransactionLog)
            .where(TransactionLog.recipe_id.in_(recipe_ids))
            .values(processed_for_royalty=True)
        )
        await session.execute(stmt)

    @staticmethod
    async def get_active_patents_for_recipes(
        session: AsyncSession, recipe_ids: list[int]
    ) -> list[dict]:
        """
        Получает активные и действующие патенты для указанных рецептов.
        Возвращает список словарей вида:
        {"patent_id": int, "player_id": int, "royalty_earned_24h": float}
        """
        if not recipe_ids:
            return []

        stmt = select(Patent.patent_id, Patent.player_id, Patent.royalty_earned_24h).where(
            Patent.recipe_id.in_(recipe_ids),
            Patent.is_active == True,  # noqa: E712
            Patent.expires_at > func.now(),
        )
        result = await session.execute(stmt)
        rows = result.all()
        return [
            {
                "patent_id": int(row[0]),
                "player_id": int(row[1]),
                "royalty_earned_24h": float(row[2]) if row[2] is not None else 0.0,
            }
            for row in rows
        ]

    @staticmethod
    async def get_ingredient_prices(session: AsyncSession) -> list[IngredientPrice]:
        """
        Возвращает текущие цены ингредиентов. Если цены не инициализированы, 
        инициализирует их базовыми значениями.
        """
        stmt = select(IngredientPrice)
        result = await session.execute(stmt)
        prices = list(result.scalars().all())

        base_costs = {
            "malt": Decimal("1.00"),
            "water": Decimal("0.10"),
            "hops": Decimal("2.00"),
            "yeast": Decimal("1.50")
        }

        if len(prices) < 4:
            existing = {p.ingredient for p in prices}
            for ing, base in base_costs.items():
                if ing not in existing:
                    ip = IngredientPrice(ingredient=ing, price=base, trend=0)
                    session.add(ip)
                    prices.append(ip)
            await session.flush()

        return prices

    @staticmethod
    async def buy_ingredient(
        session: AsyncSession, player_id: int, ingredient: str, amount: int, price_per_unit: Decimal
    ) -> None:
        """
        Процесс покупки ингредиента игроком. Списывает золото и начисляет ресурс.
        """
        player_dal = PlayerDAL(session)
        cost = Decimal(str(amount)) * price_per_unit

        await player_dal.change_gold(player_id, -cost)

        stmt = select(Resource).where(Resource.player_id == player_id, Resource.resource_type == ingredient)
        result = await session.execute(stmt)
        res = result.scalar_one_or_none()

        if res:
            res.quantity = res.quantity + Decimal(str(amount))
        else:
            new_res = Resource(player_id=player_id, resource_type=ingredient, quantity=Decimal(str(amount)))
            session.add(new_res)
        
        await session.flush()

    @staticmethod
    async def sell_batch(
        session: AsyncSession, player_id: int, batch_id: int, fraction: str, market_type: str, total_revenue: Decimal, volume_to_sell: int | None = None
    ) -> None:
        """
        Продажа готовой партии пива фракции. Списывает бочки готового пива у игрока,
        начисляет золото и делает запись в TransactionLog.
        """
        player_dal = PlayerDAL(session)

        stmt = select(Batch).where(Batch.batch_id == batch_id, Batch.player_id == player_id)
        result = await session.execute(stmt)
        batch = result.scalar_one_or_none()

        if not batch or batch.quantity_barrels <= 0 or not batch.is_completed:
            raise ValueError("Партия не найдена или уже продана!")

        volume = volume_to_sell if volume_to_sell is not None else batch.quantity_barrels
        if volume > batch.quantity_barrels:
            raise ValueError("Недостаточно бочек в партии!")

        batch.quantity_barrels -= volume
        session.add(batch)

        await player_dal.change_gold(player_id, total_revenue)

        tx = TransactionLog(
            seller_id=player_id,
            recipe_id=batch.recipe_id,
            market_type=market_type,
            volume=volume,
            total_revenue=total_revenue,
            processed_for_royalty=False
        )
        session.add(tx)
        await session.flush()
