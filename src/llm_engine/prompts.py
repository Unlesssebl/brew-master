import json
from typing import Any

SYSTEM_EVENT_PROMPT = """Ты — невидимый Гейм-мастер в экономической стратегии "Пивная Империя".
Твоя задача — сгенерировать уникальное случайное игровое событие для игрока на основе его текущего состояния.

Правила генерации события:
1. Верни ТОЛЬКО валидный JSON, соответствующий Pydantic-схеме (без markdown-оберток вроде ```json и ```). Ответ должен начинаться с {{ и заканчиваться на }}.
2. Диапазоны наград/штрафов для выбора (choices) строго в пределах:
   - gold_change: [-200, 200]
   - reputation_change: [-15, 15]
   - influence_change: [-10, 10]
3. Динамическая тональность:
   - Если в player_state['reputation'] > 50, стиль текста должен быть официальным (королевские указы).
   - Если в player_state['reputation'] < -10, стиль должен быть нуарным/криминальным (сводки наемников).
   - В остальных случаях используй нейтрально-атмосферный фэнтези-стиль.
4. Баланс выбора: Ни один выбор не должен давать чистый положительный прирост (gold_change > 0 или reputation_change > 0 или influence_change > 0) без каких-либо затрат (gold_change < 0 или reputation_change < 0 или influence_change < 0).

Формат схемы JSON для ответа:
{{
    "event_title": "Название события (строка до 50 символов)",
    "event_description": "Описание события (текст)",
    "choices": [
        {{
            "choice_id": "ID выбора (строка)",
            "button_text": "Текст на кнопке выбора (строка до 30 символов)",
            "result_text": "Описание последствий выбора (текст)",
            "gold_change": целое число,
            "reputation_change": целое число,
            "influence_change": целое число
        }}
    ]
}}

Текущее состояние игрока:
{player_state}

Выбранная тональность на основе репутации игрока: {tone_style}
"""


def build_event_prompt(player_state: dict[str, Any]) -> str:
    """
    Формирует промпт для генерации игрового события на основе состояния игрока.
    """
    reputation = player_state.get("reputation", 0)
    if reputation > 50:
        tone_style = "Официальный стиль (королевские указы)"
    elif reputation < -10:
        tone_style = "Нуарный/криминальный стиль (сводки наемников)"
    else:
        tone_style = "Нейтрально-атмосферный фэнтези-стиль"

    player_state_json = json.dumps(player_state, ensure_ascii=False, indent=2)
    return SYSTEM_EVENT_PROMPT.format(player_state=player_state_json, tone_style=tone_style)


SYSTEM_PATENT_LORE_PROMPT = """Ты — летописец пивоваренной гильдии. Игрок зарегистрировал патент на новый сорт пива.
Твоя задача — сгенерировать:
1. Поэтичное название сорта (до 40 символов, на русском, фэнтезийный стиль, без кавычек вокруг названия)
2. Лор — 2-3 предложения о вкусе, истории и легенде этого пива.

Ты НЕ изменяешь и НЕ придумываешь характеристики. Характеристики ДАНЫ:
- Крепость: {strength} | Горечь: {bitterness} | Аромат: {aroma}
- Стабильность: {stability}% | Качество: {quality_modifier}x

История пивовара (последние события):
{player_history}

Правило: верни ТОЛЬКО JSON без markdown-оберток (вроде ```json и ```). Ответ должен начинаться с {{ и заканчиваться на }}.
Формат схемы JSON для ответа:
{{
    "name": "Название сорта пива (строка до 40 символов)",
    "lore": "История и описание вкуса (строка до 300 символов)"
}}
"""


def build_patent_lore_prompt(recipe_stats: dict[str, Any], player_history: list[str]) -> str:
    """
    Формирует промпт для генерации лора патента на основе характеристик рецепта и истории игрока.
    """
    history_text = "\n".join([f"- {event}" for event in player_history]) if player_history else "История пуста."
    return SYSTEM_PATENT_LORE_PROMPT.format(
        strength=recipe_stats.get("strength", 0),
        bitterness=recipe_stats.get("bitterness", 0),
        aroma=recipe_stats.get("aroma", 0),
        stability=recipe_stats.get("stability", 0),
        quality_modifier=recipe_stats.get("quality_modifier", 1.0),
        player_history=history_text
    )
