from typing import cast
import random
from decimal import Decimal
from aiogram import F, Router, html
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.keyboards.inline import get_main_menu_keyboard, add_global_navigation_footer
from src.bot.states import TutorialStates
from src.bot.utils.formatters import get_reputation_title, get_tavern_name
from src.bot.utils.hud import send_or_edit_dashboard
from src.database.dal import PlayerDAL, PlayerNotFoundError
from src.database.models import Staff, Batch, Patent, Recipe, TransactionLog

menu_router = Router()


@menu_router.callback_query(F.data == "screen:menu")
async def show_menu_callback(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    """
    Отображает главное меню (Карту Города) при нажатии кнопки "Назад в меню/город".
    """
    await state.clear()
    if not callback.from_user or not callback.message or not isinstance(callback.message, Message):
        await callback.answer()
        return

    tg_id = callback.from_user.id
    player_dal = PlayerDAL(session)

    try:
        player = await player_dal.get_player(tg_id)
        
        rep_title = get_reputation_title(cast(int, player.reputation))
        t_name = get_tavern_name(cast(int, player.reputation))
        rep_sign = "+" if cast(int, player.reputation) >= 0 else ""
        
        text = (
            f"╔════════[ 🗺️ <b>КАРТА ГОРОДА</b> ]════════╗\n"
            f"║  🏰 Таверна: <b>«{t_name}»</b>\n"
            f"║  ⭐ Репутация: <code>{rep_sign}{player.reputation}</code> ({rep_title})\n"
            f"╚═══════════════════════════════════╝\n\n"
            f"<i>Вы стоите на рыночной площади. Куда направитесь дальше, мастер?</i>"
        )
        
        alerts = await player_dal.get_alerts_summary(cast(int, player.player_id))
        await send_or_edit_dashboard(
            bot=callback.bot,
            player=player,
            session=session,
            text=text,
            reply_markup=get_main_menu_keyboard(alerts),
        )
        
    except PlayerNotFoundError:
        await callback.answer("Профиль не найден. Напишите /start", show_alert=True)

    await callback.answer()


@menu_router.callback_query(F.data == "screen:inventory")
async def show_inventory(callback: CallbackQuery, session: AsyncSession) -> None:
    """
    Экран инвентаря игрока (Тёмный Погреб).
    """
    if not callback.from_user or not callback.message or not isinstance(callback.message, Message):
        await callback.answer()
        return

    tg_id = callback.from_user.id
    player_dal = PlayerDAL(session)

    try:
        player = await player_dal.get_player(tg_id)
        resources = await player_dal.get_resources(cast(int, player.player_id))

        # Получаем бочки на складе
        stmt = select(Batch).where(
            Batch.player_id == cast(int, player.player_id),
            Batch.quantity_barrels > 0,
            Batch.is_completed.is_(True),
        )
        res = await session.execute(stmt)
        batches = res.scalars().all()

        alerts = await player_dal.get_alerts_summary(cast(int, player.player_id))

        text = (
            f"🏺 <b>Тёмный Погреб (Склад)</b>\n"
            f"<code>┌────────────────────────────</code>\n"
            f"🌾 <b>Солод:</b> <code>{resources.get('malt', Decimal('0')):.1f} кг</code>\n"
            f"💧 <b>Вода:</b> <code>{resources.get('water', Decimal('0')):.1f} л</code>\n"
            f"🌿 <b>Хмель:</b> <code>{resources.get('hops', Decimal('0')):.1f} кг</code>\n"
            f"🍞 <b>Дрожжи:</b> <code>{resources.get('yeast', Decimal('0')):.1f} кг</code>\n"
            f"<code>└────────────────────────────</code>\n\n"
        )

        builder = InlineKeyboardBuilder()
        if alerts.get("ready_batches", 0) > 0:
            builder.row(
                InlineKeyboardButton(
                    text=f"🟢 Собрать пиво ({alerts['ready_batches']} шт)",
                    callback_data="inventory:collect_ready",
                )
            )

        if batches:
            text += "🍺 <b>Бочки готового пива на складе:</b>\n"
            seen_recipes = set()
            for b in batches:
                # Попробуем загрузить рецепт
                stmt_recipe = select(Recipe).where(Recipe.recipe_id == cast(int, b.recipe_id))
                recipe_res = await session.execute(stmt_recipe)
                recipe = recipe_res.scalar_one_or_none()
                recipe_title = str(recipe.title) if recipe else "Неизвестное пиво"
                
                # Проверим, есть ли патент для этого рецепта
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

                text += (
                    f"• <b>«{html.quote(cast(str, display_title))}»</b> — <code>{b.quantity_barrels} шт.</code>\n"
                    f"  (Качество: <code>{b.quality_modifier:.2f}x</code>)\n"
                )
                
                # Добавляем кнопку осмотра патента, если есть заполненный лор/название
                if patent and patent.patent_id not in seen_recipes:
                    seen_recipes.add(patent.patent_id)
                    builder.row(
                        InlineKeyboardButton(
                            text=f"🔍 Осмотреть «{display_title}»",
                            callback_data=f"patent:examine:{patent.patent_id}"
                        )
                    )
        else:
            text += "🍺 На складе пока нет готового пива.\n"

        # Если предыдущее сообщение было фото (например, при просмотре патента),
        # мы должны принудительно отправить новое текстовое сообщение
        force_new = False
        if callback.message and (callback.message.photo or callback.message.document):
            force_new = True

        await send_or_edit_dashboard(
            bot=callback.bot,
            player=player,
            session=session,
            text=text,
            reply_markup=add_global_navigation_footer(builder.as_markup()),
            force_new=force_new
        )
        
    except PlayerNotFoundError:
        await callback.answer("Профиль не найден. Напишите /start", show_alert=True)

    await callback.answer()


@menu_router.callback_query(F.data == "inventory:collect_ready")
async def collect_ready_batches_callback(
    callback: CallbackQuery, session: AsyncSession, state: FSMContext
) -> None:
    """
    Собирает созревшие партии пива на склад.
    """
    if not callback.from_user or not callback.message or not isinstance(callback.message, Message):
        await callback.answer()
        return

    tg_id = callback.from_user.id
    player_dal = PlayerDAL(session)

    try:
        player = await player_dal.get_player(tg_id)
        result = await player_dal.collect_ready_batches(cast(int, player.player_id))
        if result["batches"] == 0:
            if player.tutorial_step == 1:
                # Проверим, есть ли вообще партии у игрока в базе
                stmt = select(func.count(Batch.batch_id)).where(Batch.player_id == cast(int, player.player_id))
                res_count = await session.execute(stmt)
                total_batches = res_count.scalar_one_or_none() or 0
                
                if total_batches > 0:
                    # Игрок уже собрал пиво ранее. Переводим на шаг 2.
                    await player_dal.update_tutorial_step(tg_id, 2)
                    await state.set_state(TutorialStates.first_sell)
                    builder = InlineKeyboardBuilder()
                    builder.row(InlineKeyboardButton(text="⚖️ Торговая площадь", callback_data="screen:market"))
                    await send_or_edit_dashboard(
                        bot=callback.bot,
                        player=player,
                        session=session,
                        text="🏺 <b>Пиво на складе!</b>\n\n"
                             "Пора выходить на рынок. Отправляйся на Торговую площадь.",
                        reply_markup=builder.as_markup()
                    )
                    await callback.answer("Пиво уже собрано!")
                    return
                else:
                    # Партий вообще нет. Сбрасываем обучение на шаг 0, чтобы игрок мог сварить заново.
                    await player_dal.update_tutorial_step(tg_id, 0)
                    await state.clear()
                    try:
                        await callback.message.delete()
                    except Exception:
                        pass
                    if player.hud_message_id:
                        player.hud_message_id = None
                        session.add(player)
                        await session.flush()
                    await callback.bot.send_message(
                        chat_id=callback.message.chat.id,
                        text="📜 <b>Обучение сброшено!</b>\n\n"
                             "Кажется, ваша первая варка была утеряна. Напишите /start, чтобы начать обучение заново.",
                        parse_mode="HTML"
                    )
                    await callback.answer("Обучение сброшено!")
                    return

            await callback.answer("Готовых партий для сбора нет.", show_alert=True)
            return

        if player.tutorial_step == 1:
            await player_dal.update_tutorial_step(tg_id, 2)
            await state.set_state(TutorialStates.first_sell)

        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="🏺 Открыть погреб", callback_data="screen:inventory"))

        await send_or_edit_dashboard(
            bot=callback.bot,
            player=player,
            session=session,
            text=f"🟢 <b>Пиво собрано!</b>\n\n"
                 f"В погреб перенесено партий: <code>{result['batches']}</code>\n"
                 f"Всего бочек: <code>{result['barrels']}</code>",
            reply_markup=add_global_navigation_footer(builder.as_markup()),
        )
        await callback.answer("Пиво собрано!")
        
    except PlayerNotFoundError:
        await callback.answer("Профиль не найден. Напишите /start", show_alert=True)


