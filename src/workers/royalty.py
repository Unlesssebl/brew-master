import asyncio
import logging
from datetime import datetime, UTC, timedelta

from sqlalchemy import update, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.database.dal import EconomyDAL, PlayerDAL
from src.database.dal.exceptions import InsufficientFundsError
from src.database.models import Patent, Batch, Recipe, PlayerEventLog

logger = logging.getLogger(__name__)


async def run_royalty_worker(session_maker: async_sessionmaker) -> None:
    """
    Асинхронный воркер для сбора роялти и налогов, а также порчи пива.
    Запускается раз в час, обрабатывает невыплаченные роялти,
    списывает налог за владение патентом, деактивирует патенты неплательщиков,
    выплачивает роялти и проверяет партии пива на порчу.
    """
    logger.info("Royalty worker started.")
    while True:
        try:
            async with session_maker() as session:
                async with session.begin():
                    # 1. Получаем не обработанные роялти
                    royalties = await EconomyDAL.get_unprocessed_royalties(session)

                    player_dal = PlayerDAL(session)

                    if royalties:
                        for entry in royalties:
                            recipe_id = entry["recipe_id"]
                            total_revenue = entry["total_revenue"]

                            # a. Получаем активные патенты для данного рецепта
                            patents = await EconomyDAL.get_active_patents_for_recipes(
                                session, [recipe_id]
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
                                    await player_dal.change_gold(player_id, -tax)
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
                                    await player_dal.change_gold(player_id, payout)
                                    logger.info(
                                        f"Royalty of {payout} paid to player {player_id} for recipe {recipe_id}."
                                    )

                        # 3. Помечаем транзакции как обработанные
                        recipe_ids = [r["recipe_id"] for r in royalties]
                        await EconomyDAL.mark_transactions_processed(session, recipe_ids)
                        logger.info(f"Marked transactions processed for recipes: {recipe_ids}")

                    # 4. Проверка порчи пива (72 часа)
                    three_days_ago = datetime.now(UTC) - timedelta(hours=72)
                    stmt_spoiled = select(Batch).where(
                        Batch.is_completed == True,
                        Batch.quantity_barrels > 0,
                        Batch.ready_at < three_days_ago
                    )
                    res_spoiled = await session.execute(stmt_spoiled)
                    spoiled_batches = res_spoiled.scalars().all()

                    for b in spoiled_batches:
                        stmt_recipe = select(Recipe).where(Recipe.recipe_id == b.recipe_id)
                        res_recipe = await session.execute(stmt_recipe)
                        recipe = res_recipe.scalar_one_or_none()
                        recipe_title = recipe.title if recipe else "Неизвестное пиво"

                        logger.warning(
                            f"Batch {b.batch_id} for player {b.player_id} has spoiled ({b.quantity_barrels} barrels)."
                        )

                        # Пишем предупреждение игроку в лог событий
                        evt_log = PlayerEventLog(
                            player_id=b.player_id,
                            event_type="beer_spoiled",
                            summary=f"⚠️ Партия пива «{recipe_title}» ({b.quantity_barrels} бочек) испортилась, так как простояла на складе более 72 часов!",
                            metadata_json={"batch_id": b.batch_id, "barrels": b.quantity_barrels}
                        )
                        session.add(evt_log)

                        # Списываем бочки
                        b.quantity_barrels = 0
                        session.add(b)

        except Exception as e:
            logger.error(f"Error during royalty worker execution: {e}", exc_info=True)

        # Спим ровно час
        await asyncio.sleep(3600)
