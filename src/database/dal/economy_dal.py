from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import Patent, TransactionLog


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
