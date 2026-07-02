from pydantic import BaseModel, Field, field_validator


class EventChoice(BaseModel):
    choice_id: str = Field(..., description="ID выбора, например 'bribe_guard'")
    button_text: str = Field(..., max_length=35)
    result_text: str = Field(...)

    @field_validator("button_text", mode="before")
    @classmethod
    def truncate_button_text(cls, v: str) -> str:
        if isinstance(v, str) and len(v) > 35:
            return v[:32] + "..."
        return v

    # Жесткие границы изменения состояния
    gold_change: int = Field(default=0, ge=-200, le=200)
    reputation_change: int = Field(default=0, ge=-15, le=15)
    influence_change: int = Field(default=0, ge=-10, le=10)
    suspicion_change: int = Field(default=0, ge=-15, le=15)

    # Новые поля для механики кубиков (2d6)
    requires_dice_roll: bool = Field(default=False)
    dice_dc: int | None = Field(default=None, description="Сложность проверки (DC), например 7 или 8")
    dice_stat: str | None = Field(default=None, description="Проверяемый стат: reputation, influence, alchemist_skill, merchant_skill, suspicion")
    
    success_result_text: str | None = Field(default=None)
    fail_result_text: str | None = Field(default=None)
    
    success_gold_change: int | None = Field(default=None, ge=-200, le=200)
    fail_gold_change: int | None = Field(default=None, ge=-200, le=200)
    
    success_reputation_change: int | None = Field(default=None, ge=-15, le=15)
    fail_reputation_change: int | None = Field(default=None, ge=-15, le=15)
    
    success_influence_change: int | None = Field(default=None, ge=-10, le=10)
    fail_influence_change: int | None = Field(default=None, ge=-10, le=10)

    success_suspicion_change: int | None = Field(default=None, ge=-15, le=15)
    fail_suspicion_change: int | None = Field(default=None, ge=-15, le=15)


class GameEvent(BaseModel):
    event_title: str = Field(..., max_length=50)
    event_description: str = Field(...)
    choices: list[EventChoice] = Field(..., min_length=1, max_length=3)

    @field_validator("choices")
    @classmethod
    def check_balance_logic(cls, choices: list["EventChoice"]) -> list["EventChoice"]:
        for choice in choices:
            if choice.requires_dice_roll:
                # Если это бросок кубиков, предполагаем что риск и награда сбалансированы 
                # (обычно успех = профит, провал = штраф)
                continue
                
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
                or choice.suspicion_change > 0
            )

            # Если есть плюсы, но нет минусов (затрат), это нарушение баланса
            if has_positive_gain and not has_any_cost:
                raise ValueError(
                    "Выбор дает только положительные эффекты без видимых затрат. Нарушение баланса."
                )
        return choices


def get_fallback_event() -> GameEvent:
    """
    Возвращает безопасный дефолтный объект GameEvent (нейтральное событие с нулевыми изменениями ресурсов),
    который используется при полном отказе LLM.
    """
    return GameEvent(
        event_title="Спокойный день",
        event_description="Сегодня в таверне на удивление спокойно. Посетители мирно пьют пиво, никаких происшествий не происходит.",
        choices=[
            EventChoice(
                choice_id="fallback_continue",
                button_text="Продолжить работу",
                result_text="День проходит без приключений и лишних трат.",
                gold_change=0,
                reputation_change=0,
                influence_change=0,
                suspicion_change=0,
                requires_dice_roll=False,
            )
        ],
    )


class PatentLore(BaseModel):
    name: str = Field(..., max_length=40)
    lore: str = Field(..., max_length=1500)

    @field_validator("name", mode="before")
    @classmethod
    def truncate_name(cls, v: str) -> str:
        if isinstance(v, str) and len(v) > 40:
            return v[:37] + "..."
        return v


def get_fallback_patent_lore(style: str = "пиво") -> PatentLore:
    """
    Возвращает безопасный дефолтный объект PatentLore при отказе LLM.
    """
    return PatentLore(
        name=f"Безымянное {style}",
        lore="История этого напитка окутана туманом неизвестности. Летописец пивной гильдии, похоже, заснул в кружке эля...",
    )
