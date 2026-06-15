import math

from src.config import settings


def calculate_prestige_crystals(total_earned_gold: float) -> int:
    """
    Рассчитывает количество кристаллов престижа, получаемых при перерождении.

    Формула: Crystals = floor(total_earned_gold / settings.GameBalance.prestige_crystal_divisor)

    Требования:
    - total_earned_gold >= 1000000, иначе выбрасывает ValueError.
    """
    if total_earned_gold < 1000000.0:
        raise ValueError("Недостаточно общего заработка для перерождения")

    divisor = settings.GameBalance.prestige_crystal_divisor
    return math.floor(total_earned_gold / divisor)
