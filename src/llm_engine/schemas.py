from pydantic import BaseModel, Field, field_validator


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
    choices: list[EventChoice] = Field(..., min_length=1, max_length=3)

    @field_validator("choices")
    @classmethod
    def check_balance_logic(cls, choices: list[EventChoice]) -> list[EventChoice]:
        for choice in choices:
            # Проверяем наличие чистого положительного прироста без каких-либо затрат
            has_positive_gain = (
                choice.gold_change > 0
                or choice.reputation_change > 0
                or choice.influence_change > 0
            )
            has_any_cost = (
                choice.gold_change < 0
                or choice.reputation_change < 0
                or choice.influence_change < 0
            )

            # Если есть плюсы, но нет минусов (затрат), это нарушение баланса
            if has_positive_gain and not has_any_cost:
                raise ValueError(
                    f"Выбор '{choice.choice_id}' дает положительные эффекты без видимых затрат. "
                    "Нарушение баланса."
                )
        return choices
