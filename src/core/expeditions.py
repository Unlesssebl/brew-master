"""
Модуль для расчета результатов рогалик-экспедиций агентов.
Подробности в docs/01_gdd.md и docs/04_math_and_economy.md.
"""

import random
from enum import Enum

from src.config import settings


class ExpeditionEventType(str, Enum):
    """
    Типы событий в экспедициях.
    """

    BANDITS = "BANDITS"
    TRADE_OFFER = "TRADE_OFFER"
    MYSTICAL_FIND = "MYSTICAL_FIND"


def calculate_expedition_event_chance(agent_skill: int, equipment_bonus: int = 0) -> float:
    """
    Вычисляет шанс успешного исхода события в экспедиции.
    Формула: Chance = (Skill + Equipment_bonus) / 100
    """
    return (agent_skill + equipment_bonus) / 100.0


def calculate_expedition_outcome(
    agent_skill: int, event_type: ExpeditionEventType, equipment_bonus: int = 0
) -> dict:
    """
    Рассчитывает исход события в экспедиции.

    Входные параметры:
    - agent_skill: навык агента (1-100)
    - event_type: тип события (ExpeditionEventType)
    - equipment_bonus: бонус экипировки (по умолчанию 0)

    Возвращает словарь:
    {
        "success": bool,
        "reward_multiplier": float,
        "injury_risk": float
    }
    """
    # Базовые шансы
    base_chances = {
        ExpeditionEventType.BANDITS: 40,
        ExpeditionEventType.TRADE_OFFER: 70,
        ExpeditionEventType.MYSTICAL_FIND: 50,
    }

    base_chance = base_chances.get(event_type, 50)

    # Итоговый шанс
    final_chance = min(95, max(5, base_chance + (agent_skill / 2) + equipment_bonus))

    # Бросок на успех
    success = (random.random() * 100.0) <= final_chance

    # Расчет множителя награды и риска травмы
    if success:
        injury_risk = 0.0
        if event_type == ExpeditionEventType.BANDITS:
            reward_multiplier = 1.5 + (agent_skill / 100.0)
        elif event_type == ExpeditionEventType.TRADE_OFFER:
            reward_multiplier = 1.2 + (agent_skill / 100.0)
        else:  # MYSTICAL_FIND
            reward_multiplier = 2.0 + (agent_skill / 100.0)
    else:
        reward_multiplier = 0.0
        if event_type == ExpeditionEventType.BANDITS:
            injury_risk = max(0.1, 0.6 - (agent_skill / 200.0) - (equipment_bonus / 100.0))
        elif event_type == ExpeditionEventType.TRADE_OFFER:
            injury_risk = max(0.01, 0.1 - (agent_skill / 200.0))
        else:  # MYSTICAL_FIND
            injury_risk = max(0.05, 0.4 - (agent_skill / 200.0))

    return {
        "success": success,
        "reward_multiplier": round(reward_multiplier, 4),
        "injury_risk": round(injury_risk, 4),
    }


def calculate_injury_consequences(is_heavy: bool) -> dict:
    """
    Рассчитывает последствия травмы агента.

    Если травма тяжелая (is_heavy=True):
    - Блокировка на 48 часов.
    - Стоимость лечения = settings.GameBalance.expedition_heavy_injury_cost.

    Если легкая (is_heavy=False):
    - Блокировка на 12 часов.
    - Стоимость лечения = 0.0.
    """
    if is_heavy:
        return {
            "blocked_hours": 48,
            "gold_cost": float(settings.GameBalance.expedition_heavy_injury_cost),
        }
    else:
        return {"blocked_hours": 12, "gold_cost": 0.0}
