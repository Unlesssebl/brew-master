def calculate_staff_event_chance(loyalty: int, fatigue: int) -> float:
    """
    Рассчитывает вероятность негативного события персонала (саботаж, требование повышения).

    Входные параметры:
    - loyalty: лояльность сотрудника (0-100)
    - fatigue: усталость сотрудника (>= 0)

    Формула:
    P = min(90.0, ((100 - loyalty) * 0.5 + (fatigue * 0.3))) / 100

    Возвращает вероятность от 0.0 до 0.9.
    """
    # Валидация диапазонов
    if not (0 <= loyalty <= 100):
        raise ValueError("Параметр loyalty должен быть в диапазоне от 0 до 100")

    if fatigue < 0:
        raise ValueError("Параметр fatigue не может быть меньше 0")

    p_percent = min(90.0, ((100 - loyalty) * 0.5 + (fatigue * 0.3)))
    p = p_percent / 100.0
    return float(round(max(0.0, p), 4))
