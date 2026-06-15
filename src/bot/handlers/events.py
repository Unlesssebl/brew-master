import random
from datetime import datetime, timedelta, UTC
from decimal import Decimal
from aiogram import F, Router, html
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.states import ExpeditionStates
from src.bot.utils.keyboards import get_event_choice_keyboard
from src.core.expeditions import (
    ExpeditionEventType,
    calculate_expedition_outcome,
    calculate_injury_consequences,
)
from src.database.dal import PlayerDAL, PlayerNotFoundError
from src.database.models import Staff, StaffStatus
from src.llm_engine import LLMEventGenerator
from src.llm_engine.schemas import EventChoice, GameEvent

events_router = Router()


@events_router.callback_query(F.data == "screen:expeditions")
async def show_expeditions_screen(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Экран экспедиций и LLM-событий.
    """
    if not callback.message or not isinstance(callback.message, Message):
        await callback.answer()
        return

    await state.clear()
    text = (
        f"⛵ <b>Экспедиции и События королевства</b>\n\n"
        f"Отправляйте ваших верных агентов в опасные путешествия за золотом и ресурсами, "
        f"или поучаствуйте в уникальных событиях, сгенерированных Гейм-мастером!\n\n"
        f"Выберите действие:"
    )

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="⛵ Отправить в экспедицию", callback_data="expedition:start"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🎭 Случайное событие (LLM)", callback_data="event:trigger"
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
    await callback.answer()


@events_router.callback_query(F.data == "event:trigger")
async def trigger_llm_event(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    """
    Запускает уникальное случайное LLM-событие.
    """
    if not callback.from_user or not callback.message or not isinstance(callback.message, Message):
        await callback.answer()
        return

    tg_id = callback.from_user.id
    player_dal = PlayerDAL(session)

    try:
        player = await player_dal.get_player(tg_id)
    except PlayerNotFoundError:
        await callback.answer("Профиль не найден.", show_alert=True)
        return

    await callback.answer("🎭 Гейм-мастер генерирует событие...")

    # Формируем состояние игрока для LLM
    player_state = {
        "tg_id": int(player.tg_id),
        "gold": float(player.gold),
        "reputation": int(player.reputation),
        "influence": int(player.influence),
        "tavern_level": str(player.tavern_level.value),
    }

    # Генерируем событие
    llm_gen = LLMEventGenerator()
    event = await llm_gen.generate_event(player_state)

    # Сохраняем событие в стейте
    await state.update_data(active_event=event.model_dump())
    await state.set_state(ExpeditionStates.awaiting_choice)

    text = (
        f"📜 <b>{html.quote(event.event_title)}</b>\n\n"
        f"{html.quote(event.event_description)}\n\n"
        f"Сделайте ваш выбор:"
    )

    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_event_choice_keyboard(event.choices),
    )


@events_router.callback_query(ExpeditionStates.awaiting_choice, F.data.startswith("event:choice:"))
async def handle_event_choice(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    """
    Обрабатывает выбор игрока в LLM-событии.
    """
    if not callback.from_user or not callback.message or not isinstance(callback.message, Message) or not callback.data:
        await callback.answer()
        return

    choice_id = callback.data.split(":")[2]
    data = await state.get_data()
    event_data = data.get("active_event")

    if not event_data:
        await callback.answer("Событие устарело или не найдено.", show_alert=True)
        await state.clear()
        return

    event = GameEvent.model_validate(event_data)
    # Ищем нужный выбор
    choice = None
    for c in event.choices:
        if c.choice_id == choice_id:
            choice = c
            break

    if not choice:
        await callback.answer("Выбор не найден.", show_alert=True)
        return

    tg_id = callback.from_user.id
    player_dal = PlayerDAL(session)

    try:
        player = await player_dal.get_player(tg_id)
        # Применяем эффекты
        await player_dal.update_player_stats(
            int(player.player_id),
            gold_change=choice.gold_change,
            reputation_change=choice.reputation_change,
            influence_change=choice.influence_change,
        )

        text = (
            f"📖 <b>Результат события: «{html.quote(event.event_title)}»</b>\n\n"
            f"{html.quote(choice.result_text)}\n\n"
            f"📈 <b>Изменения:</b>\n"
            f"💰 Золото: <code>{choice.gold_change:+.2f} gold</code>\n"
            f"⭐ Репутация: <code>{choice.reputation_change:+}</code>\n"
            f"👑 Влияние: <code>{choice.influence_change:+}</code>"
        )

        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="🔙 Назад в меню", callback_data="screen:menu")
        )

        await callback.message.edit_text(
            text, parse_mode="HTML", reply_markup=builder.as_markup()
        )
    except Exception as e:
        await callback.answer(f"Ошибка применения эффекта: {str(e)}", show_alert=True)

    await state.clear()
    await callback.answer()


@events_router.callback_query(F.data == "expedition:start")
async def start_expedition(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    """
    Запускает случайную экспедицию.
    """
    if not callback.from_user or not callback.message or not isinstance(callback.message, Message):
        await callback.answer()
        return

    tg_id = callback.from_user.id
    player_dal = PlayerDAL(session)

    try:
        player = await player_dal.get_player(tg_id)
        staff_list = await player_dal.get_player_staff(int(player.player_id))

        # Выбираем доступного свободного агента (здоровый и не заблокированный)
        now = datetime.now(UTC)
        available_agents = []
        for s in staff_list:
            if str(s.status.value) != "dead":
                if s.blocked_until is None or s.blocked_until <= now:
                    available_agents.append(s)

        if not available_agents:
            await callback.answer(
                "❌ Нет свободных агентов!\nНажмите 'Отдых' для уставших сотрудников "
                "или наймите нового в разделе 'Персонал'.",
                show_alert=True,
            )
            return

        agent = random.choice(available_agents)
        # Выбираем тип события
        event_type = random.choice(list(ExpeditionEventType))

        # Сохраняем детали экспедиции в FSM
        await state.update_data(
            active_expedition={
                "staff_id": int(agent.staff_id),
                "event_type": event_type.value,
            }
        )
        await state.set_state(ExpeditionStates.awaiting_choice)

        # Сюжеты событий
        builder = InlineKeyboardBuilder()
        agent_name = str(agent.name)
        agent_skill = int(agent.skill)

        if event_type == ExpeditionEventType.BANDITS:
            text = (
                f"⚔️ <b>Опасность! Нападение бандитов</b>\n\n"
                f"На вашего агента <b>{html.quote(agent_name)}</b> в лесу напали разбойники!\n"
                f"Они требуют 100 золотых за мирный проход. Навык агента: <code>{agent_skill}</code>."
            )
            builder.row(
                InlineKeyboardButton(
                    text="⚔️ Дать отпор (Шанс от навыка)",
                    callback_data="expedition:choice:fight",
                )
            )
            builder.row(
                InlineKeyboardButton(
                    text="💰 Откупиться (100 gold)",
                    callback_data="expedition:choice:bribe",
                )
            )

        elif event_type == ExpeditionEventType.TRADE_OFFER:
            text = (
                f"💼 <b>Выгодное предложение?</b>\n\n"
                f"Странствующий купец предлагает агенту <b>{html.quote(agent_name)}</b> "
                f"выкупить старинные чертежи эльфийской пивоварни за 150 золотых.\n"
                f"Навык агента: <code>{agent_skill}</code>."
            )
            builder.row(
                InlineKeyboardButton(
                    text="🤝 Купить чертежи (-150 gold)",
                    callback_data="expedition:choice:trade_accept",
                )
            )
            builder.row(
                InlineKeyboardButton(
                    text="❌ Отказаться",
                    callback_data="expedition:choice:trade_decline",
                )
            )

        else:  # MYSTICAL_FIND
            text = (
                f"🔮 <b>Таинственная находка</b>\n\n"
                f"Агент <b>{html.quote(agent_name)}</b> наткнулся на светящийся рунический алтарь "
                f"в заброшенной шахте.\n"
                f"Алтарь пульсирует чистой магической энергией. Навык агента: <code>{agent_skill}</code>."
            )
            builder.row(
                InlineKeyboardButton(
                    text="🔮 Дотронуться до алтаря",
                    callback_data="expedition:choice:altar_activate",
                )
            )
            builder.row(
                InlineKeyboardButton(
                    text="🚪 Пройти мимо",
                    callback_data="expedition:choice:altar_pass",
                )
            )

        await callback.message.edit_text(
            text, parse_mode="HTML", reply_markup=builder.as_markup()
        )
    except PlayerNotFoundError:
        await callback.answer("Профиль не найден.", show_alert=True)

    await callback.answer()


@events_router.callback_query(ExpeditionStates.awaiting_choice, F.data.startswith("expedition:choice:"))
async def handle_expedition_choice(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    """
    Обрабатывает выбор игрока в экспедиции и рассчитывает результат.
    """
    if not callback.from_user or not callback.message or not isinstance(callback.message, Message) or not callback.data:
        await callback.answer()
        return

    choice_action = callback.data.split(":")[2]
    data = await state.get_data()
    exp_data = data.get("active_expedition")

    if not exp_data:
        await callback.answer("Экспедиция устарела или не найдена.", show_alert=True)
        await state.clear()
        return

    staff_id = int(exp_data["staff_id"])
    event_type_str = str(exp_data["event_type"])
    event_type = ExpeditionEventType(event_type_str)

    # Загружаем агента
    stmt = select(Staff).where(Staff.staff_id == staff_id)
    res = await session.execute(stmt)
    agent = res.scalar_one_or_none()

    if not agent:
        await callback.answer("Агент не найден.", show_alert=True)
        await state.clear()
        return

    tg_id = callback.from_user.id
    player_dal = PlayerDAL(session)

    try:
        player = await player_dal.get_player(tg_id)
        agent_name = str(agent.name)
        agent_skill = int(agent.skill)

        # Вычисляем исход на основе формул
        outcome = calculate_expedition_outcome(agent_skill, event_type, equipment_bonus=0)
        success = bool(outcome["success"])
        reward_mult = float(outcome["reward_multiplier"])
        injury_risk = float(outcome["injury_risk"])

        text = ""
        gold_change = Decimal("0.00")
        injury_info = ""

        # Увеличиваем усталость за поход
        agent.fatigue = min(100, int(agent.fatigue) + 15)

        if choice_action == "fight":
            if success:
                gold_change = Decimal(str(round(150 * reward_mult, 2)))
                text = (
                    f"⚔️ <b>Победа!</b>\n\n"
                    f"Агент <b>{html.quote(agent_name)}</b> проявил выдающуюся храбрость и разбил бандитов!\n"
                    f"Добыча составила: <b>{gold_change:.2f} gold</b>"
                )
            else:
                text = (
                    f"💀 <b>Поражение!</b>\n\n"
                    f"Агент <b>{html.quote(agent_name)}</b> не справился с бандитами и был вынужден бежать."
                )
                # Бросок на травму
                if random.random() <= injury_risk:
                    is_heavy = random.random() < 0.3
                    conseq = calculate_injury_consequences(is_heavy)
                    blocked_hours = conseq["blocked_hours"]

                    # Блокируем агента
                    agent.status = StaffStatus.heavy_injured if is_heavy else StaffStatus.light_injured
                    agent.blocked_until = datetime.now(UTC) + timedelta(hours=blocked_hours)

                    injury_info = (
                        f"\n⚠️ <b>Травма:</b> Агент получил <b>{'тяжелую' if is_heavy else 'легкую'} травму</b> "
                        f"и заблокирован на <code>{blocked_hours} ч.</code>!"
                    )

        elif choice_action == "bribe":
            gold_change = Decimal("-100.00")
            text = (
                f"💰 <b>Откуп</b>\n\n"
                f"Вы решили не рисковать агентом <b>{html.quote(agent_name)}</b> и заплатили бандитам 100 gold.\n"
                f"Агент благополучно вернулся назад."
            )

        elif choice_action == "trade_accept":
            # Проверяем золото
            if float(player.gold) < 150:
                await callback.answer("❌ Недостаточно золота для покупки! (нужно 150 gold)", show_alert=True)
                return

            gold_change = Decimal("-150.00")
            if success:
                reward = Decimal("350.00")
                gold_change += reward
                text = (
                    f"🤝 <b>Сделка совершена!</b>\n\n"
                    f"Агент выгодно купил чертежи и перепродал их гильдии за 350 gold.\n"
                    f"Чистая выручка: <b>+200.00 gold</b>!"
                )
            else:
                text = (
                    f"❌ <b>Обман!</b>\n\n"
                    f"Чертежи оказались фальшивыми. Вы потеряли 150 gold."
                )
                if random.random() <= injury_risk:
                    # Легкая травма от расстройства/потасовки
                    agent.status = StaffStatus.light_injured
                    agent.blocked_until = datetime.now(UTC) + timedelta(hours=12)
                    injury_info = f"\n⚠️ Агент расстроился и заблокирован на <code>12 ч.</code>"

        elif choice_action == "trade_decline":
            text = "Вы решили проигнорировать предложение купца. Экспедиция завершена ничем."

        elif choice_action == "altar_activate":
            if success:
                # Бафф навыка
                agent.skill = min(100, agent_skill + 5)
                gold_change = Decimal("100.00")
                text = (
                    f"🔮 <b>Мистический успех!</b>\n\n"
                    f"Алтарь озарил агента <b>{html.quote(agent_name)}</b> теплым светом!\n"
                    f"Навык агента повышен: <b>+5</b> (теперь <code>{agent.skill}</code>).\n"
                    f"Найдено золота: <b>+100.00 gold</b>!"
                )
            else:
                # Дебафф навыка
                agent.skill = max(1, agent_skill - 5)
                text = (
                    f"🔮 <b>Древнее проклятие!</b>\n\n"
                    f"Алтарь вспыхнул темным пламенем.\n"
                    f"Навык агента понижен: <b>-5</b> (теперь <code>{agent.skill}</code>)."
                )

        elif choice_action == "altar_pass":
            text = "Вы решили не трогать алтарь и прошли мимо. Экспедиция завершена."

        # Применяем финансовые изменения
        if gold_change != 0:
            await player_dal.change_gold(int(player.player_id), gold_change)

        text += injury_info

        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="🔙 Назад в меню", callback_data="screen:menu")
        )

        await callback.message.edit_text(
            text, parse_mode="HTML", reply_markup=builder.as_markup()
        )
    except Exception as e:
        await callback.answer(f"Ошибка завершения экспедиции: {str(e)}", show_alert=True)

    await state.clear()
    await callback.answer()
