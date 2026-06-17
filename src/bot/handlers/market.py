import logging
from decimal import Decimal
from datetime import datetime
from typing import cast
from aiogram import F, Router, html
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.dal import PlayerDAL, PlayerNotFoundError, EconomyDAL, InsufficientFundsError
from src.database.models import Batch, Recipe, IngredientPrice, PlayerEventLog
from src.bot.utils.hud import send_or_edit_dashboard
from src.bot.utils.formatters import get_tavern_name
from src.bot.keyboards.inline import add_global_navigation_footer

logger = logging.getLogger(__name__)
market_router = Router()


@market_router.callback_query(F.data == "screen:market")
async def show_market(callback: CallbackQuery, session: AsyncSession) -> None:
    """
    Главный экран Торговой площади.
    """
    if not callback.from_user or not callback.message or not isinstance(callback.message, Message):
        await callback.answer()
        return

    tg_id = callback.from_user.id
    player_dal = PlayerDAL(session)

    try:
        player = await player_dal.get_player(tg_id)
        t_name = get_tavern_name(cast(int, player.reputation))

        text = (
            f"⚖️ <b>Торговая площадь города</b>\n\n"
            f"Здесь шумно и людно. Купцы со всего света предлагают редкие ингредиенты, "
            f"а представители фракций готовы выкупить ваши лучшие бочки эля.\n\n"
            f"Что вы хотите сделать?"
        )

        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="📦 Закупить сырьё", callback_data="market:buy_list")
        )
        builder.row(
            InlineKeyboardButton(text="💰 Сбыть партию готового пива", callback_data="market:sell_list")
        )

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


@market_router.callback_query(F.data == "market:buy_list")
async def show_buy_list(callback: CallbackQuery, session: AsyncSession) -> None:
    """
    Экран закупки сырья с плавающими ценами.
    """
    if not callback.from_user or not callback.message or not isinstance(callback.message, Message):
        await callback.answer()
        return

    tg_id = callback.from_user.id
    player_dal = PlayerDAL(session)
    economy_dal = EconomyDAL()

    try:
        player = await player_dal.get_player(tg_id)
        prices = await economy_dal.get_ingredient_prices(session)

        # Создаем словарь для отображения названий и эмодзи
        names_ru = {
            "malt": ("🌾 Солод", "кг"),
            "water": ("💧 Вода", "л"),
            "hops": ("🌿 Хмель", "кг"),
            "yeast": ("🍞 Дрожжи", "кг")
        }

        text = (
            f"📦 <b>Закупка сырья (Плавающие цены)</b>\n\n"
            f"Цены меняются каждые 4 часа в зависимости от спроса на рынке.\n\n"
        )

        builder = InlineKeyboardBuilder()

        for p in prices:
            ing_key = cast(str, p.ingredient)
            name, unit = names_ru.get(ing_key, (ing_key, ""))
            trend_emoji = "➡️"
            if p.trend > 0:
                trend_emoji = "🔺"
            elif p.trend < 0:
                trend_emoji = "🔻"

            text += f"{name}: <b>{p.price:.2f} gold</b> за 1 {unit} {trend_emoji}\n"
            
            # Кнопка для покупки пачки из 50 единиц
            cost_50 = cast(Decimal, p.price) * Decimal("50")
            builder.row(
                InlineKeyboardButton(
                    text=f"Купить 50 {unit} {name} ({cost_50:.1f}g)",
                    callback_data=f"market:buy:{ing_key}:50"
                )
            )

        await send_or_edit_dashboard(
            bot=callback.bot,
            player=player,
            session=session,
            text=text,
            reply_markup=add_global_navigation_footer(builder.as_markup(), back_callback="screen:market")
        )
    except PlayerNotFoundError:
        await callback.answer("Профиль не найден.", show_alert=True)
    await callback.answer()


