import math
import random
from dataclasses import dataclass


@dataclass(slots=True)
class BeerStatsDTO:
    """
    DTO для хранения характеристик пива.
    """

    strength: float
    bitterness: float
    aroma: float
    stability: int


def calculate_strength(
    malt_pct: int,
    water_pct: int,
    hop_pct: int,
    yeast_pct: int,
) -> float:
    """
    Рассчитывает крепость пива (Strength).
    Формула: Str = min(20.0, (M * sqrt(Y) / 15) * (1.2 - W / 100))
    """
    if yeast_pct < 0:
        return 0.0
    str_val = (malt_pct * math.sqrt(yeast_pct) / 15.0) * (1.2 - water_pct / 100.0)
    return float(min(20.0, max(0.0, str_val)))


def calculate_bitterness(
    malt_pct: int,
    water_pct: int,
    hop_pct: int,
    yeast_pct: int,
) -> float:
    """
    Рассчитывает горечь пива (Bitterness).
    Формула: Bit = min(20.0, (H * 1.5 / sqrt(W / 10 + 1)) + M / 20)
    """
    if water_pct < 0:
        return 0.0
    bit_val = (hop_pct * 1.5 / math.sqrt(water_pct / 10.0 + 1.0)) + malt_pct / 20.0
    return float(min(20.0, max(0.0, bit_val)))


def calculate_aroma(
    malt_pct: int,
    water_pct: int,
    hop_pct: int,
    yeast_pct: int,
    bitterness: float,
) -> float:
    """
    Рассчитывает аромат пива (Aroma).
    Формула: Aro = min(20.0, (H * 0.8 + M * 0.3 + Y * 0.2) / (1 + Bit / 20))
    """
    denom = 1.0 + bitterness / 20.0
    if denom <= 0:
        denom = 1.0
    aro_val = (hop_pct * 0.8 + malt_pct * 0.3 + yeast_pct * 0.2) / denom
    return float(min(20.0, max(0.0, aro_val)))


def calculate_stability(
    yeast_pct: int,
    water_pct: int,
    skill: int,
    fatigue: int,
) -> int:
    """
    Рассчитывает стабильность партии пива (Stability).
    Применяет принудительный риск брака (stability <= 30), если усталость сотрудника > 80.
    Формулы:
    St_base = 100 - 3 * |Y - 12| - 2 * max(0, W - 50)
    Stab = min(100, max(0, St_base + floor(Skill / 2)))
    """
    st_base = 100 - 3 * abs(yeast_pct - 12) - 2 * max(0, water_pct - 50)
    stab = st_base + math.floor(skill / 2)

    if fatigue > 80:
        if random.random() < 0.25:
            stab = min(30, st_base)

    return int(min(100, max(0, stab)))


def calculate_beer_stats(
    malt_pct: int,
    water_pct: int,
    hop_pct: int,
    yeast_pct: int,
    skill: int,
    fatigue: int = 0,
) -> BeerStatsDTO:
    """
    Выполняет полный расчет характеристик пива с валидацией входных данных.

    Входные параметры:
    - malt_pct (M): Пропорция солода (0-100)
    - water_pct (W): Пропорция воды (0-100)
    - hop_pct (H): Пропорция хмеля (0-100)
    - yeast_pct (Y): Пропорция дрожжей (0-100)
    - skill: Навык алхимика (1-100)
    - fatigue: Усталость алхимика (0-100)

    Возвращает BeerStatsDTO с округленными параметрами:
    - strength: float (округлено до 2 знаков)
    - bitterness: float (округлено до 2 знаков)
    - aroma: float (округлено до 2 знаков)
    - stability: int (округлено/приведено к int в диапазоне 0-100)
    """
    # Валидация диапазонов
    for name, val in [
        ("malt_pct", malt_pct),
        ("water_pct", water_pct),
        ("hop_pct", hop_pct),
        ("yeast_pct", yeast_pct),
    ]:
        if not (0 <= val <= 100):
            raise ValueError(f"Параметр {name} должен быть в диапазоне от 0 до 100")

    if not (1 <= skill <= 100):
        raise ValueError("Навык алхимика (skill) должен быть в диапазоне от 1 до 100")

    # Валидация суммы
    if malt_pct + water_pct + hop_pct + yeast_pct != 100:
        raise ValueError(
            "Сумма пропорций ингредиентов (M + W + H + Y) должна быть строго равна 100"
        )

    strength = calculate_strength(malt_pct, water_pct, hop_pct, yeast_pct)
    bitterness = calculate_bitterness(malt_pct, water_pct, hop_pct, yeast_pct)
    aroma = calculate_aroma(malt_pct, water_pct, hop_pct, yeast_pct, bitterness)
    stability = calculate_stability(yeast_pct, water_pct, skill, fatigue)

    return BeerStatsDTO(
        strength=round(strength, 2),
        bitterness=round(bitterness, 2),
        aroma=round(aroma, 2),
        stability=int(min(100, max(0, stability))),
    )
