from datetime import datetime
from src.config import settings

def calculate_offline_production(
    last_online: datetime,
    current_time: datetime,
    base_hourly_rate: float
) -> float:
    """
    Рассчитывает накопленный оффлайн-доход.
    
    Входные параметры:
    - last_online: время последнего выхода из игры (datetime)
    - current_time: текущее время расчета (datetime)
    - base_hourly_rate: базовая почасовая ставка производства
    
    Логика:
    1. Рассчитать delta_hours = (current_time - last_online).total_seconds() / 3600.
    2. Если delta_hours <= 0, вернуть 0.0.
    3. Ограничить delta_hours максимумом settings.GameBalance.offline_max_hours.
    4. Если delta_hours > 4, применить штраф: effective_rate = base_hourly_rate * settings.GameBalance.offline_efficiency_multiplier.
       Иначе effective_rate = base_hourly_rate.
    5. Вернуть effective_rate * delta_hours.
    """
    # Расчет разницы в часах
    delta_seconds = (current_time - last_online).total_seconds()
    delta_hours = delta_seconds / 3600.0
    
    if delta_hours <= 0.0:
        return 0.0
        
    # Ограничение максимумом оффлайн-дохода
    max_hours = settings.GameBalance.offline_max_hours
    if delta_hours > max_hours:
        delta_hours = float(max_hours)
        
    # Применение штрафа эффективности при оффлайне > 4 часов
    if delta_hours > 4.0:
        effective_rate = base_hourly_rate * settings.GameBalance.offline_efficiency_multiplier
    else:
        effective_rate = base_hourly_rate
        
    production = effective_rate * delta_hours
    return float(round(production, 4))
