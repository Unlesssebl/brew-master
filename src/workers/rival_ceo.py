import asyncio
import logging
from datetime import datetime, UTC, timedelta
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.database.models import MarketSaturation, TransactionLog, Player, PlayerEventLog
from src.llm_engine.api_client import call_llm_api
from config import settings

logger = logging.getLogger(__name__)


async def run_rival_ceo_worker(session_maker: async_sessionmaker) -> None:
    """
    Асинхронный воркер для симуляции действий ИИ-конкурентов (Rival CEO).
    Запускается раз в 12 часов, анализирует перенасыщение рынка,
    вызывает LLM для принятия решений конкурентами и применяет рыночные штрафы.
    """
    logger.info("Rival CEO worker started.")
    while True:
        try:
            logger.info("Rival CEO iteration started")

            async with session_maker() as session:
                # 1. Агрегация продаж из TransactionLog за последние 24 часа
                day_ago = datetime.now(UTC) - timedelta(hours=24)

                stmt_sales = select(
                    TransactionLog.market_type,
                    func.sum(TransactionLog.volume).label("total_volume")
                ).where(
                    TransactionLog.created_at >= day_ago
                ).group_by(
                    TransactionLog.market_type
                )

                res_sales = await session.execute(stmt_sales)
                actual_sales = {row[0]: int(row[1] or 0) for row in res_sales.all()}

                # Гарантируем наличие всех 3 сегментов
                for seg in ["legal", "grey", "black"]:
                    if seg not in actual_sales:
                        actual_sales[seg] = 0

                # Получаем текущие записи насыщения рынка
                stmt_sat = select(MarketSaturation)
                res_sat = await session.execute(stmt_sat)
                saturations = {s.market_segment: s for s in res_sat.scalars().all()}

                # Обновляем EMA
                for seg, actual_vol in actual_sales.items():
                    sat = saturations.get(seg)
                    if sat:
                        new_ema = float(sat.volume_sold_24h) * 0.7 + float(actual_vol) * 0.3
                        sat.volume_sold_24h = int(new_ema)
                        sat.last_updated = datetime.now(UTC)
                        session.add(sat)
                    else:
                        new_sat = MarketSaturation(
                            market_segment=seg,
                            volume_sold_24h=actual_vol,
                            last_updated=datetime.now(UTC)
                        )
                        session.add(new_sat)
                        saturations[seg] = new_sat

                await session.flush()

                # 2. Проверяем перенасыщение рынка и симулируем действия Rival CEO
                threshold = settings.GameBalance.market_saturation_threshold
                over_market = None
                for seg in ["legal", "grey"]:
                    sat = saturations.get(seg)
                    if sat and sat.volume_sold_24h > threshold:
                        over_market = seg
                        break

                if over_market:
                    logger.info(f"Market segment '{over_market}' is saturated. Triggering Rival CEO dumping.")
                    # Демпинг
                    sat = saturations[over_market]
                    sat.volume_sold_24h += 150
                    session.add(sat)

                    # Генерируем новость
                    prompt = (
                        "Сгенерируй короткую новость для экономической газеты в стиле средневекового фэнтези.\n"
                        f"Контекст: Рынок пива '{over_market}' перенасыщен. Крупный ИИ-конкурент (например, 'Гномьи Пивоварни' или 'Синдикат Хмеля') "
                        "производит демпинг цен и выбрасывает на рынок огромную партию дешевого пива.\n"
                        "Напиши 2-3 предложения на русском языке, с заголовком, предупреждающие игроков о падении цен на пиво в ближайшие часы. Используй HTML-теги для оформления (например <b> для заголовка)."
                    )

                    try:
                        news_text = await call_llm_api(prompt)
                    except Exception as llm_e:
                        logger.error(f"Failed to generate Rival CEO news: {llm_e}")
                        news_text = "🗞️ <b>Рыночный вестник:</b> Крупные торговые гильдии наводнили рынок дешевым импортным элем! Цены на сбыт временно падают."

                    # Записываем событие всем игрокам
                    stmt_players = select(Player.player_id)
                    res_players = await session.execute(stmt_players)
                    player_ids = res_players.scalars().all()

                    for p_id in player_ids:
                        evt_log = PlayerEventLog(
                            player_id=p_id,
                            event_type="rival_ceo_dump",
                            summary=news_text,
                            metadata_json={"market_segment": over_market}
                        )
                        session.add(evt_log)

                await session.commit()
                logger.info("Rival CEO iteration completed successfully")

        except Exception as e:
            logger.error(f"Error during Rival CEO worker execution: {e}", exc_info=True)

        # Спим 12 часов (43200 секунд)
        await asyncio.sleep(43200)
