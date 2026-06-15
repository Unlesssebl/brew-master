import asyncio
import logging
from aiogram import Bot, Dispatcher
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from config import settings
from src.bot import setup_routers
from src.workers.queue_worker import run_queue_worker
from src.workers.royalty import run_royalty_worker
from src.workers.rival_ceo import run_rival_ceo_worker
from src.llm_engine import LLMEventGenerator

# Setup logging configuration
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("main")


async def call_llm_api(prompt: str) -> str:
    """
    Асинхронный вызов Google Gemini API с использованием официального клиента google-genai.
    В случае отсутствия ключа LLM_API_KEY возвращается стандартное заглушечное событие.
    """
    if not settings.LLM_API_KEY:
        logger.warning("LLM_API_KEY не задан. Используется заглушка для генерации события.")
        return (
            '{"event_title": "Затишье в таверне", '
            '"event_description": "В таверне подозрительно тихо. Никаких событий сегодня не произошло.", '
            '"choices": []}'
        )

    try:
        from google import genai
        # Инициализируем клиент Google GenAI
        client = genai.Client(api_key=settings.LLM_API_KEY)
        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        return response.text
    except Exception as e:
        logger.error(f"Ошибка при вызове Gemini API: {e}", exc_info=True)
        raise


async def main() -> None:
    """
    Главная точка входа оркестратора.
    Инициализирует подключение к базе данных, бота Telegram
    и запускает все фоновые процессы параллельно.
    """
    # Инициализация асинхронного движка базы данных
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.LOG_LEVEL.upper() == "DEBUG",
        pool_pre_ping=True,
    )

    # Фабрика асинхронных сессий SQLAlchemy
    session_maker = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # Инициализация Bot и Dispatcher для Telegram
    bot = Bot(token=settings.BOT_TOKEN)
    dp = Dispatcher()

    # Регистрация обработчиков и middleware в диспетчере
    setup_routers(dp, session_maker)

    # Инициализация генератора игровых событий на базе LLM
    llm_generator = LLMEventGenerator(call_llm_api=call_llm_api)

    logger.info("Запуск Beer Empire оркестратора (бот и фоновые процессы)...")

    try:
        # Запуск параллельных задач через gather
        await asyncio.gather(
            dp.start_polling(bot),
            run_queue_worker(session_maker, llm_generator),
            run_royalty_worker(session_maker),
            run_rival_ceo_worker(session_maker),
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


