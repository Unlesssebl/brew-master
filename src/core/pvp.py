"""
Модуль для расчета вероятностных PVP-событий (диверсии, промышленный шпионаж).
Подробности в docs/04_math_and_economy.md.
"""


def calculate_reverse_engineering_chance(skill_alchemist: int) -> float:
    """
    Вычисляет шанс успешной обратной разработки чертежа рецепта.
    Формула: Chance = min(95, max(5, 60 + Skill / 2))
    """
    pass


def calculate_sabotage_chance(
    influence_atk: int,
    guard_lvl_def: int,
    base_chance: float = 50.0,
) -> float:
    """
    Вычисляет шанс успешной диверсии (подкуп, слухи) с учетом защиты цели.
    Формула: Chance = min(90, max(10, Base_chance + Influence_atk - Guard_lvl * 10))
    """
    pass