@menu_router.callback_query(F.data == "screen:chronicle")
async def show_chronicle(callback: CallbackQuery, session: AsyncSession) -> None:
    """
    Экран "Летопись Мастера" (профиль игрока с логом событий).
    """
    if not callback.from_user or not callback.message or not isinstance(callback.message, Message):
        await callback.answer()
        return

    tg_id = callback.from_user.id
    player_dal = PlayerDAL(session)

    try:
        player = await player_dal.get_player(tg_id)
        rep_title = get_reputation_title(cast(int, player.reputation))
        
        # Получаем последние 5 событий
        recent_events = await player_dal.get_recent_events(cast(int, player.player_id), limit=5)
        events_text = ""
        if recent_events:
            for ev in recent_events:
                created_str = ev.created_at.strftime("%H:%M")
                events_text += f"• <code>[{created_str}]</code> {ev.summary}\n"
        else:
            events_text = "• <i>Летопись пока чиста... Сварите первую партию!</i>\n"

        # Варок проведено
        stmt_brews = select(func.count(Batch.batch_id)).where(Batch.player_id == cast(int, player.player_id))
        brews_res = await session.execute(stmt_brews)
        total_brews = brews_res.scalar_one_or_none() or 0

        # Бочек продано
        stmt_sales = select(func.sum(TransactionLog.volume)).where(TransactionLog.seller_id == cast(int, player.player_id))
        sales_res = await session.execute(stmt_sales)
        total_sales = sales_res.scalar_one_or_none() or 0

        # Активных патентов
        stmt_patents = select(func.count(Patent.patent_id)).where(
            Patent.player_id == cast(int, player.player_id), Patent.is_active.is_(True)
        )
        patents_res = await session.execute(stmt_patents)
        total_patents = patents_res.scalar_one_or_none() or 0

        # Ранг таверны
        tavern_levels = {
            "garage": "Гараж (уровень 1)",
            "tavern": "Таверна (уровень 2)",
            "brewery": "Пивоварня (уровень 3)",
            "factory": "Завод (уровень 4)",
            "guild": "Гильдия Пивоваров (уровень 5)",
        }
        rank_str = tavern_levels.get(player.tavern_level.value, "Неизвестно")

        # Рисуем полосы прогресса (0-10 делений)
        rep_normalized = max(-100, min(100, cast(int, player.reputation)))
        rep_pct = int((rep_normalized + 100) / 20)
        rep_bar = "█" * rep_pct + "░" * (10 - rep_pct)

        inf_normalized = max(0, min(100, cast(int, player.influence)))
        inf_pct = int(inf_normalized / 10)
        inf_bar = "█" * inf_pct + "░" * (10 - inf_pct)

        user_name = callback.from_user.full_name

        text = (
            f"📜 <b>ЛЕТОПИСЬ МАСТЕРА — {html.quote(user_name)}</b>\n\n"
            f"⚔️ <b>Ранг таверны:</b>  <code>{rank_str}</code>\n"
            f"💰 <b>Золото:</b>        <code>{player.gold:.2f} g</code>\n"
            f"⭐ <b>Репутация:</b>     <code>{player.reputation:+.0f}</code>  <code>[{rep_bar}]</code> {rep_title}\n"
            f"👑 <b>Влияние:</b>       <code>{player.influence}</code>  <code>[{inf_bar}]</code>\n"
            f"💎 <b>Кристаллы:</b>     <code>{player.prestige_crystals}</code>\n\n"
            f"🍺 <b>Варок проведено:</b>    <code>{total_brews}</code>\n"
            f"📦 <b>Бочек продано:</b>      <code>{total_sales}</code>\n"
            f"📜 <b>Активных патентов:</b>  <code>{total_patents}</code>\n\n"
            f"✍️ <b>ПОСЛЕДНИЕ СОБЫТИЯ:</b>\n"
            f"{events_text}\n"
        )

        builder = InlineKeyboardBuilder()

        await send_or_edit_dashboard(
            bot=callback.bot,
            player=player,
            session=session,
            text=text,
            reply_markup=add_global_navigation_footer(builder.as_markup()),
        )
        
    except PlayerNotFoundError:
        try:
            await callback.answer("Профиль не найден.", show_alert=True)
        except Exception:
            pass

    try:
        await callback.answer()
    except Exception:
        pass


