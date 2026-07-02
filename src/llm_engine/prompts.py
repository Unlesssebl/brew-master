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
   - suspicion_change: [-15, 15]
3. Динамическая тональность:
   - Если в player_state['reputation'] > 50, стиль текста должен быть официальным (королевские указы).
   - Если в player_state['reputation'] < -10, стиль должен быть нуарным/криминальным (сводки наемников).
   - Если в player_state['suspicion'] > 40, сгенерируй событие об угрозе: облава стражи, внеплановая проверка, шантаж.
   - В остальных случаях используй нейтрально-атмосферный фэнтези-стиль.
4. Баланс выбора: Ни один выбор не должен давать чистый положительный прирост без каких-либо затрат.
5. Интеграция броска кубиков (2d6):
   - Обязательно сгенерируй хотя бы один из вариантов выбора с проверкой навыка (requires_dice_roll = true).
   - Укажи сложность проверки dice_dc (от 5 до 12).
   - Укажи проверяемый стат dice_stat (одно из: reputation, influence, suspicion, alchemist_skill, merchant_skill). Для suspicion успешной считается проверка, если результат МЕНЬШЕ или РАВЕН (так как это негативный стат, чем меньше тем лучше, но механика кубиков прибавляет стат. Точнее механика кубиков вычтет suspicion/10).
   - Для выбора с кубиками заполни success_* и fail_* поля, а обычные change-поля и result_text оставь пустыми (или 0).

Формат схемы JSON для ответа:
{{
    "event_title": "Название события (строка до 50 символов)",
    "event_description": "Описание события (текст)",
    "choices": [
        {{
            "choice_id": "ID выбора (строка)",
            "button_text": "Краткий текст на кнопке (ОЧЕНЬ КРАТКО, до 30 символов, не более 3-4 слов)",
            "result_text": "Описание последствий (если без кубиков)",
            "gold_change": 0,
            "reputation_change": 0,
            "influence_change": 0,
            "suspicion_change": 0,
            "requires_dice_roll": true,
            "dice_dc": 8,
            "dice_stat": "reputation",
            "success_result_text": "Описание успеха",
            "fail_result_text": "Описание провала",
            "success_gold_change": 50,
            "fail_gold_change": -50,
            "success_reputation_change": 2,
            "fail_reputation_change": -2,
            "success_influence_change": 1,
            "fail_influence_change": -1,
            "success_suspicion_change": -5,
            "fail_suspicion_change": 10
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
    suspicion = player_state.get("suspicion", 0)
    if suspicion > 40:
        tone_style = "Угроза (облава стражи, шантаж, проверка)"
    elif reputation > 50:
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
    "lore": "История и описание вкуса (строка до 1000 символов)"
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
