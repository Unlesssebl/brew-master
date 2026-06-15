import logging
from typing import Any

from google import genai

from src.config import settings
from src.llm_engine.schemas import GameEvent

logger = logging.getLogger(__name__)


def get_genai_client() -> genai.Client:
    """
    Инициализирует и возвращает клиент Google GenAI.
    """
    if not settings.GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY is not set in configuration!")
    return genai.Client(api_key=settings.GEMINI_API_KEY)


async def generate_player_event(player_state: dict[str, Any]) -> GameEvent:
    """
    Генерирует уникальное событие для игрока на основе его JSON-состояния.
    Применяет динамическую тональность.
    """
    pass


async def generate_rival_ceo_action(market_state: dict[str, Any]) -> dict[str, Any]:
    """
    Генерирует действие для бота-конкурента на основе состояния рынка.
    """
    pass
