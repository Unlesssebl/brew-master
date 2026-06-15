from decimal import Decimal
from aiogram import F, Router, html
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.dal import PlayerDAL, PlayerNotFoundError, InsufficientFundsError
from src.database.models import TavernTier
from src.bot.utils.keyboards import get_building_keyboard

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


@buildings_router.callback_query(F.data == "screen:buildings")
async def show_buildings(callback: CallbackQuery, session: AsyncSession) -> None:
    """
    Экран со списком всех зданий игрока.
    """
    if not callback.from_user or not callback.message or not isinstance(callback.message, Message):
        await callback.answer()
        return

    tg_id = callback.from_user.id
    player_dal = PlayerDAL(session)

    try:
        player = await player_dal.get_player(tg_id)
        level_str = str(player.tavern_level.value) if player.tavern_level else "garage"

        text = (
            f"🏢 <b>Здания вашей Пивной Империи</b>\n\n"
            f"Развивайте здания, чтобы открывать новые рецепты, нанимать редких специалистов "
            f"и повышать прибыль!\n\n"
            f"1. 🍺 <b>Пивоварня / Таверна</b>\n"
            f"   Уровень: <code>{level_str.capitalize()}</code>\n\n"
            f"Выберите здание из списка для управления:"
        )

        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(
                text="🍺 Пивоварня / Таверна", callback_data="building:brewery"
            )
        )
        builder.row(
            InlineKeyboardButton(
                text="🔙 Назад в меню", callback_data="screen:menu"
            )
        )

        await callback.message.edit_text(
            text, parse_mode="HTML", reply_markup=builder.as_markup()
        )
    except PlayerNotFoundError:
        await callback.answer("Профиль не найден.", show_alert=True)

    await callback.answer()


@buildings_router.callback_query(F.data == "building:brewery")
async def show_brewery_details(callback: CallbackQuery, session: AsyncSession) -> None:
    """
    Детальный экран Пивоварни.
    """
    if not callback.from_user or not callback.message or not isinstance(callback.message, Message):
        await callback.answer()
        return

    tg_id = callback.from_user.id
    player_dal = PlayerDAL(session)

    try:
        player = await player_dal.get_player(tg_id)
        current_tier = TavernTier(str(player.tavern_level.value)) if player.tavern_level else TavernTier.garage

        descriptions = {
            TavernTier.garage: "🏚️ <b>Гараж:</b> Скромная пивоварня на коленке. Отсюда начнется ваша пивная империя.",
            TavernTier.tavern: "🍺 <b>Таверна:</b> Полноценный пивной паб с постоянными гостями.",
            TavernTier.brewery: "🏭 <b>Пивоварня:</b> Профессиональное оборудование, расширенный сбыт.",
            TavernTier.factory: "🏬 <b>Завод:</b> Промышленное производство, автоматические варки и огромная прибыль.",
            TavernTier.guild: "🏰 <b>Гильдия Алхимиков:</b> Легендарное место. Здесь куется пивная история.",
        }

        desc = descriptions.get(current_tier, "")

        text = (
            f"🍺 <b>Управление Пивоварней</b>\n\n"
            f"{desc}\n\n"
            f"Текущий уровень: <code>{current_tier.value.upper()}</code>\n"
        )

        if current_tier in NEXT_TIER:
            next_tier = NEXT_TIER[current_tier]
            cost = UPGRADE_COSTS[current_tier]
            text += (
                f"Следующий уровень: <code>{next_tier.value.upper()}</code>\n"
                f"💰 Стоимость улучшения: <b>{cost:.2f} gold</b>\n"
            )
        else:
            text += "🌟 Достигнут максимальный уровень Пивоварни!\n"

        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=get_building_keyboard("brewery", current_tier.value),
        )
    except PlayerNotFoundError:
        await callback.answer("Профиль не найден.", show_alert=True)

    await callback.answer()


@buildings_router.callback_query(F.data.startswith("building:upgrade:"))
async def upgrade_building_callback(callback: CallbackQuery, session: AsyncSession) -> None:
    """
    Обработчик улучшения здания.
    """
    if not callback.from_user or not callback.message or not isinstance(callback.message, Message) or not callback.data:
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

        await player_dal.upgrade_tavern_level(int(player.player_id))

        await callback.answer(
            f"🎉 Ура! Здание успешно улучшено до уровня {next_tier.value.capitalize()}!",
            show_alert=True,
        )
        # Перерисовываем детальный экран
        await show_brewery_details(callback, session)

    except InsufficientFundsError:
        # Снова получаем игрока, чтобы достать current_tier на случай, если выше упало
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
