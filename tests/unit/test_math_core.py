import pytest

from src.core.crafting import BeerStatsDTO, calculate_beer_stats
from src.core.economy import (
    FractionMultiplier,
    calculate_final_barrel_price,
    calculate_final_price,
    calculate_market_saturation_penalty,
    calculate_patent_daily_tax,
    calculate_patent_tax,
    calculate_royalty_payouts,
    calculate_saturation_penalty,
)
from src.core.pvp import (
    calculate_reverse_engineering_chance,
    calculate_sabotage_chance,
)


def test_calculate_beer_stats_valid():
    # M=30, W=40, H=20, Y=10 (sum = 100)
    # Skill = 50, Fatigue = 0
    stats = calculate_beer_stats(30, 40, 20, 10, 50, 0)
    assert isinstance(stats, BeerStatsDTO)
    assert isinstance(stats.strength, float)
    assert isinstance(stats.bitterness, float)
    assert isinstance(stats.aroma, float)
    assert isinstance(stats.stability, int)

    # Verify calculated values are rounded appropriately
    # Str: (30 * sqrt(10) / 15) * (1.2 - 40/100) = (2 * 3.162277) * 0.8 = 6.3245 * 0.8 = 5.06
    assert stats.strength == pytest.approx(5.06, abs=0.01)
    # Bit: (20 * 1.5 / sqrt(4 + 1)) + 30 / 20 = 30 / sqrt(5) + 1.5 = 13.4164 + 1.5 = 14.92
    assert stats.bitterness == pytest.approx(14.92, abs=0.01)
    # Aro: (20 * 0.8 + 30 * 0.3 + 10 * 0.2) / (1 + 14.9164 / 20) = 27 / 1.74582 = 15.47
    assert stats.aroma == pytest.approx(15.47, abs=0.01)
    # Stab: St_base = 100 - 3 * |10 - 12| - 2 * max(0, 40 - 50) = 100 - 6 - 0 = 94
    # Stab = min(100, max(0, 94 + floor(50/2))) = min(100, 94 + 25) = 100
    assert stats.stability == 100


def test_calculate_beer_stats_validation():
    # Sum of ingredients is not 100
    with pytest.raises(ValueError, match="Сумма пропорций"):
        calculate_beer_stats(20, 20, 20, 20, 50, 0)

    # Ingredient value out of bounds
    with pytest.raises(ValueError, match="диапазоне от 0 до 100"):
        calculate_beer_stats(-10, 50, 30, 30, 50, 0)

    with pytest.raises(ValueError, match="диапазоне от 0 до 100"):
        calculate_beer_stats(105, -5, 0, 0, 50, 0)

    # Skill value out of bounds
    with pytest.raises(ValueError, match="Навык алхимика"):
        calculate_beer_stats(30, 40, 20, 10, 0, 0)

    with pytest.raises(ValueError, match="Навык алхимика"):
        calculate_beer_stats(30, 40, 20, 10, 101, 0)


def test_economy_fraction_multiplier():
    assert FractionMultiplier.DWARVES == 2.0
    assert FractionMultiplier.GNOMES == 2.0
    assert FractionMultiplier.ELVES == 0.8
    assert FractionMultiplier.GOBLINS == 0.2


def test_economy_patent_tax():
    # Tax_daily = 50 + (daily_royalty * 0.15)
    assert calculate_patent_tax(100.0) == 65.0
    assert calculate_patent_daily_tax(200.0) == 80.0
    assert calculate_patent_tax(0.0) == 50.0


def test_economy_royalty_payouts():
    class MockTx:
        def __init__(self, volume, price, market_type):
            self.volume = volume
            self.price = price
            self.market_type = market_type

    txs = [
        MockTx(10, 100.0, "legal"),
        MockTx(5, 50.0, "grey"),
        MockTx(20, 10.0, "black"),  # Should be ignored
        {"volume": 10, "price": 100.0, "market_type": "legal"},
        {"volume": 2, "price": 50.0, "market_type": "invalid"},  # Should be ignored
    ]
    # (10 * 100 * 0.05) + (5 * 50 * 0.05) + (10 * 100 * 0.05) = 50 + 12.5 + 50 = 112.5
    assert calculate_royalty_payouts(txs) == 112.5


def test_economy_saturation_penalty():
    # D_penalty = e^(-lambda * max(0, V - Threshold))
    # V=600, Threshold=500, Lambda=0.001 -> e^(-0.001 * 100) = e^(-0.1) = 0.904837
    val1 = calculate_saturation_penalty(600.0, 500, 0.001)
    assert val1 == 0.9048

    # Under threshold -> e^0 = 1.0000
    val2 = calculate_market_saturation_penalty(400.0, 500.0, 0.001)
    assert val2 == 1.0


def test_economy_final_price():
    # base=100.0, k_market=2.0, k_quality=1.5, d_penalty=0.9048
    # 100.0 * 2.0 * 1.5 * 0.9048 = 300.0 * 0.9048 = 271.44
    assert calculate_final_price(100.0, 2.0, 1.5, 0.9048) == 271.44
    assert calculate_final_barrel_price(100.0, 2.0, 1.5, 0.9048) == 271.44


def test_pvp_reverse_engineering_chance():
    # min(95, max(5, 60 + Skill / 2))
    assert calculate_reverse_engineering_chance(50) == 85
    assert calculate_reverse_engineering_chance(100) == 95  # 60 + 50 = 110 -> 95
    assert (
        calculate_reverse_engineering_chance(1) == 60
    )  # 60 + 0.5 = 60.5 -> int(60.5) = 60 (actually if math.floor or int is used)


def test_pvp_sabotage_chance():
    # min(90, max(10, Base_chance + Influence_atk - Guard_lvl * 10))
    # base=50, influence=20, guard=3 -> 50 + 20 - 30 = 40
    assert calculate_sabotage_chance(20, 3, 50.0) == 40
    # Capped at 90: base=50, influence=60, guard=0 -> 110 -> 90
    assert calculate_sabotage_chance(60, 0, 50.0) == 90
    # Capped at 10: base=50, influence=0, guard=6 -> 50 - 60 = -10 -> 10
    assert calculate_sabotage_chance(0, 6, 50.0) == 10
