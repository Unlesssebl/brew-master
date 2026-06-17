import logging
import random
from datetime import datetime, UTC, timedelta
from decimal import Decimal
from typing import cast
from aiogram import F, Router, html
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.dal import PlayerDAL, PlayerNotFoundError, EconomyDAL, InsufficientFundsError
from src.database.models import Batch, Recipe, Player, PlayerEventLog, TavernTier
from src.bot.utils.hud import send_or_edit_dashboard
from src.bot.utils.formatters import get_tavern_name
from src.bot.keyboards.inline import add_global_navigation_footer

logger = logging.getLogger(__name__)
slums_router = Router()


@slums_router.callback_query(F.data == "screen:slums")
async def show_slums(callback: CallbackQuery, session: AsyncSession) -> None:
    """
    Экран "Тёмный переулок".
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
            f"🌑 <b>Тёмный переулок Трущоб</b>\n\n"
            f"Здесь, в тени старых стен таверны «{t_name}», проворачиваются самые темные дела города. "
            f"Гоблины скупают любой неликвид за бесценок, а информаторы готовы продать секреты ваших конкурентов.\n\n"
            f"Что вас интересует, мастер?"
        )

        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="🍶 Гоблинский базар (Сброс брака)", callback_data="slums:black_market")
        )
        builder.row(
            InlineKeyboardButton(text="🗡️ Сеть осведомителей (PvP)", callback_data="slums:pvp_list")
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


@slums_router.callback_query(F.data == "slums:black_market")
async def show_black_market(callback: CallbackQuery, session: AsyncSession) -> None:
    """
    Экран Гоблинского базара (сброс брака: Stability < 30 или quality_modifier < 0.5).
    """
    if not callback.from_user or not callback.message or not isinstance(callback.message, Message):
        await callback.answer()
        return

    tg_id = callback.from_user.id
    player_dal = PlayerDAL(session)

    try:
        player = await player_dal.get_player(tg_id)
        
        # Получаем все завершенные бочки игрока
        stmt = select(Batch).where(
            Batch.player_id == cast(int, player.player_id),
            Batch.quantity_barrels > 0,
            Batch.is_completed.is_(True)
        )
        res = await session.execute(stmt)
        batches = res.scalars().all()

        text = (
            f"🍶 <b>Гоблинский базар (Черный рынок)</b>\n\n"
            f"Гоблины с удовольствием скупят ваш пивной брак (Стабильность &lt; 30% или Качество &lt; 0.5x).\n"
            f"Покупают по фиксированной цене: <b>0.2x</b> от базы (20 gold за партию из 10 бочек).\n"
            f"⚠️ Каждая сделка с гоблинами снижает вашу репутацию на <b>-1 ⭐</b>.\n\n"
        )

        builder = InlineKeyboardBuilder()
        has_junk = False

        for b in batches:
            # Загрузим рецепт, чтобы проверить стабильность
            stmt_r = select(Recipe).where(Recipe.recipe_id == b.recipe_id)
            res_r = await session.execute(stmt_r)
            rec = res_r.scalar_one_or_none()
            
            stability = rec.stability if rec else 100
            
            # Критерий брака: стабильность < 30 или модификатор качества < 0.50
            if stability < 30 or b.quality_modifier < Decimal("0.50"):
                has_junk = True
                title = rec.title if rec else "Неизвестное пиво"
                text += f"• <b>«{title}»</b> — {b.quantity_barrels} бочек (Стаб: {stability}%, Кач: {b.quality_modifier:.2f}x)\n"
                builder.row(
                    InlineKeyboardButton(
                        text=f"Сдать «{title}» гоблинам (20g)",
                        callback_data=f"slums:black_sell:{b.batch_id}"
                    )
                )

        if not has_junk:
            text += "<i>У вас нет бракованного пива в погребе. Гоблины не заинтересованы в качественном товаре!</i>\n"

        await send_or_edit_dashboard(
            bot=callback.bot,
            player=player,
            session=session,
            text=text,
            reply_markup=add_global_navigation_footer(builder.as_markup(), back_callback="screen:slums")
        )
    except PlayerNotFoundError:
        await callback.answer("Профиль не найден.", show_alert=True)
    await callback.answer()


@slums_router.callback_query(F.data.startswith("slums:black_sell:"))
async def process_black_sell(callback: CallbackQuery, session: AsyncSession) -> None:
    """
    Продажа брака гоблинам.
    """
    if not callback.from_user or not callback.message or not isinstance(callback.message, Message) or not callback.data:
        await callback.answer()
        return

    batch_id = int(callback.data.split(":")[2])
    tg_id = callback.from_user.id
    player_dal = PlayerDAL(session)
    economy_dal = EconomyDAL()

    try:
        player = await player_dal.get_player(tg_id)
        
        # Получаем батч
        stmt = select(Batch).where(Batch.batch_id == batch_id)
        res = await session.execute(stmt)
        batch = res.scalar_one_or_none()

        if not batch or batch.quantity_barrels <= 0:
            await callback.answer("Партия уже продана.", show_alert=True)
            return

        stmt_rec = select(Recipe).where(Recipe.recipe_id == batch.recipe_id)
        res_rec = await session.execute(stmt_rec)
        recipe = res_rec.scalar_one_or_none()
        recipe_title = recipe.title if recipe else "Брак"

        # Фиксированная цена: 20 gold за партию
        revenue = Decimal("20.00")
        
        # Продаем партию
        await economy_dal.sell_batch(session, cast(int, player.player_id), batch_id, "goblins", "black", revenue)

        # Снижаем репутацию на -1
        await player_dal.update_player_stats(
            player_id=cast(int, player.player_id),
            gold_change=Decimal("0.00"),
            reputation_change=-1,
            influence_change=0
        )

        # Пишем в лог событий игрока
        summary = f"Сбросил бракованную партию «{recipe_title}» гоблинам за 20 gold (-1 реп.)"
        await player_dal.log_player_event(
            player_id=cast(int, player.player_id),
            event_type="black_market_sell",
            summary=summary,
            metadata={"batch_id": batch_id, "revenue": 20.0}
        )

        await callback.answer("🍶 Гоблины забрали бочки, довольно ухмыляясь (+20 gold, -1 реп.)!", show_alert=True)
        
        # Обновляем HUD и перерисовываем базар
        # update_hud не требуется отдельно, так как его вызывает send_or_edit_dashboard
        await show_black_market(callback, session)

    except PlayerNotFoundError:
        await callback.answer("Профиль не найден.", show_alert=True)
    except Exception as e:
        await callback.answer(f"Ошибка продажи: {str(e)}", show_alert=True)


@slums_router.callback_query(F.data == "slums:pvp_list")
async def show_pvp_list(callback: CallbackQuery, session: AsyncSession) -> None:
    """
    Экран сети осведомителей (PvP-цели).
    """
    if not callback.from_user or not callback.message or not isinstance(callback.message, Message):
        await callback.answer()
        return

    tg_id = callback.from_user.id
    player_dal = PlayerDAL(session)

    try:
        player = await player_dal.get_player(tg_id)
        
        # Получаем цели
        targets = await player_dal.get_pvp_targets(
            exclude_id=cast(int, player.player_id),
            current_tier=cast(TavernTier, player.tavern_level),
            limit=5
        )

        text = (
            f"🗡️ <b>Сеть осведомителей (Саботаж и Шпионаж)</b>\n\n"
            f"Наши шпионы нашли конкурентов близкого уровня. Выберите цель для операции:\n\n"
        )

        builder = InlineKeyboardBuilder()

        if targets:
            for t in targets:
                tavern_levels = {
                    "garage": "Гараж",
                    "tavern": "Таверна",
                    "brewery": "Пивоварня",
                    "factory": "Завод",
                    "guild": "Гильдия",
                }
                t_level = tavern_levels.get(t.tavern_level.value, t.tavern_level.value)
                text += (
                    f"👤 <b>Игрок #{t.tg_id}</b>\n"
                    f"⚔️ Ранг: <code>{t_level}</code> | ⭐ Репутация: <code>{t.reputation}</code>\n\n"
                )
                
                # Добавляем ряд кнопок действий для каждого конкурента
                builder.row(
                    InlineKeyboardButton(
                        text=f"🔍 Шпионить за #{t.tg_id} (200g, 10вл)",
                        callback_data=f"slums:action:spy:{t.player_id}"
                    )
                )
                builder.row(
                    InlineKeyboardButton(
                        text=f"💸 Подкупить инспектора ({t.tg_id}) (150g, 5вл)",
                        callback_data=f"slums:action:bribe:{t.player_id}"
                    ),
                    InlineKeyboardButton(
                        text=f"📢 Слухи ({t.tg_id}) (100g, 15вл)",
                        callback_data=f"slums:action:rumor:{t.player_id}"
                    )
                )
        else:
            text += "<i>В данный момент конкурентов не обнаружено. Либо все боятся вашей репутации, либо город опустел...</i>\n"

        await send_or_edit_dashboard(
            bot=callback.bot,
            player=player,
            session=session,
            text=text,
            reply_markup=add_global_navigation_footer(builder.as_markup(), back_callback="screen:slums")
        )
    except PlayerNotFoundError:
        await callback.answer("Профиль не найден.", show_alert=True)
    await callback.answer()


@slums_router.callback_query(F.data.startswith("slums:action:"))
async def process_pvp_action(callback: CallbackQuery, session: AsyncSession) -> None:
    """
    Обработчик проведения PvP действий (шпионаж, подкуп, слухи).
    """
    if not callback.from_user or not callback.message or not isinstance(callback.message, Message) or not callback.data:
        await callback.answer()
        return

    parts = callback.data.split(":")
    action_type = parts[2]
    target_id = int(parts[3])

    tg_id = callback.from_user.id
    player_dal = PlayerDAL(session)

    try:
        player = await player_dal.get_player(tg_id)
        
        # Получаем данные цели
        stmt = select(Player).where(Player.player_id == target_id)
        res_target = await session.execute(stmt)
        target = res_target.scalar_one_or_none()

        if not target:
            await callback.answer("Цель не найдена.", show_alert=True)
            return

        # Настройка стоимости и шансов успеха
        costs = {
            "spy": (Decimal("200.00"), 10, 0.70),    # gold, influence, success_chance
            "bribe": (Decimal("150.00"), 5, 0.60),
            "rumor": (Decimal("100.00"), 15, 0.50),
        }

        gold_cost, influence_cost, success_chance = costs[action_type]

        # Проверяем ресурсы игрока
        if player.gold < gold_cost:
            await callback.answer(f"❌ Недостаточно золота! Нужно {gold_cost:.0f} gold.", show_alert=True)
            return
        if player.influence < influence_cost:
            await callback.answer(f"❌ Недостаточно влияния! Нужно {influence_cost} Влияния.", show_alert=True)
            return

        # Списываем ресурсы игрока
        await player_dal.change_gold(cast(int, player.player_id), -gold_cost)
        await player_dal.update_player_stats(
            player_id=cast(int, player.player_id),
            gold_change=Decimal("0.00"),
            reputation_change=0,
            influence_change=-influence_cost
        )

        is_success = random.random() < success_chance
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="🔙 Назад к осведомителям", callback_data="slums:pvp_list"))

        text = ""

        if action_type == "spy":
            if is_success:
                # Получаем случайный рецепт цели
                stmt_rec = select(Recipe).where(Recipe.creator_id == target_id)
                res_rec = await session.execute(stmt_rec)
                recipes = res_rec.scalars().all()
                
                recipe_info = ""
                if recipes:
                    r = random.choice(recipes)
                    recipe_info = (
                        f"Секретный рецепт цели: <b>«{html.quote(cast(str, r.title))}»</b>\n"
                        f"🌾 {r.malt_pct}% | 💧 {r.water_pct}% | 🌿 {r.hop_pct}% | 🍞 {r.yeast_pct}%\n"
                        f"Крепость: {r.strength:.1f}% | Горечь: {r.bitterness:.1f} | Аромат: {r.aroma:.1f}"
                    )
                else:
                    recipe_info = "У цели пока нет записанных рецептов."

                text = (
                    f"🔍 <b>Шпионаж: УСПЕХ!</b>\n\n"
                    f"Ваш шпион успешно проник в архивы игрока #{target.tg_id}.\n\n"
                    f"💰 Золото цели: <b>{target.gold:.2f} gold</b>\n"
                    f"⭐ Репутация цели: <b>{target.reputation}</b>\n\n"
                    f"{recipe_info}"
                )
                
                # Логируем успешный шпионаж
                await player_dal.log_player_event(
                    player_id=cast(int, player.player_id),
                    event_type="pvp_success",
                    summary=f"Успешно шпионил за игроком #{target.tg_id}",
                    metadata={"target_id": target_id, "action": "spy"}
                )
            else:
                text = (
                    f"🔍 <b>Шпионаж: ПРОВАЛ!</b>\n\n"
                    f"Ваш шпион был пойман охраной на подступах к погребам игрока #{target.tg_id}!\n"
                    f"Вам пришлось заплатить штраф. Вы потеряли <b>{gold_cost:.0f} gold</b> и <b>{influence_cost} Влияния</b>."
                )

        elif action_type == "bribe":
            if is_success:
                text = (
                    f"💸 <b>Подкуп инспектора: УСПЕХ!</b>\n\n"
                    f"Взятка принята! Королевский инспектор отправлен с внеплановой проверкой в варочный зал игрока #{target.tg_id}.\n"
                    f"Качество его варок будет снижено на <b>-20%</b> в течение следующих 2 часов."
                )
                
                # Накладываем дебафф на цель
                expires = datetime.now(UTC) + timedelta(hours=2)
                await player_dal.log_player_event(
                    player_id=target_id,
                    event_type="pvp_debuff_received",
                    summary="Внеплановая проверка! Варочный зал оштрафован (-20% качества на 2 часа)",
                    metadata={"debuff": "inspection", "expires_at": expires.isoformat()}
                )
                
                # Логируем успешный саботаж у игрока
                await player_dal.log_player_event(
                    player_id=cast(int, player.player_id),
                    event_type="pvp_success",
                    summary=f"Отправил инспектора к игроку #{target.tg_id}",
                    metadata={"target_id": target_id, "action": "bribe"}
                )
            else:
                text = (
                    f"💸 <b>Подкуп инспектора: ПРОВАЛ!</b>\n\n"
                    f"Честный инспектор донес на ваших людей городской страже! Саботаж сорван.\n"
                    f"Вы потеряли <b>{gold_cost:.0f} gold</b> и <b>{influence_cost} Влияния</b>."
                )

        elif action_type == "rumor":
            if is_success:
                text = (
                    f"📢 <b>Грязные слухи: УСПЕХ!</b>\n\n"
                    f"Слухи распущены! Горожане шепчутся, что в таверне игрока #{target.tg_id} разбавляют пиво болотной водой.\n"
                    f"Спрос и цены продажи на его товар снижены на <b>-50%</b> на 12 часов!"
                )
                
                # Накладываем дебафф на цель
                expires = datetime.now(UTC) + timedelta(hours=12)
                await player_dal.log_player_event(
                    player_id=target_id,
                    event_type="pvp_debuff_received",
                    summary="Грязные слухи! Спрос и цены продажи вашего пива снижены на -50% на 12 часов",
                    metadata={"debuff": "rumors", "expires_at": expires.isoformat()}
                )
                
                # Логируем успешный саботаж у игрока
                await player_dal.log_player_event(
                    player_id=cast(int, player.player_id),
                    event_type="pvp_success",
                    summary=f"Очернил репутацию пива игрока #{target.tg_id}",
                    metadata={"target_id": target_id, "action": "rumor"}
                )
            else:
                text = (
                    f"📢 <b>Грязные слухи: ПРОВАЛ!</b>\n\n"
                    f"Глашатаи отказались распространять ложь, а ваша гильдия потеряла уважение.\n"
                    f"Вы потеряли <b>{gold_cost:.0f} gold</b> и <b>{influence_cost} Влияния</b>."
                )

        await send_or_edit_dashboard(
            bot=callback.bot,
            player=player,
            session=session,
            text=text,
            reply_markup=add_global_navigation_footer(builder.as_markup(), back_callback="slums:pvp_list")
        )

    except PlayerNotFoundError:
        await callback.answer("Профиль не найден.", show_alert=True)
    await callback.answer()
