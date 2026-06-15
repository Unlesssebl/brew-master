from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.crafting import calculate_beer_stats
from src.database.models import Recipe


class CraftingDAL:
    """
    Data Access Layer (DAL) для работы с рецептами и крафтом.
    """

    def __init__(self, session: AsyncSession = None):
        self.session = session

    async def create_recipe(self=None, *args, **kwargs) -> Recipe:
        """
        Рассчитать характеристики рецепта пива и сохранить его в базе данных.
        
        Использует логику из src.core.crafting.calculate_beer_stats для расчета параметров.
        """
        if self is None or not isinstance(self, CraftingDAL):
            session = self if self is not None else kwargs.get("session")
            args_to_use = args
        else:
            session = self.session
            args_to_use = args

        def get_val(idx: int, name: str, default=None):
            if len(args_to_use) > idx:
                return args_to_use[idx]
            return kwargs.get(name, default)

        player_id = get_val(0, "player_id")
        m = get_val(1, "m")
        w = get_val(2, "w")
        h = get_val(3, "h")
        y = get_val(4, "y")
        skill = get_val(5, "skill")
        fatigue = get_val(6, "fatigue")
        title = get_val(7, "title", "Экспериментальная варка")

        stats = calculate_beer_stats(
            malt_pct=m,
            water_pct=w,
            hop_pct=h,
            yeast_pct=y,
            skill=skill,
            fatigue=fatigue,
        )

        recipe = Recipe(
            creator_id=player_id,
            title=title,
            malt_pct=m,
            water_pct=w,
            hop_pct=h,
            yeast_pct=y,
            strength=Decimal(str(stats.strength)),
            bitterness=Decimal(str(stats.bitterness)),
            aroma=Decimal(str(stats.aroma)),
            stability=stats.stability,
        )

        session.add(recipe)
        await session.flush()
        return recipe