@market_router.callback_query(F.data.startswith("market:buy:"))
async def process_buy_ingredient(callback: CallbackQuery, session: AsyncSession) -> None:
    """
    Обработчик покупки ингредиента.
    """
    if not callback.from_user or not callback.message or not isinstance(callback.message, Message) or not callback.data:
        await callback.answer()
        return

    parts = callback.data.split(":")
    ingredient = parts[2]
    amount = int(parts[3])

    tg_id = callback.from_user.id
    player_dal = PlayerDAL(session)
    economy_dal = EconomyDAL()

    try:
        player = await player_dal.get_player(tg_id)
        
        # Получаем цену ингредиента
        stmt = select(IngredientPrice).where(IngredientPrice.ingredient == ingredient)
        res_price = await session.execute(stmt)
        ing_price = res_price.scalar_one_or_none()

        if not ing_price:
            await callback.answer("Ингредиент не найден на рынке.", show_alert=True)
            return

        price_per_unit = cast(Decimal, ing_price.price)
        cost = Decimal(str(amount)) * price_per_unit

        try:
            await economy_dal.buy_ingredient(session, cast(int, player.player_id), ingredient, amount, price_per_unit)
        except InsufficientFundsError:
            await callback.answer(f"❌ Недостаточно золота! Нужно {cost:.1f} gold, у вас {player.gold:.1f}", show_alert=True)
            return

        # Логируем событие покупки в лог событий игрока
        names_ru = {"malt": "солод", "water": "вода", "hops": "хмель", "yeast": "дрожжи"}
        summary = f"Купил 50 единиц ресурса '{names_ru.get(ingredient, ingredient)}' за {cost:.1f} gold"
        await player_dal.log_player_event(
            player_id=cast(int, player.player_id),
            event_type="buy_resources",
            summary=summary,
            metadata={"ingredient": ingredient, "amount": amount, "cost": float(cost)}
        )

        await callback.answer(f"📦 Куплено: {amount} ед. ({cost:.1f} gold)!", show_alert=True)
        
        # Обновляем HUD и перерисовываем закупку
        # Так как это коллбек покупки, мы обновляем дашборд. Нам не нужен update_hud отдельно.
        await show_buy_list(callback, session)

    except PlayerNotFoundError:
        await callback.answer("Профиль не найден.", show_alert=True)
    except Exception as e:
        await callback.answer(f"Ошибка при покупке: {str(e)}", show_alert=True)


@market_router.callback_query(F.data == "market:sell_list")
async def show_sell_list(callback: CallbackQuery, session: AsyncSession) -> None:
    """
    Экран выбора готовой партии для продажи.
    """
    if not callback.from_user or not callback.message or not isinstance(callback.message, Message):
        await callback.answer()
        return

    tg_id = callback.from_user.id
    player_dal = PlayerDAL(session)

    try:
        player = await player_dal.get_player(tg_id)
        
        # Получаем бочки на складе
        stmt = select(Batch).where(
            Batch.player_id == cast(int, player.player_id),
            Batch.quantity_barrels > 0,
            Batch.is_completed.is_(True),
        )
        res = await session.execute(stmt)
        batches = res.scalars().all()

        text = "💰 <b>Сбыт готового пива фракциям</b>\n\n"
        builder = InlineKeyboardBuilder()

        if batches:
            text += "Выберите партию для продажи:\n\n"
            for b in batches:
                # Получаем название рецепта
                stmt_recipe = select(Recipe).where(Recipe.recipe_id == cast(int, b.recipe_id))
                recipe_res = await session.execute(stmt_recipe)
                recipe = recipe_res.scalar_one_or_none()
                recipe_title = str(recipe.title) if recipe else "Неизвестное пиво"

                # Проверим, есть ли патент для отображения названия
                from src.database.models import Patent
                stmt_pat = select(Patent).where(
                    Patent.recipe_id == cast(int, b.recipe_id),
                    Patent.player_id == cast(int, player.player_id),
                    Patent.is_active.is_(True)
                )
                pat_res = await session.execute(stmt_pat)
                patent = pat_res.scalar_one_or_none()
                
                display_title = recipe_title
                if patent and patent.lore_name:
                    display_title = patent.lore_name

                text += f"• <b>«{html.quote(cast(str, display_title))}»</b> — <code>{b.quantity_barrels} бочек</code> (качество {b.quality_modifier:.2f}x)\n"
                builder.row(
                    InlineKeyboardButton(
                        text=f"Продать «{display_title}»",
                        callback_data=f"market:sell_factions:{b.batch_id}"
                    )
                )
        else:
            text += "В вашем погребе пока нет готового к продаже пива. Сварите партию в варочном зале!\n"

        await send_or_edit_dashboard(
            bot=callback.bot,
            player=player,
            session=session,
            text=text,
            reply_markup=add_global_navigation_footer(builder.as_markup(), back_callback="screen:market")
        )
    except PlayerNotFoundError:
        await callback.answer("Профиль не найден.", show_alert=True)
    await callback.answer()


