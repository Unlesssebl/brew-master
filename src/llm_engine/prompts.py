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
