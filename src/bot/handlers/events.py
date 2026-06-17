import random
from datetime import datetime, timedelta, UTC
from decimal import Decimal
from aiogram import F, Router, html
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.keyboards.inline import get_event_choice_keyboard, add_global_navigation_footer
from src.bot.states import ExpeditionStates
from src.core.expeditions import (
    ExpeditionEventType,
    calculate_expedition_outcome,
    calculate_injury_consequences,
)
from src.database.dal import PlayerDAL, PlayerNotFoundError
from src.database.models import Staff, StaffStatus, StaffRole
from src.llm_engine import LLMEventGenerator
from src.llm_engine.schemas import EventChoice, GameEvent
from src.bot.utils.hud import send_or_edit_dashboard

events_router = Router()


@events_router.callback_query(F.data == "screen:expeditions")
async def show_expeditions_screen(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    """
    Экран экспедиций и LLM-событий (Ворота).
    """
    if not callback.message or not isinstance(callback.message, Message):
        await callback.answer()
        return

    await state.clear()
    text = (
        f"🗺️ <b>Городские ворота</b>\n\n"
        f"Отсюда караваны отправляются в неизведанные земли. Вы можете направить своих караванщиков "
        f"и торговцев в экспедиции за золотом, или довериться судьбе и активировать случайное событие королевства.\n\n"
        f"Выберите действие:"
    )

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="⛵ Подготовить экспедицию", callback_data="expedition:start"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🎭 Случайное событие (LLM)", callback_data="event:trigger"
        )
    )

    player_dal = PlayerDAL(session)
    player = await player_dal.get_player(callback.from_user.id)

    await send_or_edit_dashboard(
        bot=callback.bot,
        player=player,
        session=session,
        text=text,
        reply_markup=add_global_navigation_footer(builder.as_markup())
    )
    await callback.answer()


@events_router.callback_query(F.data == "expedition:start")
async def start_expedition_setup(
    callback: CallbackQuery, session: AsyncSession
) -> None:
    """
    Экран выбора агента для экспедиции.
    """
    if not callback.from_user or not callback.message or not isinstance(callback.message, Message):
        await callback.answer()
        return

    tg_id = callback.from_user.id
    player_dal = PlayerDAL(session)

    try:
        player = await player_dal.get_player(tg_id)
        
        # Получаем всех караванщиков и торговцев
        stmt = select(Staff).where(
            Staff.player_id == int(player.player_id),
            Staff.role.in_([StaffRole.caravaner, StaffRole.merchant]),
            Staff.status != StaffStatus.dead
        )
        res = await session.execute(stmt)
        staff_list = res.scalars().all()

        now = datetime.now(UTC)
        free_agents = []
        busy_agents = []

        for s in staff_list:
            if s.blocked_until and s.blocked_until > now:
                busy_agents.append(s)
            elif s.fatigue >= 100:
                busy_agents.append(s)
            else:
                free_agents.append(s)

        text = "⛵ <b>Выбор агента для экспедиции</b>\n\n"
        builder = InlineKeyboardBuilder()

        if free_agents:
            text += "👥 <b>Доступные агенты:</b>\n"
            for s in free_agents:
                role_ru = "Караванщик" if s.role == StaffRole.caravaner else "Торговец"
                text += f"• <b>{s.name}</b> ({role_ru}) — Навык: <code>{s.skill}</code> | Усталость: <code>{s.fatigue}%</code>\n"
                
                builder.row(
                    InlineKeyboardButton(
                        text=f"Отправить {s.name} ({role_ru})",
                        callback_data=f"expedition:run:{s.staff_id}"
                    )
                )
            
            # Кнопка Bulk Action
            if len(free_agents) > 1:
                builder.row(
                    InlineKeyboardButton(
                        text="⛵ Отправить всех свободных в авто-поход",
                        callback_data="expedition:run:all"
                    )
                )
        else:
            text += "❌ <i>У вас нет свободных караванщиков или торговцев. Направьте их на отдых в Таверне или наймите новых!</i>\n\n"

        if busy_agents:
            text += "\n⏳ <b>Занятые/Уставшие агенты:</b>\n"
            for s in busy_agents:
                role_ru = "Караванщик" if s.role == StaffRole.caravaner else "Торговец"
                status_desc = "устал (100%)" if s.fatigue >= 100 else "в походе"
                text += f"• {s.name} ({role_ru}) — {status_desc}\n"

        await send_or_edit_dashboard(
            bot=callback.bot,
            player=player,
            session=session,
            text=text,
            reply_markup=add_global_navigation_footer(builder.as_markup(), back_callback="screen:expeditions")
        )

    except PlayerNotFoundError:
        await callback.answer("Профиль не найден.", show_alert=True)
    await callback.answer()