@market_router.callback_query(F.data.startswith("market:sell_factions:"))
async def show_faction_choice(callback: CallbackQuery, session: AsyncSession) -> None:
    """
    Экран выбора фракции для продажи партии пива с расчетом цены.
    """
    if not callback.from_user or not callback.message or not isinstance(callback.message, Message) or not callback.data:
        await callback.answer()
        return

    batch_id = int(callback.data.split(":")[2])
    tg_id = callback.from_user.id
    player_dal = PlayerDAL(session)

    try:
        player = await player_dal.get_player(tg_id)
        
        # Получаем батч
        stmt = select(Batch).where(Batch.batch_id == batch_id)
        res = await session.execute(stmt)
        batch = res.scalar_one_or_none()

        if not batch or batch.quantity_barrels <= 0:
            await callback.answer("Партия не найдена или уже продана.", show_alert=True)
            return

        # Проверяем наличие дебаффа "rumors"
        from datetime import UTC
        stmt_debuff = select(PlayerEventLog).where(
            PlayerEventLog.player_id == cast(int, player.player_id),
            PlayerEventLog.event_type == "pvp_debuff_received"
        ).order_by(PlayerEventLog.created_at.desc()).limit(1)
        res_debuff = await session.execute(stmt_debuff)
        last_debuff = res_debuff.scalar_one_or_none()
        
        debuff_multiplier = Decimal("1.0")
        debuff_alert = ""
        if last_debuff:
            meta = last_debuff.metadata_json or {}
            if meta.get("debuff") == "rumors":
                expires_str = meta.get("expires_at")
                if expires_str:
                    expires = datetime.fromisoformat(expires_str)
                    if expires.tzinfo is None:
                        expires = expires.replace(tzinfo=UTC)
                    if expires > datetime.now(UTC):
                        debuff_multiplier = Decimal("0.5")
                        debuff_alert = "\n⚠️ <b>Внимание:</b> О вашей таверне ходят Грязные слухи! Выручка снижена на 50%.\n"

        # Рассчитываем цены для разных фракций
        # Базовая цена за бочку: 10 gold (итого 100 gold за партию из 10 бочек)
        base_revenue = Decimal(str(batch.quantity_barrels)) * Decimal("10.00")
        
        # 1. Дворфы (legal): коэфф = 1.0 + 0.02 * influence + 0.01 * reputation
        dwarfs_coeff = Decimal("1.0") + Decimal(str(player.influence)) * Decimal("0.02") + Decimal(str(player.reputation)) * Decimal("0.01")
        dwarfs_coeff = max(Decimal("0.5"), dwarfs_coeff)
        dwarfs_revenue = base_revenue * dwarfs_coeff * batch.quality_modifier * debuff_multiplier

        # 2. Эльфы (grey): коэфф = 1.5 + 0.03 * influence - 0.02 * reputation
        elves_coeff = Decimal("1.5") + Decimal(str(player.influence)) * Decimal("0.03") - Decimal(str(player.reputation)) * Decimal("0.02")
        elves_coeff = max(Decimal("0.5"), elves_coeff)
        elves_revenue = base_revenue * elves_coeff * batch.quality_modifier * debuff_multiplier

        # 3. Гоблины (black): коэфф = 0.5 (покупают всё, репутация падает)
        goblins_revenue = base_revenue * Decimal("0.5") * batch.quality_modifier * debuff_multiplier

        text = (
            f"💰 <b>Выбор покупателя для вашей партии пива</b>\n\n"
            f"Объем партии: <code>{batch.quantity_barrels} бочек</code>\n"
            f"Качество: <code>{batch.quality_modifier:.2f}x</code>\n"
            f"{debuff_alert}\n"
            f"Выберите фракцию для заключения контракта:\n\n"
            f"⛏️ <b>Дворфы (Надежный сбыт):</b>\n"
            f"• Цена: <b>{dwarfs_revenue:.1f} gold</b>\n"
            f"• Репутация: <b>+1 ⭐</b>\n\n"
            f"🧝 <b>Эльфы (Контрабанда):</b>\n"
            f"• Цена: <b>{elves_revenue:.1f} gold</b>\n"
            f"• Репутация: Риск падения на <b>-2 ⭐</b> (шанс 30%)\n\n"
            f"👺 <b>Гоблины (Скупщики):</b>\n"
            f"• Цена: <b>{goblins_revenue:.1f} gold</b>\n"
            f"• Репутация: Падает на <b>-3 ⭐</b>\n"
        )

        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(
                text=f"⛏️ Дворфы ({dwarfs_revenue:.1f}g)",
                callback_data=f"market:sell_confirm:{batch.batch_id}:dwarfs:{dwarfs_revenue:.2f}"
            )
        )
        builder.row(
            InlineKeyboardButton(
                text=f"🧝 Эльфы ({elves_revenue:.1f}g)",
                callback_data=f"market:sell_confirm:{batch.batch_id}:elves:{elves_revenue:.2f}"
            )
        )
        builder.row(
            InlineKeyboardButton(
                text=f"👺 Гоблины ({goblins_revenue:.1f}g)",
                callback_data=f"market:sell_confirm:{batch.batch_id}:goblins:{goblins_revenue:.2f}"
            )
        )
        await send_or_edit_dashboard(
            bot=callback.bot,
            player=player,
            session=session,
            text=text,
            reply_markup=add_global_navigation_footer(builder.as_markup(), back_callback="market:sell_list")
        )
    except PlayerNotFoundError:
        await callback.answer("Профиль не найден.", show_alert=True)
    await callback.answer()


