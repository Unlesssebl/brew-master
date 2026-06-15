import inspect

from src.bot import run_bot


def test_bot_entrypoint():
    """
    Проверяет, что функция запуска бота импортируется и является корутиной.
    """
    assert inspect.iscoroutinefunction(run_bot)
