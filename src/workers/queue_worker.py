import asyncio
import logging

from aiogram import Bot
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.database.dal import QueueDAL
from src.llm_engine import LLMEventGenerator

logger = logging.getLogger(__name__)


async def run_queue_worker(
    session_maker: async_sessionmaker,
    llm_generator: LLMEventGenerator,
    bot: Bot,
) -> None:
    """
    Асинхронный воркер для обработки задач из очереди.
    Слушает задачи типа 'llm_event', генерирует события с помощью LLM
    и создает новые задачи 'bot_dispatch' для отправки игрокам.
    А также отправляет квесты ('bot_dispatch') пользователям в Telegram.
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

                elif task.task_type == "bot_dispatch":
                    # Отправляем сообщение пользователю в Telegram
                    tg_id = task.payload.get("tg_id")
                    if not tg_id:
                        logger.error(f"Task {task.task_id} of type 'bot_dispatch' has no tg_id in payload.")
                        async with session_maker() as session:
                            await QueueDAL.complete_task(session, task.task_id, success=False)
                            await session.commit()
                        continue

                    event_title = task.payload.get("event_title", "Случайное событие")
                    event_description = task.payload.get("event_description", "")
                    choices = task.payload.get("choices", [])

                    text = f"🎭 <b>{event_title}</b>\n\n{event_description}"

                    builder = InlineKeyboardBuilder()
                    for choice in choices:
                        choice_id = choice.get("choice_id")
                        button_text = choice.get("button_text", "Выбрать")
                        # Формируем callback_data: llm_c:{task_id}:{choice_id}
                        callback_data = f"llm_c:{task.task_id}:{choice_id}"
                        builder.row(
                            InlineKeyboardButton(
                                text=button_text,
                                callback_data=callback_data
                            )
                        )

                    try:
                        await bot.send_message(
                            chat_id=int(tg_id),
                            text=text,
                            reply_markup=builder.as_markup(),
                        )
                        async with session_maker() as session:
                            await QueueDAL.complete_task(session, task.task_id, success=True)
                            await session.commit()
                    except Exception as tg_e:
                        logger.error(f"Failed to send Telegram message for task {task.task_id}: {tg_e}")
                        async with session_maker() as session:
                            await QueueDAL.complete_task(session, task.task_id, success=False)
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
