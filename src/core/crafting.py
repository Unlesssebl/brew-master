"""
Модуль для расчета физических и химических свойств пива на основе пропорций ингредиентов.
Формулы и ограничения описаны в docs/04_math_and_economy.md.
"""


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
    pass


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
    pass


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
    pass


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
    pass
