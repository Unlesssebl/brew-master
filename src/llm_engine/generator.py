import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any, cast

from pydantic import ValidationError

from src.llm_engine.prompts import build_event_prompt, build_patent_lore_prompt
from src.llm_engine.schemas import GameEvent, get_fallback_event, PatentLore, get_fallback_patent_lore

logger = logging.getLogger(__name__)


class LLMEventGenerator:
    """
    Класс для генерации игровых событий с использованием LLM.
    Реализует пайплайн: создание промпта, запрос к LLM, валидация и обработка ошибок.
    """

    def __init__(self, call_llm_api: Callable[[str], Awaitable[str]] | None = None) -> None:
        """
        Инициализация генератора.

        :param call_llm_api: Асинхронный вызываемый объект (async def (prompt: str) -> str)
        """
        if call_llm_api is None:
            from src.llm_engine.api_client import call_llm_api as default_call
            self._call_llm_api: Callable[[str], Awaitable[str]] = cast(Callable[[str], Awaitable[str]], default_call)
        else:
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


class LLMPatentLoreGenerator:
    """
    Класс для генерации поэтичного лора и фэнтезийного названия рецепта пива.
    """

    def __init__(self, call_llm_api: Callable[[str], Awaitable[str]] | None = None) -> None:
        """
        Инициализация генератора.
        """
        if call_llm_api is None:
            from src.llm_engine.api_client import call_llm_api as default_call
            self._call_llm_api: Callable[[str], Awaitable[str]] = cast(Callable[[str], Awaitable[str]], default_call)
        else:
            self._call_llm_api = call_llm_api

    async def generate_patent_lore(
        self, recipe_stats: dict[str, Any], player_history: list[str], style: str = "пиво"
    ) -> PatentLore:
        """
        Генерирует лор патента:
        - Строит промпт на основе рецепта и истории игрока.
        - Вызывает LLM API (до 3 попыток).
        - Парсит и валидирует ответ через PatentLore.
        - При ошибке возвращает fallback.
        """
        prompt = build_patent_lore_prompt(recipe_stats, player_history)
        max_attempts = 3

        for attempt in range(1, max_attempts + 1):
            try:
                response = await self._call_llm_api(prompt)
                # Очистим возможную обертку markdown (на всякий случай)
                if response.strip().startswith("```"):
                    lines = response.strip().splitlines()
                    if lines[0].startswith("```"):
                        lines = lines[1:]
                    if lines[-1].startswith("```"):
                        lines = lines[:-1]
                    response = "\n".join(lines).strip()
                
                lore = PatentLore.model_validate_json(response)
                return lore
            except (ValidationError, json.JSONDecodeError) as e:
                logger.warning(
                    f"Попытка {attempt}/{max_attempts} генерации лора не удалась из-за ошибки валидации/парсинга: {e}"
                )
                if attempt == max_attempts:
                    logger.critical(
                        "Все попытки генерации лора через LLM завершились сбоем. Применение fallback.",
                        exc_info=True,
                    )
                    return get_fallback_patent_lore(style)
            except Exception as e:
                logger.error(
                    f"Попытка {attempt}/{max_attempts} генерации лора завершилась ошибкой API: {e}"
                )
                if attempt == max_attempts:
                    logger.critical(
                        "Все попытки генерации лора завершились критической системной ошибкой. Применение fallback.",
                        exc_info=True,
                    )
                    return get_fallback_patent_lore(style)

        return get_fallback_patent_lore(style)