@events_router.callback_query(F.data.startswith("expedition:run:"))
async def run_expedition(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    """
    Запускает экспедицию для выбранного агента (или bulk action).
    """
    if not callback.from_user or not callback.message or not isinstance(callback.message, Message):
        await callback.answer()
        return

    agent_id_str = callback.data.split(":")[2]
    tg_id = callback.from_user.id
    player_dal = PlayerDAL(session)

    try:
        player = await player_dal.get_player(tg_id)
        
        # BULK ACTION
        if agent_id_str == "all":
            # Находим всех свободных агентов
            stmt = select(Staff).where(
                Staff.player_id == int(player.player_id),
                Staff.role.in_([StaffRole.caravaner, StaffRole.merchant]),
                Staff.status != StaffStatus.dead
            )
            res = await session.execute(stmt)
            staff_list = res.scalars().all()

            now = datetime.now(UTC)
            free_agents = [s for s in staff_list if (not s.blocked_until or s.blocked_until <= now) and s.fatigue < 100]

            if not free_agents:
                await callback.answer("Нет доступных агентов.", show_alert=True)
                return

            total_gold = Decimal("0.00")
            details = []
            
            for agent in free_agents:
                # Награда зависит от навыка
                reward = Decimal(str(round(float(agent.skill) * random.uniform(1.2, 2.5), 2)))
                total_gold += reward
                
                # Усталость +20%
                agent.fatigue = min(100, agent.fatigue + 20)
                # Блокировка на 2 минуты
                agent.blocked_until = datetime.now(UTC) + timedelta(minutes=2)
                session.add(agent)
                
                role_ru = "Караванщик" if agent.role == StaffRole.caravaner else "Торговец"
                details.append(f"• {agent.name} ({role_ru}) принесет <b>{reward:.1f} gold</b>")
                
                # Записываем событие авто-экспедиции в лог игрока
                await player_dal.log_player_event(
                    player_id=int(player.player_id),
                    event_type="expedition_event",
                    summary=f"Отправил {agent.name} в торговый поход (+{reward:.1f} gold)",
                    metadata={"agent_id": agent.staff_id, "gold_reward": float(reward)}
                )

            # Начисляем золото игроку
            await player_dal.change_gold(int(player.player_id), total_gold)

            text = (
                f"⛵ <b>Торговый караван отправлен!</b>\n\n"
                f"Вы собрали всех свободных агентов в единый караван и направили их на рынки соседних королевств.\n\n"
                f"📜 <b>Детали похода:</b>\n" + "\n".join(details) + "\n\n"
                f"💰 Суммарная выручка: <b>{total_gold:.1f} gold</b> (золото уже начислено).\n"
                f"⏳ Агенты вернутся и будут готовы к новым поручениям через 2 минуты."
            )

            builder = InlineKeyboardBuilder()

            await send_or_edit_dashboard(
                bot=callback.bot,
                player=player,
                session=session,
                text=text,
                reply_markup=add_global_navigation_footer(builder.as_markup(), back_callback="screen:expeditions")
            )
            await callback.answer("Караван отправлен!")
            return

        # ИНТЕРАКТИВНОЕ СОБЫТИЕ ДЛЯ ОДНОГО АГЕНТА
        agent_id = int(agent_id_str)
        stmt = select(Staff).where(Staff.staff_id == agent_id)
        res = await session.execute(stmt)
        agent = res.scalar_one_or_none()

        if not agent:
            await callback.answer("Агент не найден.", show_alert=True)
            return

        event_type = random.choice(list(ExpeditionEventType))

        await state.update_data(
            active_expedition={
                "staff_id": int(agent.staff_id),
                "event_type": event_type.value,
            }
        )
        await state.set_state(ExpeditionStates.awaiting_choice)

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

        await send_or_edit_dashboard(
            bot=callback.bot,
            player=player,
            session=session,
            text=text,
            reply_markup=builder.as_markup()
        )

    except PlayerNotFoundError:
        await callback.answer("Профиль не найден.", show_alert=True)
    await callback.answer()


@events_router.callback_query(ExpeditionStates.awaiting_choice, F.data.startswith("expedition:choice:"))
async def handle_expedition_choice(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    """
    Обрабатывает выбор игрока в экспедиции и рассчитывает результат с записью в лог.
    """
    if not callback.from_user or not callback.message or not isinstance(callback.message, Message) or not callback.data:
        await callback.answer()
        return

    choice_action = callback.data.split(":")[2]
    data = await state.get_data()
    exp_data = data.get("active_expedition")

    if not exp_data:
        await callback.answer("Экспедиция не найдена.", show_alert=True)
        await state.clear()
        return

    staff_id = int(exp_data["staff_id"])
    event_type_str = str(exp_data["event_type"])
    event_type = ExpeditionEventType(event_type_str)

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

        outcome = calculate_expedition_outcome(agent_skill, event_type, equipment_bonus=0)
        success = bool(outcome["success"])
        reward_mult = float(outcome["reward_multiplier"])
        injury_risk = float(outcome["injury_risk"])

        text = ""
        gold_change = Decimal("0.00")
        injury_info = ""
        log_summary = ""

        # Усталость
        agent.fatigue = min(100, int(agent.fatigue) + 15)

        if choice_action == "fight":
            if success:
                gold_change = Decimal(str(round(150 * reward_mult, 2)))
                text = (
                    f"⚔️ <b>Победил бандитов!</b>\n\n"
                    f"Агент <b>{html.quote(agent_name)}</b> проявил выдающуюся храбрость и разбил разбойников!\n"
                    f"Добыча составила: <b>{gold_change:.2f} gold</b>"
                )
                log_summary = f"Агент {agent_name} победил бандитов в походе (+{gold_change:.1f} gold)"
            else:
                text = (
                    f"💀 <b>Поражение!</b>\n\n"
                    f"Агент <b>{html.quote(agent_name)}</b> не справился с бандитами и был вынужден бежать."
                )
                log_summary = f"Агент {agent_name} проиграл бандитам в походе"
                if random.random() <= injury_risk:
                    is_heavy = random.random() < 0.3
                    conseq = calculate_injury_consequences(is_heavy)
                    blocked_hours = conseq["blocked_hours"]

                    agent.status = StaffStatus.heavy_injured if is_heavy else StaffStatus.light_injured
                    agent.blocked_until = datetime.now(UTC) + timedelta(hours=blocked_hours)

                    injury_info = (
                        f"\n⚠️ <b>Травма:</b> Агент получил <b>{'тяжелую' if is_heavy else 'легкую'} травму</b> "
                        f"и заблокирован на <code>{blocked_hours} ч.</code>!"
                    )
                    log_summary += f" и получил травму (блок на {blocked_hours}ч)"

        elif choice_action == "bribe":
            gold_change = Decimal("-100.00")
            text = (
                f"💰 <b>Выкуп</b>\n\n"
                f"Вы решили не рисковать агентом <b>{html.quote(agent_name)}</b> и заплатили бандитам 100 gold.\n"
                f"Агент благополучно вернулся назад."
            )
            log_summary = f"Откупился от бандитов в экспедиции с {agent_name} (-100 gold)"

        elif choice_action == "trade_accept":
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
                log_summary = f"Выгодно купил эльфийские чертежи с {agent_name} (+200 gold)"
            else:
                text = (
                    f"❌ <b>Обман!</b>\n\n"
                    f"Чертежи оказались фальшивыми. Вы потеряли 150 gold."
                )
                log_summary = f"Агента {agent_name} обманул фальшивый торговец (-150 gold)"
                if random.random() <= injury_risk:
                    agent.status = StaffStatus.light_injured
                    agent.blocked_until = datetime.now(UTC) + timedelta(hours=12)
                    injury_info = f"\n⚠️ Агент расстроился и заблокирован на <code>12 ч.</code>"
                    log_summary += " (агент заблокирован на 12ч)"

        elif choice_action == "trade_decline":
            text = "Вы решили проигнорировать предложение купца. Экспедиция завершена ничем."
            log_summary = f"Агент {agent_name} прошел мимо купца"

        elif choice_action == "altar_activate":
            if success:
                agent.skill = min(100, agent_skill + 5)
                gold_change = Decimal("100.00")
                text = (
                    f"🔮 <b>Мистический успех!</b>\n\n"
                    f"Алтарь озарил агента <b>{html.quote(agent_name)}</b> теплым светом!\n"
                    f"Навык агента повышен: <b>+5</b> (теперь <code>{agent.skill}</code>).\n"
                    f"Найдено золота: <b>+100.00 gold</b>!"
                )
                log_summary = f"Агент {agent_name} активировал алтарь (+5 навык, +100 gold)"
            else:
                agent.skill = max(1, agent_skill - 5)
                text = (
                    f"🔮 <b>Древнее проклятие!</b>\n\n"
                    f"Алтарь вспыхнул темным пламенем.\n"
                    f"Навык агента понижен: <b>-5</b> (теперь <code>{agent.skill}</code>)."
                )
                log_summary = f"Агент {agent_name} проклят алтарем (-5 навык)"

        elif choice_action == "altar_pass":
            text = "Вы решили не трогать алтарь и прошли мимо. Экспедиция завершена."
            log_summary = f"Агент {agent_name} прошел мимо алтаря"

        # Применяем финансы
        if gold_change != 0:
            await player_dal.change_gold(int(player.player_id), gold_change)

        text += injury_info

        # Записываем в лог событий игрока
        await player_dal.log_player_event(
            player_id=int(player.player_id),
            event_type="expedition_event",
            summary=log_summary,
            metadata={"agent_id": staff_id, "action": choice_action, "success": success}
        )

        builder = InlineKeyboardBuilder()

        await send_or_edit_dashboard(
            bot=callback.bot,
            player=player,
            session=session,
            text=text,
            reply_markup=add_global_navigation_footer(builder.as_markup())
        )

    except Exception as e:
        await callback.answer(f"Ошибка завершения экспедиции: {str(e)}", show_alert=True)

    await state.clear()
    await callback.answer()
