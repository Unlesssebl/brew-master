import asyncio
import logging

logger = logging.getLogger(__name__)


async def run_worker():
    """
    Основной цикл асинхронного воркера.
    Забирает задачи из схемы queue с использованием FOR UPDATE SKIP LOCKED
    и выполняет их по расписанию.
    """
    logger.info("Starting Beer Empire economy worker...")
    while True:
        try:
            # 1. Запрос к БД на получение задачи (SKIP LOCKED)
            # 2. Выполнение задачи (налоги, роялти, обновление рынка)
            # 3. Фиксация выполнения задачи в очереди
            await asyncio.sleep(5)
        except asyncio.CancelledError:
            logger.info("Economy worker received stop signal, shutting down...")
            break
        except Exception as e:
            logger.error(f"Error in economy worker loop: {e}", exc_info=True)
            await asyncio.sleep(10)
