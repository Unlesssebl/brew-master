import asyncio
import logging
from sqlalchemy import update
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.database.dal import EconomyDAL, PlayerDAL
from src.database.dal.exceptions import InsufficientFundsError
from src.database.models import Patent

logger = logging.getLogger(__name__)


async def run_royalty_worker(session_maker: async_sessionmaker) -> None:
    """
    Асинхронный воркер для сбора роялти и налогов.
    Запускается раз в час, обрабатывает невыплаченные роялти,
    списывает налог за владение патентом, деактивирует патенты неплательщиков
    и выплачивает роялти.
    """
    logger.info("Royalty worker started.")
    while True:
        try:
            async with session_maker() as session:
                async with session.begin():
                    # 1. Получаем не обработанные роялти
                    royalties = await EconomyDAL.get_unprocessed_royalties(session)

                    if royalties:
                        for entry in royalties:
                            recipe_id = entry["recipe_id"]
                            total_revenue = entry["total_revenue"]

                            # a. Получаем активные патенты для данного рецепта
                            patents = (
                                await EconomyDAL.get_active_patents_for_recipes(
                                    session, [recipe_id]
                                )
                            )

                            # b. Для каждого патента обрабатываем налог и выплату
                            for patent in patents:
                                patent_id = patent["patent_id"]
                                player_id = patent["player_id"]
                                royalty_earned_24h = patent["royalty_earned_24h"]

                                # Расчет выплаты: payout = entry['total_revenue'] * 0.05
                                payout = total_revenue * 0.05

                                # Расчет прогрессивного налога: tax = 50 + (patent['royalty_earned_24h'] * 0.15)
                                tax = 50.0 + (royalty_earned_24h * 0.15)

                                # Попытка списать налог
                                try:
                                    await PlayerDAL.change_gold(
                                        session, player_id, -tax
                                    )
                                    tax_paid = True
                                    logger.info(
                                        f"Tax of {tax} successfully collected from player {player_id} for patent {patent_id}."
                                    )
                                except InsufficientFundsError:
                                    tax_paid = False
                                    logger.warning(
                                        f"Player {player_id} has insufficient funds to pay tax {tax} for patent {patent_id}. "
                                        f"Deactivating patent."
                                    )
                                    # Деактивируем патент
                                    stmt = (
                                        update(Patent)
                                        .where(Patent.patent_id == patent_id)
                                        .values(is_active=False)
                                    )
                                    await session.execute(stmt)

                                # Если налог списан успешно (или был 0): начисли роялти
                                if tax_paid:
                                    await PlayerDAL.change_gold(
                                        session, player_id, payout
                                    )
                                    logger.info(
                                        f"Royalty of {payout} paid to player {player_id} for recipe {recipe_id}."
                                    )

                        # 3. Помечаем транзакции как обработанные
                        recipe_ids = [r["recipe_id"] for r in royalties]
                        await EconomyDAL.mark_transactions_processed(
                            session, recipe_ids
                        )
                        logger.info(
                            f"Marked transactions processed for recipes: {recipe_ids}"
                        )

        except Exception as e:
            logger.error(
                f"Error during royalty worker execution: {e}", exc_info=True
            )

        # Спим ровно час
        await asyncio.sleep(3600)
