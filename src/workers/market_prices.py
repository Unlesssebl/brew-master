import asyncio
import logging
import random
from datetime import datetime, UTC, timedelta
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from typing import cast
from src.database.models import IngredientPrice, PlayerEventLog
from src.database.dal import EconomyDAL

logger = logging.getLogger(__name__)


async def run_market_prices_worker(session_maker: async_sessionmaker) -> None:
    """
    Фоновый воркер для обновления цен ингредиентов на рынке с EMA-сглаживанием.
    Запускается каждые 4 часа.
    """
    logger.info("Market Prices worker started.")
    while True:
        try:
            logger.info("Market Prices iteration started...")
            async with session_maker() as session:
                economy_dal = EconomyDAL()
                prices = await economy_dal.get_ingredient_prices(session)

                # Считаем покупки за последние 4 часа
                four_hours_ago = datetime.now(UTC) - timedelta(hours=4)
                stmt_events = select(PlayerEventLog).where(
                    PlayerEventLog.event_type == "buy_resources",
                    PlayerEventLog.created_at >= four_hours_ago
                )
                res_events = await session.execute(stmt_events)
                events = res_events.scalars().all()

                purchases = {"malt": 0, "water": 0, "hops": 0, "yeast": 0}
                for ev in events:
                    meta = ev.metadata_json or {}
                    ing = meta.get("ingredient")
                    amount = meta.get("amount", 0)
                    if ing in purchases:
                        purchases[ing] += amount

                base_costs = {
                    "malt": Decimal("1.00"),
                    "water": Decimal("0.10"),
                    "hops": Decimal("2.00"),
                    "yeast": Decimal("1.50")
                }

                for p in prices:
                    ing = cast(str, p.ingredient)
                    purchased_qty = purchases.get(ing, 0)
                    base_cost = base_costs.get(ing, Decimal("1.00"))
                    
                    # new_price = base_cost * (1 + 0.1 * (purchases / 100))
                    demand_multiplier = Decimal("1.0") + Decimal("0.1") * (Decimal(str(purchased_qty)) / Decimal("100.0"))
                    
                    # Легкий случайный шум рынка (+/- 5%)
                    noise = Decimal(str(random.uniform(0.95, 1.05)))
                    new_price = base_cost * demand_multiplier * noise

                    # Clamp
                    min_price = base_cost * Decimal("0.5")
                    max_price = base_cost * Decimal("3.0")
                    new_price = max(min_price, min(max_price, new_price))

                    # EMA-сглаживание
                    ema_price = p.price * Decimal("0.7") + new_price * Decimal("0.3")

                    if ema_price > p.price:
                        p.trend = 1
                    elif ema_price < p.price:
                        p.trend = -1
                    else:
                        p.trend = 0

                    p.price = ema_price
                    p.last_updated = datetime.now(UTC)
                    session.add(p)

                await session.commit()
                logger.info("Ingredient prices updated successfully.")
        except Exception as e:
            logger.error(f"Error in Market Prices worker: {e}", exc_info=True)

        await asyncio.sleep(14400)
