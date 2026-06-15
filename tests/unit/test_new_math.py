import pytest
from datetime import datetime, timedelta
from src.config import settings
from src.core.config import GameBalance
from src.core.prestige import calculate_prestige_crystals
from src.core.expeditions import (
    ExpeditionEventType,
    calculate_expedition_event_chance,
    calculate_expedition_outcome,
    calculate_injury_consequences,
)
from src.core.staff_events import calculate_staff_event_chance
from src.core.offline_progress import calculate_offline_production


def test_game_balance_config():
    # Проверка значений по умолчанию
    balance = settings.GameBalance
    assert balance.market_saturation_threshold == 500
    assert balance.market_saturation_lambda == 0.005
    assert balance.prestige_crystal_divisor == 1000000.0
    assert balance.base_ingredient_costs["malt"] == 1.0
    assert balance.offline_max_hours == 24
    assert balance.offline_efficiency_multiplier == 0.5
    assert balance.expedition_heavy_injury_cost == 200.0


def test_calculate_prestige_crystals():
    # Проверка работы корректных значений
    assert calculate_prestige_crystals(1000000.0) == 1
    assert calculate_prestige_crystals(2500000.0) == 2
    assert calculate_prestige_crystals(10000000.0) == 10

    # Проверка исключения при значении меньше 1000000
    with pytest.raises(ValueError, match="Недостаточно общего заработка"):
        calculate_prestige_crystals(999999.9)


def test_calculate_expedition_event_chance():
    # Шанс = (Skill + Equipment_bonus) / 100
    assert calculate_expedition_event_chance(50, 10) == 0.6
    assert calculate_expedition_event_chance(80, 0) == 0.8
    assert calculate_expedition_event_chance(0, 5) == 0.05


def test_calculate_expedition_outcome():
    # Проверка структуры результатов для каждого типа события
    for event_type in ExpeditionEventType:
        outcome = calculate_expedition_outcome(50, event_type, equipment_bonus=10)
        assert "success" in outcome
        assert isinstance(outcome["success"], bool)
        assert "reward_multiplier" in outcome
        assert isinstance(outcome["reward_multiplier"], float)
        assert "injury_risk" in outcome
        assert isinstance(outcome["injury_risk"], float)

        if outcome["success"]:
            assert outcome["reward_multiplier"] > 0.0
            assert outcome["injury_risk"] == 0.0
        else:
            assert outcome["reward_multiplier"] == 0.0
            assert outcome["injury_risk"] > 0.0


def test_calculate_injury_consequences():
    # Тяжелая травма
    heavy = calculate_injury_consequences(is_heavy=True)
    assert heavy["blocked_hours"] == 48
    assert heavy["gold_cost"] == settings.GameBalance.expedition_heavy_injury_cost

    # Легкая травма
    light = calculate_injury_consequences(is_heavy=False)
    assert light["blocked_hours"] == 12
    assert light["gold_cost"] == 0.0


def test_calculate_staff_event_chance():
    # P = min(90.0, ((100 - loyalty) * 0.5 + (fatigue * 0.3))) / 100
    # loyalty=100, fatigue=0 -> P = min(90.0, 0) / 100 = 0.0
    assert calculate_staff_event_chance(100, 0) == 0.0

    # loyalty=0, fatigue=100 -> P = min(90.0, 50 + 30) / 100 = 80 / 100 = 0.8
    assert calculate_staff_event_chance(0, 100) == 0.8

    # loyalty=0, fatigue=0 -> P = min(90.0, 50) / 100 = 0.5
    assert calculate_staff_event_chance(0, 0) == 0.5

    # Проверка ограничения сверху (90% / 0.9): loyalty=10, fatigue=100 -> P = min(90, 45 + 30 = 75) -> 0.75
    assert calculate_staff_event_chance(10, 100) == 0.75

    # Превышение лимита в 90: loyalty=0, fatigue=150 -> 50 + 45 = 95 -> min(90, 95) = 90 -> 0.9
    # (Хотя fatigue макс 100, проверим формулу с выходом за рамки)
    assert calculate_staff_event_chance(0, 150) == 0.9

    # Проверка валидации входных данных
    with pytest.raises(ValueError, match="loyalty"):
        calculate_staff_event_chance(-1, 50)
    with pytest.raises(ValueError, match="loyalty"):
        calculate_staff_event_chance(101, 50)
    with pytest.raises(ValueError, match="fatigue"):
        calculate_staff_event_chance(50, -1)



def test_calculate_offline_production():
    now = datetime.now()
    base_rate = 10.0

    # Разница <= 0
    assert calculate_offline_production(now, now, base_rate) == 0.0
    assert calculate_offline_production(now, now - timedelta(hours=1), base_rate) == 0.0

    # Разница <= 4 часов (без штрафа)
    # 3 часа * 10 = 30.0
    assert calculate_offline_production(now - timedelta(hours=3), now, base_rate) == 30.0

    # Разница > 4 часов, но меньше лимита 24 часов (со штрафом 0.5)
    # 5 часов * (10 * 0.5) = 25.0
    assert calculate_offline_production(now - timedelta(hours=5), now, base_rate) == 25.0

    # Разница больше лимита 24 часов (ограничивается 24 часами, со штрафом 0.5)
    # 24 часа * (10 * 0.5) = 120.0
    assert calculate_offline_production(now - timedelta(hours=30), now, base_rate) == 120.0
