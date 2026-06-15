import argparse
import asyncio
import logging

from src.bot import run_bot
from src.config import settings
from src.workers.rival_ceo import run_rival_ceos
from src.workers.royalty import run_worker as run_royalty_worker

# Настройка логирования
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("main")


async def run_all():
    """
    Запуск всех компонентов Beer Empire (бот и фоновые воркеры) параллельно.
    """
    logger.info("Starting all components (bot and workers)...")
    await asyncio.gather(
        run_bot(),
        run_royalty_worker(),
        run_rival_ceos(),
    )


def main():
    parser = argparse.ArgumentParser(description="Beer Empire Entrypoint")
    parser.add_argument(
        "--run",
        choices=["bot", "worker-royalty", "worker-rival-ceo", "all"],
        default="all",
        help="Specify which component to run (default: all)",
    )
    args = parser.parse_args()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    if args.run == "bot":
        coro = run_bot()
    elif args.run == "worker-royalty":
        coro = run_royalty_worker()
    elif args.run == "worker-rival-ceo":
        coro = run_rival_ceos()
    else:
        coro = run_all()

    try:
        loop.run_until_complete(coro)
    except KeyboardInterrupt:
        logger.info("Received exit signal, shutting down...")
    finally:
        # Отменяем все оставшиеся задачи для корректного завершения
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
        if pending:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        loop.close()
        logger.info("Shutdown complete.")


if __name__ == "__main__":
    main()

