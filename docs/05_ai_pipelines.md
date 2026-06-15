
Markdown  
\# LLM Pipelines (Невидимый Гейм-мастер)

LLM используется исключительно как генератор контента и изолирована от бизнес-логики строгой типизацией.

\#\# 1\. Пайплайн Генерации Событий  
1\.  \*\*Data Extraction:\*\* Сбор агрегированного JSON-состояния игрока из БД (репутация, влияние, уровень таверны).  
2\.  \*\*Prompt Assembly:\*\* Формирование промпта с передачей JSON-состояния и жестким лимитированием параметров ответа (например, "gold\_change не более 200").  
3\.  \*\*LLM Call:\*\* Запрос к API модели.  
4\.  \*\*Pydantic Validation:\*\* Парсинг ответа. Если ответ не валиден, делается 2 retry-попытки.  
5\.  \*\*Fallback:\*\* При ошибке парсинга берется шаблонное событие из таблицы \`fallback\_events\`.

## 2. Валидационный контракт (Pydantic Schema)

Любой код ИИ-агента для обработки событий обязан использовать эту схему валидации:

```python
from pydantic import BaseModel, Field, field_validator
from typing import List

class EventChoice(BaseModel):
    choice_id: str = Field(..., description="ID выбора, например 'bribe_guard'")
    button_text: str = Field(..., max_length=30)
    result_text: str = Field(...)
    
    # Жесткие границы изменения состояния
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
            # Проверяем наличие чистого положительного增益 без каких-либо затрат
            has_positive_gain = choice.gold_change > 0 or choice.reputation_change > 0 or choice.influence_change > 0
            has_any_cost = choice.gold_change < 0 or choice.reputation_change < 0 or choice.influence_change < 0
            
            # Если есть плюсы, но нет минусов (затрат), это нарушение баланса
            if has_positive_gain and not has_any_cost:
                raise ValueError("Выбор дает только положительные эффекты без видимых затрат. Нарушение баланса.")
        return choices

## **3\. Автономные ИИ-Конкуренты (Rival CEOs)**

Скрипты, симулирующие действия рыночных игроков.

* **Триггер:** Раз в 12 часов (cron task \-\> queue).  
* **Вход:** Агрегация рынка (самые продаваемые рецепты).  
* **Выход:** Специфичное JSON-действие {"action": "dumping", "target\_market": "elves"}.  
* **Обработка:** Движок читает JSON, применяет $D\_{penalty}$ к выбранному рынку и транслирует новость в глобальный лор.

Такое разделение контекста — это залог того, что если вы поручите ИИ написать эндпоинт для расчета Горечи, он не попытается переписать структуру базы данных.  