@menu_router.callback_query(F.data.startswith("patent:examine:"))
async def examine_patent_callback(callback: CallbackQuery, session: AsyncSession) -> None:
    """
    Обработчик просмотра деталей патента (лор + статы + картинка).
    """
    if not callback.from_user or not callback.message or not isinstance(callback.message, Message) or not callback.data:
        await callback.answer()
        return

    patent_id = int(callback.data.split(":")[2])
    stmt = select(Patent).where(Patent.patent_id == patent_id)
    res = await session.execute(stmt)
    patent = res.scalar_one_or_none()

    if not patent:
        await callback.answer("Патент не найден.", show_alert=True)
        return

    # Загружаем рецепт
    stmt_recipe = select(Recipe).where(Recipe.recipe_id == patent.recipe_id)
    recipe_res = await session.execute(stmt_recipe)
    recipe = recipe_res.scalar_one_or_none()

    recipe_title = recipe.title if recipe else "Неизвестный рецепт"
    lore_name = patent.lore_name or recipe_title
    lore_text = patent.lore_text or "Описание этого легендарного напитка утеряно..."

    if recipe:
        strength_val = f"{recipe.strength:.1f}%"
        bitterness_val = f"{recipe.bitterness:.1f} IBU"
        aroma_val = f"{recipe.aroma:.1f}"
        stability_val = f"{recipe.stability}%"
    else:
        strength_val = "0.0%"
        bitterness_val = "0.0 IBU"
        aroma_val = "0.0"
        stability_val = "0%"

    caption = (
        f"📜 <b>ПАТЕНТ: «{html.quote(cast(str, lore_name))}»</b>\n"
        f"<code>┌────────────────────────────</code>\n"
        f"💪 Крепость: <code>{strength_val}</code>\n"
        f"⚡ Горечь: <code>{bitterness_val}</code>\n"
        f"👃 Аромат: <code>{aroma_val}</code>\n"
        f"🛡️ Стабильность: <code>{stability_val}</code>\n"
        f"<code>└────────────────────────────</code>\n\n"
        f"<i>{html.quote(cast(str, lore_text))}</i>"
    )

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="❌ Закрыть", callback_data="screen:inventory"))

    if patent.card_image_file_id:
        try:
            new_msg = await callback.message.answer_photo(
                photo=cast(str, patent.card_image_file_id),
                caption=caption,
                parse_mode="HTML",
                reply_markup=builder.as_markup()
            )
            try:
                await callback.message.delete()
            except Exception:
                pass
            player.hud_message_id = new_msg.message_id
            session.add(player)
            await session.flush()
        except Exception:
            # Если отправка фото не сработала, обновим текстом в дашборде
            player = await PlayerDAL(session).get_player(callback.from_user.id)
            await send_or_edit_dashboard(
                bot=callback.bot,
                player=player,
                session=session,
                text=caption,
                reply_markup=builder.as_markup()
            )
    else:
        player = await PlayerDAL(session).get_player(callback.from_user.id)
        await send_or_edit_dashboard(
            bot=callback.bot,
            player=player,
            session=session,
            text=caption,
            reply_markup=builder.as_markup()
        )

    await callback.answer()


