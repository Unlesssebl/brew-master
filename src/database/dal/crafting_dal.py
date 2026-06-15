from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.crafting import calculate_beer_stats
from src.database.models import Recipe


class CraftingDAL:
    """
    Data Access Layer (DAL) для работы с рецептами и крафтом.
    """

    @staticmethod
    async def create_recipe(
        session: AsyncSession,
        player_id: int,
        m: int,
        w: int,
        h: int,
        y: int,
        skill: int,
        fatigue: int,
        title: str,
    ) -> Recipe:
        """
        Рассчитать характеристики рецепта пива и сохранить его в базе данных.
        
        Использует логику из src.core.crafting.calculate_beer_stats для расчета параметров.
        """
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
