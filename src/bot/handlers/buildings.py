from typing import cast
from decimal import Decimal
from aiogram import F, Router, html
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.dal import PlayerDAL, PlayerNotFoundError, InsufficientFundsError
from src.database.models import TavernTier
from src.bot.utils.formatters import get_tavern_name
from src.bot.utils.hud import send_or_edit_dashboard
from src.bot.keyboards.inline import add_global_navigation_footer

buildings_router = Router()

UPGRADE_COSTS = {
    TavernTier.garage: Decimal("500.00"),
    TavernTier.tavern: Decimal("2000.00"),
    TavernTier.brewery: Decimal("10000.00"),
    TavernTier.factory: Decimal("50000.00"),
}

NEXT_TIER = {
    TavernTier.garage: TavernTier.tavern,
    TavernTier.tavern: TavernTier.brewery,
    TavernTier.brewery: TavernTier.factory,
    TavernTier.factory: TavernTier.guild,
}


@buildings_router.callback_query(F.data == "screen:tavern")
async def show_tavern(callback: CallbackQuery, session: AsyncSession) -> None:
    """
    Экран "Моя Таверна" (бывший экран зданий).
    """
    if not callback.from_user or not callback.message or not isinstance(callback.message, Message):
        await callback.answer()
        return

    tg_id = callback.from_user.id
    player_dal = PlayerDAL(session)

    try:
        player = await player_dal.get_player(tg_id)
        current_tier = TavernTier(str(player.tavern_level.value)) if player.tavern_level else TavernTier.garage

        tavern_levels = {
            TavernTier.garage: "Гараж (уровень 1)",
            TavernTier.tavern: "Таверна (уровень 2)",
            TavernTier.brewery: "Пивоварня (уровень 3)",
            TavernTier.factory: "Завод (уровень 4)",
            TavernTier.guild: "Гильдия Пивоваров (уровень 5)",
        }
        rank_str = tavern_levels.get(current_tier, "Неизвестно")

        descriptions = {
            TavernTier.garage: "🏚️ <b>Гараж:</b> Скромная пивоварня на коленке. Отсюда начнется ваша пивная империя.",
            TavernTier.tavern: "🍺 <b>Таверна:</b> Полноценный пивной паб с постоянными гостями.",
            TavernTier.brewery: "🏭 <b>Пивоварня:</b> Профессиональное оборудование, расширенный сбыт.",
            TavernTier.factory: "🏬 <b>Завод:</b> Промышленное производство, автоматические варки и огромная прибыль.",
            TavernTier.guild: "🏰 <b>Гильдия Алхимиков:</b> Легендарное место. Здесь куется пивная история.",
        }

        t_name = get_tavern_name(cast(int, player.reputation))
        desc = descriptions.get(current_tier, "")

        text = (
            f"🍻 <b>Моя Таверна «{t_name}»</b>\n\n"
            f"{desc}\n\n"
            f"Текущий уровень: <code>{rank_str}</code>\n"
        )

        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="👥 Управление персоналом", callback_data="screen:staff")
        )

        if current_tier in NEXT_TIER:
            next_tier = NEXT_TIER[current_tier]
            cost = UPGRADE_COSTS[current_tier]
            text += (
                f"Следующий уровень: <code>{tavern_levels.get(next_tier, next_tier.value).capitalize()}</code>\n"
                f"💰 Стоимость улучшения: <b>{cost:.2f} gold</b>\n"
            )
            builder.row(
                InlineKeyboardButton(text="⬆️ Улучшить таверну", callback_data="tavern:upgrade")
            )
        else:
            text += "🌟 Достигнут максимальный уровень улучшения!\n"

        await send_or_edit_dashboard(
            bot=callback.bot,
            player=player,
            session=session,
            text=text,
            reply_markup=add_global_navigation_footer(builder.as_markup())
        )

    except PlayerNotFoundError:
        await callback.answer("Профиль не найден.", show_alert=True)

    await callback.answer()


@buildings_router.callback_query(F.data == "tavern:upgrade")
async def upgrade_tavern_callback(callback: CallbackQuery, session: AsyncSession) -> None:
    """
    Обработчик улучшения таверны.
    """
    if not callback.from_user or not callback.message or not isinstance(callback.message, Message):
        await callback.answer()
        return

    tg_id = callback.from_user.id
    player_dal = PlayerDAL(session)

    try:
        player = await player_dal.get_player(tg_id)
        current_tier = TavernTier(str(player.tavern_level.value)) if player.tavern_level else TavernTier.garage

        if current_tier not in NEXT_TIER:
            await callback.answer("Здание уже максимального уровня!", show_alert=True)
            return

        next_tier = NEXT_TIER[current_tier]

        await player_dal.upgrade_tavern_level(cast(int, player.player_id))
        
        # Запишем событие улучшения в лог событий игрока!
        summary = f"Улучшил таверну до ранга '{next_tier.value.capitalize()}'"
        await player_dal.log_player_event(
            player_id=cast(int, player.player_id),
            event_type="tavern_upgrade",
            summary=summary,
            metadata={"old_tier": current_tier.value, "new_tier": next_tier.value}
        )

        await callback.answer(
            f"🎉 Ура! Таверна успешно улучшена до ранга {next_tier.value.capitalize()}!",
            show_alert=True,
        )
        
        # Перерисовываем экран таверны
        await show_tavern(callback, session)

    except InsufficientFundsError:
        try:
            player = await player_dal.get_player(tg_id)
            current_tier = TavernTier(str(player.tavern_level.value)) if player.tavern_level else TavernTier.garage
            cost = UPGRADE_COSTS[current_tier]
            await callback.answer(
                f"❌ Недостаточно золота! Нужно {cost:.2f} gold.",
                show_alert=True,
            )
        except Exception:
            await callback.answer("❌ Недостаточно золота для улучшения!", show_alert=True)
    except Exception as e:
        await callback.answer(f"❌ Ошибка улучшения: {str(e)}", show_alert=True)
