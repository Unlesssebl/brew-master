import logging
from config import settings

logger = logging.getLogger("llm_api_client")


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
