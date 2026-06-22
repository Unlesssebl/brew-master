# LLM Integration & AI Pipelines (Невидимый Гейм-мастер)

LLM используется исключительно как генератор контента и изолирована от бизнес-логики строгой типизацией. Модели не имеют прямого доступа к базе данных.

## 1. Рекомендованные модели (Google Gemini)
Для разных задач в игре используются разные версии моделей из-за баланса стоимости, скорости и лимитов (RPD).
- **События и квесты (Текст):** `gemini-2.5-flash` или `gemini-2.0-flash` (высокая скорость, 1500 RPD).
- **Генерация карточек патентов:** пайплайн из `gemini-2.5-pro` (сложный лор) + `imagen-4.0-fast-generate-001` (картинка).
- **Аудио-окружение в таверне:** `gemini-2.5-flash-native-audio-latest` (TTS).

## 2. Пайплайн Генерации Событий  
1. **Data Extraction:** Сбор агрегированного JSON-состояния игрока из БД (репутация, влияние, уровень таверны).  
2. **Prompt Assembly:** Формирование промпта с передачей JSON-состояния и жестким лимитированием параметров ответа (например, "gold_change не более 200").  
3. **LLM Call:** Запрос к API модели Gemini 2.5 Flash.  
4. **Pydantic Validation:** Парсинг ответа. Если ответ не валиден (не прошел бизнес-правила), делается до 2 retry-попыток.  
5. **Fallback:** При ошибке парсинга берется шаблонное событие из локальной таблицы `fallback_events`.

## 3. Валидационный контракт (Pydantic Schema)

Любой код ИИ-агента для обработки событий обязан использовать эту схему валидации:

```python
from pydantic import BaseModel, Field, field_validator
from typing import List

class EventChoice(BaseModel):
    choice_id: str = Field(..., description="ID выбора, например 'bribe_guard'")
    button_text: str = Field(..., max_length=30)
    result_text: str = Field(...)
    
    # Жесткие границы изменения состояния (Anti-Exploit)
    gold_change: int = Field(default=0, ge=-200, le=200)
    reputation_change: int = Field(default=0, ge=-15, le=15)
    influence_change: int = Field(default=0, ge=-10, le=10)

class GameEvent(BaseModel):
    event_title: str = Field(..., max_length=50)
    event_description: str = Field(...)
    choices: List[EventChoice] = Field(..., min_length=1, max_length=3)

    @field_validator('choices')
    def check_balance_logic(cls, choices):
        for choice in choices:
            # Проверяем наличие чистого положительного баффа без каких-либо затрат
            has_positive_gain = choice.gold_change > 0 or choice.reputation_change > 0 or choice.influence_change > 0
            has_any_cost = choice.gold_change < 0 or choice.reputation_change < 0 or choice.influence_change < 0
            
            # Если есть плюсы, но нет минусов (затрат), это нарушение баланса
            if has_positive_gain and not has_any_cost:
                raise ValueError("Выбор дает только положительные эффекты без видимых затрат. Нарушение баланса.")
        return choices
```

## 4. Пайплайн патентования и генерации карточек

Механика патентования уникальных рецептов задействует генеративный ИИ для повышения ценности крафта.

1. **Lore Prompt Assembly:** Сбор характеристик пива (крепость, горечь, аромат, стабильность) и последних 5 событий игрока.
2. **Structured Outputs:** Запрос к Gemini с использованием Pydantic-схемы `PatentLore` (поля `name` и `lore`) для получения поэтичного фэнтези-названия и описания напитка.
3. **Image Generation:** Генерация фэнтезийной иллюстрации бутылки/зелья через Imagen 3.
4. **Telegram Delivery & Caching:** Отправка карточки игроку в чат и кэширование `file_id` картинки в `card_image_file_id` таблицы патентов для мгновенного просмотра в погребе без повторного вызова API.

## 5. Автономные ИИ-Конкуренты (Rival CEOs)

Скрипты, симулирующие действия рыночных ботов.
- **Триггер:** Раз в 12 часов.
- **Вход:** Агрегация рынка (самые продаваемые рецепты).  
- **Выход:** Специфичное JSON-действие `{"action": "dumping", "target_market": "elves"}`.  
- **Обработка:** Движок читает JSON, применяет математический штраф к выбранному рынку и транслирует новость в глобальный лор.
