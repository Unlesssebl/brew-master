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
        from src.llm_engine.schemas import get_fallback_event
        return get_fallback_event().model_dump_json()

    try:
        from google import genai

        # Инициализируем клиент Google GenAI
        client = genai.Client(api_key=settings.LLM_API_KEY)
        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        return response.text or ""
    except Exception as e:
        logger.error(f"Ошибка при вызове Gemini API: {e}", exc_info=True)
        raise


async def generate_patent_image(prompt: str) -> bytes | None:
    """
    Генерирует изображение для патента с помощью Imagen 3.
    """
    if not settings.LLM_API_KEY:
        logger.warning("LLM_API_KEY не задан. Картинка патента не будет сгенерирована.")
        return None

    try:
        from google import genai
        import asyncio

        def _sync_generate():
            client = genai.Client(api_key=settings.LLM_API_KEY)
            response = client.models.generate_images(
                model='imagen-3.0-generate-002',
                prompt=prompt,
                config=dict(
                    number_of_images=1,
                    output_mime_type="image/jpeg",
                    aspect_ratio="1:1"
                )
            )
            if response.generated_images:
                img_obj = response.generated_images[0].image
                if img_obj is not None:
                    return img_obj.image_bytes
            return None

        return await asyncio.to_thread(_sync_generate)
    except Exception as e:
        err_msg = str(e)
        if "404" in err_msg or "NOT_FOUND" in err_msg:
            logger.warning(
                "Генерация изображений через Imagen API недоступна (ошибка 404). "
                "Вероятно, ваш API-ключ Gemini находится на бесплатном тарифе (Free Tier), который не поддерживает генерацию картинок."
            )
        else:
            logger.error(f"Ошибка при генерации изображения через Imagen API: {e}", exc_info=True)
        return None
