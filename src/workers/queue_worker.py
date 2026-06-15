import asyncio
import logging

from sqlalchemy.ext.asyncio import async_sessionmaker

from src.database.dal import QueueDAL
from src.llm_engine import LLMEventGenerator

logger = logging.getLogger(__name__)


async def run_queue_worker(
    session_maker: async_sessionmaker, llm_generator: LLMEventGenerator
) -> None:
    """
    Асинхронный воркер для обработки задач из очереди.
    Слушает задачи типа 'llm_event', генерирует события с помощью LLM
    и создает новые задачи 'bot_dispatch' для отправки игрокам.
    """
    logger.info("Queue worker started.")
    while True:
        try:
            # Шаг 1: Захватываем задачу в отдельной транзакции
            async with session_maker() as session:
                task = await QueueDAL.fetch_next_task(session)
                if task is not None:
                    await session.commit()

            if task is None:
                await asyncio.sleep(5)
                continue

            logger.info(f"Processing task {task.task_id} of type '{task.task_type}'")

            # Шаг 2: Обрабатываем задачу
            try:
                if task.task_type == "llm_event":
                    # Вызов генератора LLM (вне транзакции БД)
                    event = await llm_generator.generate_event(task.payload)

                    # Запись результатов в новой транзакции
                    async with session_maker() as session:
                        await QueueDAL.create_task(
                            session,
                            task_type="bot_dispatch",
                            payload=event.model_dump(),
                            target_tg_id=task.payload.get("tg_id"),
                        )
                        await QueueDAL.complete_task(session, task.task_id, success=True)
                        await session.commit()
                else:
                    # Для других типов задач просто завершаем их
                    async with session_maker() as session:
                        await QueueDAL.complete_task(session, task.task_id, success=True)
                        await session.commit()
            except Exception as inner_e:
                logger.error(
                    f"Error processing task {task.task_id}: {inner_e}",
                    exc_info=True,
                )
                async with session_maker() as session:
                    await QueueDAL.complete_task(session, task.task_id, success=False)
                    await session.commit()

        except Exception as outer_e:
            logger.critical(f"Critical error in queue worker loop: {outer_e}", exc_info=True)
            await asyncio.sleep(5)
