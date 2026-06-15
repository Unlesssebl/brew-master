import json
import logging
from typing import Any, Callable, Awaitable

from pydantic import ValidationError

from src.llm_engine.schemas import GameEvent, get_fallback_event
from src.llm_engine.prompts import build_event_prompt

logger = logging.getLogger(__name__)


class LLMEventGenerator:
    """
    Класс для генерации игровых событий с использованием LLM.
    Реализует пайплайн: создание промпта, запрос к LLM, валидация и обработка ошибок.
    """

    def __init__(self, call_llm_api: Callable[[str], Awaitable[str]]) -> None:
        """
        Инициализация генератора.

        :param call_llm_api: Асинхронный вызываемый объект (async def (prompt: str) -> str)
        """
        self._call_llm_api = call_llm_api

    async def generate_event(self, player_state: dict[str, Any]) -> GameEvent:
        """
        Главный метод пайплайна генерации игровых событий.

        - Получает промпт из build_event_prompt.
        - Вызывает асинхронный клиент LLM с механизмом повторных попыток (до 3 попыток всего).
        - Валидирует ответ через Pydantic схему GameEvent.
        - При полной неудаче возвращает безопасное fallback событие.
        """
        prompt = build_event_prompt(player_state)
        max_attempts = 3

        for attempt in range(1, max_attempts + 1):
            try:
                response = await self._call_llm_api(prompt)
                event = GameEvent.model_validate_json(response)
                return event
            except (ValidationError, json.JSONDecodeError) as e:
                logger.warning(
                    f"Попытка {attempt}/{max_attempts} не удалась из-за ошибки валидации/парсинга JSON: {e}"
                )
                if attempt == max_attempts:
                    logger.critical(
                        "Все попытки генерации события через LLM завершились сбоем валидации. Применение fallback.",
                        exc_info=True,
                    )
                    return get_fallback_event()
            except Exception as e:
                logger.error(
                    f"Попытка {attempt}/{max_attempts} завершилась системной ошибкой API: {e}"
                )
                if attempt == max_attempts:
                    logger.critical(
                        "Все попытки генерации события завершились критической системной ошибкой. Применение fallback.",
                        exc_info=True,
                    )
                    return get_fallback_event()

        return get_fallback_event()