@menu_router.callback_query(F.data == "screen:staff")
async def show_staff(callback: CallbackQuery, session: AsyncSession) -> None:
    """
    Экран управления персоналом.
    """
    if not callback.from_user or not callback.message or not isinstance(callback.message, Message):
        await callback.answer()
        return

    tg_id = callback.from_user.id
    player_dal = PlayerDAL(session)

    try:
        player = await player_dal.get_player(tg_id)
        staff_list = await player_dal.get_player_staff(cast(int, player.player_id))

        text = "👥 <b>Управление персоналом</b>\n\n"

        builder = InlineKeyboardBuilder()

        if staff_list:
            for s in staff_list:
                status_val = str(s.status.value)
                status_emoji = "🟢" if status_val == "healthy" else "🟡"
                if status_val == "dead":
                    status_emoji = "💀"

                role_ru = {
                    "master_alchemist": "🧙‍♂️ Мастер-алхимик",
                    "caravaner": "⛵ Караванщик",
                    "merchant": "💼 Торговец",
                }.get(str(s.role.value), str(s.role.value))

                text += (
                    f"👤 <b>{html.quote(str(s.name))}</b> — {role_ru}\n"
                    f"⚡ Навык: <code>{s.skill}/100</code> | 😩 Усталость: <code>{s.fatigue}%</code>\n"
                    f"{status_emoji} Статус: <code>{status_val}</code>\n"
                )
                if s.blocked_until:
                    from datetime import datetime, UTC
                    now = datetime.now(UTC)
                    blocked_until_aware = s.blocked_until
                    if blocked_until_aware > now:
                        hours_left = int((blocked_until_aware - now).total_seconds() / 3600) + 1
                        text += f"⏳ Заблокирован еще на {hours_left} ч.\n"

                text += "\n"

                if cast(int, s.fatigue) > 0 and status_val != "dead":
                    builder.row(
                        InlineKeyboardButton(
                            text=f"💤 Отправить отдыхать {s.name}",
                            callback_data=f"staff:rest:{s.staff_id}",
                        )
                    )
        else:
            text += "У вас пока нет нанятых сотрудников. Вы можете нанять их за 300 золота!\n\n"

        builder.row(
            InlineKeyboardButton(
                text="🤝 Нанять сотрудника (300 gold)", callback_data="staff:recruit"
            )
        )

        await send_or_edit_dashboard(
            bot=callback.bot,
            player=player,
            session=session,
            text=text,
            reply_markup=add_global_navigation_footer(builder.as_markup(), back_callback="screen:tavern"),
        )
        
    except PlayerNotFoundError:
        await callback.answer("Профиль не найден. Напишите /start", show_alert=True)

    await callback.answer()


