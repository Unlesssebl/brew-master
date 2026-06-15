# Telegram API Gateway (Бот-клиент)
import asyncio
import logging

logger = logging.getLogger(__name__)


async def run_bot():
    """
    Основной цикл запуска Telegram-бота.
    """
    logger.info("Starting Beer Empire Telegram Bot...")
    try:
        # Ожидаем бесконечно, пока задача не будет отменена
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        logger.info("Telegram Bot received stop signal, shutting down...")

