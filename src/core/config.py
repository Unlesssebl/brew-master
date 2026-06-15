from pydantic import BaseModel, Field

class GameBalance(BaseModel):
    """
    Класс констант игрового баланса для формул и расчетов.
    """
    market_saturation_threshold: int = Field(default=500, description="Порог насыщения рынка в бочках")
    market_saturation_lambda: float = Field(default=0.005, description="Коэффициент эластичности рынка (скорость падения цены)")
    prestige_crystal_divisor: float = Field(default=1000000.0, description="Делитель для расчета кристаллов престижа")
    base_ingredient_costs: dict[str, float] = Field(
        default_factory=lambda: {"malt": 1.0, "water": 0.1, "hops": 2.0, "yeast": 1.5},
        description="Себестоимость базовых ингредиентов"
    )
    offline_max_hours: int = Field(default=24, description="Максимальное время начисления оффлайн-дохода")
    offline_efficiency_multiplier: float = Field(default=0.5, description="Множитель эффективности оффлайн-дохода после 4 часов")
    expedition_heavy_injury_cost: float = Field(default=200.0, description="Стоимость лечения тяжелой травмы")