@menu_router.callback_query(F.data.startswith("staff:rest:"))
async def rest_staff(callback: CallbackQuery, session: AsyncSession) -> None:
    if not callback.message or not isinstance(callback.message, Message) or not callback.data:
        await callback.answer()
        return

    staff_id = int(callback.data.split(":")[2])

    stmt = select(Staff).where(Staff.staff_id == staff_id)
    res = await session.execute(stmt)
    staff = res.scalar_one_or_none()

    if staff:
        staff.fatigue = 0
        await session.flush()
        await callback.answer(f"💤 {staff.name} отдохнул и готов к работе!", show_alert=True)
        await show_staff(callback, session)
    else:
        await callback.answer("Сотрудник не найден.", show_alert=True)


@menu_router.callback_query(F.data == "staff:recruit")
async def recruit_staff(callback: CallbackQuery, session: AsyncSession) -> None:
    if not callback.from_user or not callback.message or not isinstance(callback.message, Message):
        await callback.answer()
        return

    tg_id = callback.from_user.id
    player_dal = PlayerDAL(session)

    try:
        player = await player_dal.get_player(tg_id)

        await player_dal.change_gold(cast(int, player.player_id), Decimal("-300.00"))

        names = ["Бертранд", "Олаф", "Фридрих", "Ульрих", "Сигурд", "Торвальд", "Гуннар", "Альрик"]
        roles = ["master_alchemist", "caravaner", "merchant"]

        name = random.choice(names)
        role = random.choice(roles)
        skill = random.randint(20, 60)

        await player_dal.create_staff(cast(int, player.player_id), name, role, skill)

        role_ru = {
            "master_alchemist": "Мастер-алхимик",
            "caravaner": "Караванщик",
            "merchant": "Торговец",
        }.get(role, role)

        # Записываем событие найма
        summary = f"Нанял сотрудника: {name} ({role_ru}, навык {skill}/100)"
        await player_dal.log_player_event(
            player_id=cast(int, player.player_id),
            event_type="recruit_staff",
            summary=summary,
            metadata={"name": name, "role": role, "skill": skill}
        )

        await callback.answer(
            f"🤝 Успешно нанят новый сотрудник!\n"
            f"Имя: {name}\n"
            f"Роль: {role_ru}\n"
            f"Навык: {skill}/100",
            show_alert=True,
        )

        await show_staff(callback, session)
    except PlayerNotFoundError:
        await callback.answer("Профиль не найден.", show_alert=True)
    except Exception:
        await callback.answer("❌ Недостаточно золота для найма! (нужно 300 gold)", show_alert=True)
