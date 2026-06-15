import math
import random


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
    return min(20.0, max(0.0, str_val))


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
    return min(20.0, max(0.0, bit_val))


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
    return min(20.0, max(0.0, aro_val))


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

    return min(100, max(0, stab))

