import random
from decimal import Decimal
from aiogram import F, Router, html
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.keyboards.inline import get_main_menu_keyboard
from src.bot.states import TutorialStates
from src.bot.utils.formatters import get_profile_text
from src.database.dal import PlayerDAL, PlayerNotFoundError
from src.database.models import Staff, Batch

menu_router = Router()


@menu_router.callback_query(F.data == "screen:menu")
async def show_menu_callback(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    """
    Отображает главное меню при нажатии кнопки "Назад в меню".
    """
    await state.clear()
    if not callback.from_user or not callback.message or not isinstance(callback.message, Message):
        await callback.answer()
        return

    tg_id = callback.from_user.id
    player_dal = PlayerDAL(session)

    try:
        player = await player_dal.get_player(tg_id)
        text = get_profile_text(player)
        alerts = await player_dal.get_alerts_summary(int(player.player_id))
        await callback.message.edit_text(
            text, parse_mode="HTML", reply_markup=get_main_menu_keyboard(alerts)
        )
    except PlayerNotFoundError:
        await callback.answer("Профиль не найден. Напишите /start", show_alert=True)

    await callback.answer()


@menu_router.callback_query(F.data == "screen:inventory")
async def show_inventory(callback: CallbackQuery, session: AsyncSession) -> None:
    """
    Экран инвентаря игрока.
    """
    if not callback.from_user or not callback.message or not isinstance(callback.message, Message):
        await callback.answer()
        return

    tg_id = callback.from_user.id
    player_dal = PlayerDAL(session)

    try:
        player = await player_dal.get_player(tg_id)
        resources = await player_dal.get_resources(int(player.player_id))

        # Получаем бочки на складе
        stmt = select(Batch).where(
            Batch.player_id == int(player.player_id),
            Batch.quantity_barrels > 0,
            Batch.is_completed.is_(True),
        )
        res = await session.execute(stmt)
        batches = res.scalars().all()

        text = (
            f"🎒 <b>Ваш инвентарь</b>\n"
            f"<code>┌────────────────────────────</code>\n"
            f"🌾 <b>Солод:</b> <code>{resources.get('malt', Decimal('0')):.1f} кг</code>\n"
            f"💧 <b>Вода:</b> <code>{resources.get('water', Decimal('0')):.1f} л</code>\n"
            f"🌿 <b>Хмель:</b> <code>{resources.get('hops', Decimal('0')):.1f} кг</code>\n"
            f"🍞 <b>Дрожжи:</b> <code>{resources.get('yeast', Decimal('0')):.1f} кг</code>\n"
            f"<code>└────────────────────────────</code>\n\n"
        )

        if batches:
            text += "🍺 <b>Бочки готового пива на складе:</b>\n"
            for b in batches:
                # Попробуем загрузить рецепт
                from src.database.models import Recipe
                stmt_recipe = select(Recipe).where(Recipe.recipe_id == int(b.recipe_id))
                recipe_res = await session.execute(stmt_recipe)
                recipe = recipe_res.scalar_one_or_none()
                recipe_title = str(recipe.title) if recipe else "Неизвестное пиво"
                text += (
                    f"• <b>«{html.quote(recipe_title)}»</b> — <code>{b.quantity_barrels} шт.</code>\n"
                    f"  (Качество: <code>{b.quality_modifier:.2f}x</code>)\n"
                )
        else:
            text += "🍺 На складе пока нет готового пива.\n"

        # Клавиатура
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(
                text="🛒 Купить сырье (100 gold)",
                callback_data="inventory:buy_resources",
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
        result = await player_dal.collect_ready_batches(int(player.player_id))
        if result["batches"] == 0:
            await callback.answer("Готовых партий для сбора нет.", show_alert=True)
            return

        if player.tutorial_step == 1:
            await player_dal.update_tutorial_step(tg_id, 2)
            await state.set_state(TutorialStates.first_sell)

        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="🎒 Открыть склад", callback_data="screen:inventory"))
        builder.row(InlineKeyboardButton(text="🔙 Назад в меню", callback_data="screen:menu"))

        await callback.message.edit_text(
            f"🟢 <b>Пиво собрано!</b>\n\n"
            f"На склад перенесено партий: <code>{result['batches']}</code>\n"
            f"Всего бочек: <code>{result['barrels']}</code>",
            parse_mode="HTML",
            reply_markup=builder.as_markup(),
        )
        await callback.answer("Пиво собрано!")
    except PlayerNotFoundError:
        await callback.answer("Профиль не найден. Напишите /start", show_alert=True)


@menu_router.callback_query(F.data == "inventory:buy_resources")
async def buy_resources_callback(callback: CallbackQuery, session: AsyncSession) -> None:
    """
    Обработчик покупки пакета ресурсов.
    """
    if not callback.from_user or not callback.message or not isinstance(callback.message, Message):
        await callback.answer()
        return

    tg_id = callback.from_user.id
    player_dal = PlayerDAL(session)

    try:
        player = await player_dal.get_player(tg_id)
        # Стоимость пакета: 100 gold, количество: 50 шт
        await player_dal.buy_resources_pack(
            int(player.player_id), cost=Decimal("100.00"), amount=Decimal("50.00")
        )
        await callback.answer("🎒 Ресурсы успешно куплены! (+50 каждого вида)", show_alert=True)
        # Перерисовываем экран инвентаря
        await show_inventory(callback, session)
    except PlayerNotFoundError:
        await callback.answer("Профиль не найден.", show_alert=True)
    except Exception:
        await callback.answer("❌ Ошибка покупки: Недостаточно золота!", show_alert=True)


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
        staff_list = await player_dal.get_player_staff(int(player.player_id))

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
                    "caravaner": "⛵ Caravaner",
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

                # Если сотрудник устал, добавляем кнопку отдыха
                if int(s.fatigue) > 0 and status_val != "dead":
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
        builder.row(
            InlineKeyboardButton(
                text="🔙 Назад в меню", callback_data="screen:menu"
            )
        )

        await callback.message.edit_text(
            text, parse_mode="HTML", reply_markup=builder.as_markup()
        )
    except PlayerNotFoundError:
        await callback.answer("Профиль не найден. Напишите /start", show_alert=True)

    await callback.answer()


@menu_router.callback_query(F.data.startswith("staff:rest:"))
async def rest_staff(callback: CallbackQuery, session: AsyncSession) -> None:
    """
    Обработчик отправки сотрудника на отдых.
    """
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
    """
    Обработчик найма нового сотрудника.
    """
    if not callback.from_user or not callback.message or not isinstance(callback.message, Message):
        await callback.answer()
        return

    tg_id = callback.from_user.id
    player_dal = PlayerDAL(session)

    try:
        player = await player_dal.get_player(tg_id)

        # Списываем 300 золота за найм
        await player_dal.change_gold(int(player.player_id), Decimal("-300.00"))

        # Генерируем случайного сотрудника
        names = ["Бертранд", "Олаф", "Фридрих", "Ульрих", "Сигурд", "Торвальд", "Гуннар", "Альрик"]
        roles = ["master_alchemist", "caravaner", "merchant"]

        name = random.choice(names)
        role = random.choice(roles)
        skill = random.randint(20, 60)

        await player_dal.create_staff(int(player.player_id), name, role, skill)

        role_ru = {
            "master_alchemist": "Мастер-алхимик",
            "caravaner": "Караванщик",
            "merchant": "Торговец",
        }.get(role, role)

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
