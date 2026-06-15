import asyncio
import logging

from aiogram import Bot, Dispatcher

from config import settings
from src.bot import setup_routers
from src.database.connection import async_session_factory, engine
from src.llm_engine import LLMEventGenerator
from src.workers.queue_worker import run_queue_worker
from src.workers.rival_ceo import run_rival_ceo_worker
from src.workers.royalty import run_royalty_worker

# Setup logging configuration
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("main")


from src.llm_engine.api_client import call_llm_api


async def main() -> None:
    """
    Главная точка входа оркестратора.
    Инициализирует подключение к базе данных, бота Telegram
    и запускает все фоновые процессы параллельно.
    """
    # Инициализация Bot и Dispatcher для Telegram
    bot = Bot(token=settings.BOT_TOKEN)
    dp = Dispatcher()

    # Регистрация обработчиков и middleware в диспетчере
    setup_routers(dp, async_session_factory)

    # Инициализация генератора игровых событий на базе LLM
    llm_generator = LLMEventGenerator(call_llm_api=call_llm_api)

    logger.info("Запуск Beer Empire оркестратора (бот и фоновые процессы)...")

    try:
        # Запуск параллельных задач через gather
        await asyncio.gather(
            dp.start_polling(bot),
            run_queue_worker(async_session_factory, llm_generator),
            run_royalty_worker(async_session_factory),
            run_rival_ceo_worker(async_session_factory),
        )
    except asyncio.CancelledError:
        logger.info("Получен сигнал отмены. Завершение работы...")
    finally:
        logger.info("Закрытие сессии бота...")
        await bot.session.close()
        logger.info("Закрытие соединений с базой данных...")
        await engine.dispose()
        logger.info("Работа приложения полностью завершена.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Процесс прерван пользователем (KeyboardInterrupt). Завершение работы...")