@market_router.callback_query(F.data.startswith("market:sell_confirm:"))
async def process_sell_confirm(callback: CallbackQuery, session: AsyncSession) -> None:
    """
    Обрабатывает подтверждение продажи партии выбранной фракции.
    """
    if not callback.from_user or not callback.message or not isinstance(callback.message, Message) or not callback.data:
        await callback.answer()
        return

    parts = callback.data.split(":")
    batch_id = int(parts[2])
    faction = parts[3]
    revenue = Decimal(parts[4])

    tg_id = callback.from_user.id
    player_dal = PlayerDAL(session)
    economy_dal = EconomyDAL()

    try:
        player = await player_dal.get_player(tg_id)

        # Загружаем батч для лога
        stmt = select(Batch).where(Batch.batch_id == batch_id)
        res = await session.execute(stmt)
        batch = res.scalar_one_or_none()

        if not batch:
            await callback.answer("Партия не найдена.", show_alert=True)
            return

        stmt_recipe = select(Recipe).where(Recipe.recipe_id == batch.recipe_id)
        res_recipe = await session.execute(stmt_recipe)
        recipe = res_recipe.scalar_one_or_none()
        recipe_title = recipe.title if recipe else "Неизвестный рецепт"

        # Применяем фракционные эффекты на репутацию и влияние
        import random
        reputation_change = 0
        influence_change = 0
        market_type = "legal"
        faction_name_ru = "Дворфы"

        if faction == "dwarfs":
            reputation_change = 1
            influence_change = 0
            market_type = "legal"
            faction_name_ru = "Дворфы"
        elif faction == "elves":
            # 30% шанс потерять 2 репутации
            if random.random() < 0.3:
                reputation_change = -2
            else:
                reputation_change = 0
            influence_change = 1
            market_type = "grey"
            faction_name_ru = "Эльфы"
        elif faction == "goblins":
            reputation_change = -3
            influence_change = 0
            market_type = "black"
            faction_name_ru = "Гоблины"

        # Продаем партию через DAL
        await economy_dal.sell_batch(session, cast(int, player.player_id), batch_id, faction, market_type, revenue)

        if player.tutorial_step == 2:
            await player_dal.update_tutorial_step(tg_id, 3)

        # Обновляем статы игрока (репутация, влияние)
        await player_dal.update_player_stats(
            player_id=cast(int, player.player_id),
            gold_change=Decimal("0.00"),  # Золото уже начислено в sell_batch
            reputation_change=reputation_change,
            influence_change=influence_change
        )

        # Пишем в лог событий игрока
        rep_text = f" ({reputation_change:+.0f} реп.)" if reputation_change != 0 else ""
        summary = f"Продал партию пива «{recipe_title}» фракции {faction_name_ru} за {revenue:.1f} gold{rep_text}"
        await player_dal.log_player_event(
            player_id=cast(int, player.player_id),
            event_type="sell_batch",
            summary=summary,
            metadata={
                "batch_id": batch_id,
                "faction": faction,
                "revenue": float(revenue),
                "reputation_change": reputation_change,
                "influence_change": influence_change
            }
        )

        await callback.answer(f"💰 Партия продана за {revenue:.1f} gold!", show_alert=True)
        
        # Обновляем HUD и возвращаемся в список
        await show_sell_list(callback, session)

    except PlayerNotFoundError:
        await callback.answer("Профиль не найден.", show_alert=True)
    except Exception as e:
        await callback.answer(f"Ошибка продажи: {str(e)}", show_alert=True)
