from typing import cast
from aiogram import F, Router, html
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, InlineKeyboardButton, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.keyboards.inline import (
    get_main_menu_keyboard,
    get_tutorial_start_keyboard,
    get_welcome_keyboard,
    get_nav_reply_keyboard,
)
from src.bot.states import TutorialStates
from src.bot.utils.formatters import get_profile_text
from src.bot.utils.hud import send_or_edit_dashboard
from src.database.dal import PlayerDAL, PlayerNotFoundError

# Импорт хэндлеров локаций для Reply Keyboard навигации
from src.bot.handlers.buildings import show_tavern
from src.bot.handlers.brewery_hall import show_brewery_hall
from src.bot.handlers.menu import show_inventory
from src.bot.handlers.market import show_market
from src.bot.handlers.slums import show_slums
from src.bot.handlers.events import show_expeditions_screen

basic_router = Router()


@basic_router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession, state: FSMContext | None = None) -> None:
    """
    Хэндлер команды /start. Направляет новичков в обучение, а опытных игроков в меню.
    """
    if not message.from_user:
        return

    tg_id = message.from_user.id
    player_dal = PlayerDAL(session)

    try:
        player = await player_dal.get_player(tg_id)
    except PlayerNotFoundError:
        player = await player_dal.create_player(tg_id)

    if player.tutorial_step == 0:
        await message.answer(
            f"📜 <b>Добро пожаловать в Brew Master!</b>\n\n"
            f"<i>Старая вывеска скрипит на ветру, а тяжелая дубовая дверь приглашает внутрь... "
            f"Вы унаследовали эту заброшенную таверну, и теперь ваша цель — вернуть ей былую славу, "
            f"стать величайшим мастером-пивоваром и покорить рынки всех фракций Города.</i>\n\n"
            f"Готов ли ты начать свой путь, {html.quote(message.from_user.full_name)}?",
            parse_mode="HTML",
            reply_markup=get_welcome_keyboard(),
        )
        return
    elif player.tutorial_step == 1:
        if state is not None:
            await state.set_state(TutorialStates.first_collect)
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="🟢 Собрать пиво", callback_data="inventory:collect_ready"))
        await send_or_edit_dashboard(
            bot=message.bot,
            player=player,
            session=session,
            text="🔥 <b>Твоя первая варка завершена!</b>\n\n"
                 "Погреб наполняется ароматом свежего эля. "
                 "Следующий шаг — перелей пиво в бочки и спусти на склад.",
            reply_markup=builder.as_markup(),
            force_new=True,
        )
        return
    elif player.tutorial_step == 2:
        if state is not None:
            await state.set_state(TutorialStates.first_sell)
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="⚖️ Торговая площадь", callback_data="screen:market"))
        await send_or_edit_dashboard(
            bot=message.bot,
            player=player,
            session=session,
            text="🏺 <b>Пиво на складе!</b>\n\n"
                 "Пора выходить на рынок. Отправляйся на Торговую площадь и продай свою первую партию фракциям, "
                 "чтобы заработать золото и репутацию.",
            reply_markup=builder.as_markup(),
            force_new=True,
        )
        return

    if state is not None:
        await state.clear()
    text = (
        f"С возвращением на завод, {html.quote(message.from_user.full_name)}!\n\n"
        + get_profile_text(player)
    )
    try:
        alerts = await player_dal.get_alerts_summary(cast(int, player.player_id))
    except TypeError:
        alerts = {}

    await send_or_edit_dashboard(
        bot=message.bot,
        player=player,
        session=session,
        text=text,
        reply_markup=get_main_menu_keyboard(alerts),
        force_new=True,
        reply_keyboard=get_nav_reply_keyboard(),
    )


@basic_router.callback_query(F.data == "tutorial:start")
async def process_tutorial_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Обработчик кнопки 'Войти в таверну' на приветственном экране.
    Переводит игрока в состояние обучения и предлагает первую варку.
    """
    if not callback.from_user or not callback.message or not isinstance(callback.message, Message):
        await callback.answer()
        return

    tg_id = callback.from_user.id
    player_dal = PlayerDAL(session)

    try:
        player = await player_dal.get_player(tg_id)
    except PlayerNotFoundError:
        await callback.answer("Профиль не найден. Напишите /start", show_alert=True)
        return

    if player.tutorial_step > 0:
        await callback.answer("Обучение уже начато или пройдено.", show_alert=True)
        return

    await state.set_state(TutorialStates.first_brew)
    await callback.message.edit_text(
        f"🏰 <b>Твоя старая таверна</b>\n\n"
        f"Твой путь начинается с малого: в подвале стоит старый медный чан и пылится мешок ячменя. "
        f"Прежде чем заявлять о себе в гильдии, давай сварим первую пробную партию эля.\n\n"
        f"Нажми кнопку ниже, чтобы разжечь огонь и запустить тестовую варку (25/25/25/25).",
        parse_mode="HTML",
        reply_markup=get_tutorial_start_keyboard(),
    )
    await callback.answer()


@basic_router.message(Command("menu"))
async def cmd_menu(message: Message, session: AsyncSession) -> None:
    """
    Хэндлер команды /menu. Отображает профиль и главное меню.
    """
    if not message.from_user:
        return

    tg_id = message.from_user.id
    player_dal = PlayerDAL(session)

    try:
        player = await player_dal.get_player(tg_id)
        text = get_profile_text(player)
        try:
            alerts = await player_dal.get_alerts_summary(cast(int, player.player_id))
        except TypeError:
            alerts = {}
        await send_or_edit_dashboard(
            bot=message.bot,
            player=player,
            session=session,
            text=text,
            reply_markup=get_main_menu_keyboard(alerts),
            force_new=True,
            reply_keyboard=get_nav_reply_keyboard(),
        )
    except PlayerNotFoundError:
        await message.answer(
            "Вы не зарегистрированы в игре. Напишите /start, чтобы начать приключение!",
            parse_mode="HTML",
        )


@basic_router.message(Command("profile"))
async def cmd_profile(message: Message, session: AsyncSession) -> None:
    """
    Хэндлер команды /profile. Отображает профиль пивовара.
    """
    if not message.from_user:
        return

    tg_id = message.from_user.id
    player_dal = PlayerDAL(session)

    try:
        player = await player_dal.get_player(tg_id)
        text = get_profile_text(player)
        try:
            alerts = await player_dal.get_alerts_summary(cast(int, player.player_id))
        except TypeError:
            alerts = {}
        await send_or_edit_dashboard(
            bot=message.bot,
            player=player,
            session=session,
            text=text,
            reply_markup=get_main_menu_keyboard(alerts),
            force_new=True,
            reply_keyboard=get_nav_reply_keyboard(),
        )
    except PlayerNotFoundError:
        await message.answer(
            "Вы не зарегистрированы в игре. Напишите /start, чтобы начать приключение!",
            parse_mode="HTML",
        )


def make_mock_callback(message: Message, data: str) -> CallbackQuery:
    async def dummy_answer(*args, **kwargs):
        pass
    
    cb = CallbackQuery(
        id="mock",
        from_user=message.from_user,
        chat_instance="mock",
        message=message,
        data=data
    )
    cb.answer = dummy_answer
    return cb


@basic_router.message(F.text == "🍻 Моя Таверна")
async def handle_nav_tavern(message: Message, session: AsyncSession) -> None:
    player_dal = PlayerDAL(session)
    try:
        player = await player_dal.get_player(message.from_user.id)
        if player.tutorial_step < 3:
            return
    except Exception:
        return

    try:
        await message.delete()
    except Exception:
        pass
    cb = make_mock_callback(message, "screen:tavern")
    await show_tavern(cb, session)


@basic_router.message(F.text == "🔥 Варочный Зал")
async def handle_nav_brewery_hall(message: Message, session: AsyncSession) -> None:
    player_dal = PlayerDAL(session)
    try:
        player = await player_dal.get_player(message.from_user.id)
        if player.tutorial_step < 3:
            return
    except Exception:
        return

    try:
        await message.delete()
    except Exception:
        pass
    cb = make_mock_callback(message, "screen:brewery_hall")
    await show_brewery_hall(cb, session)


@basic_router.message(F.text == "🏺 Тёмный Погреб")
async def handle_nav_inventory(message: Message, session: AsyncSession) -> None:
    player_dal = PlayerDAL(session)
    try:
        player = await player_dal.get_player(message.from_user.id)
        if player.tutorial_step < 3:
            return
    except Exception:
        return

    try:
        await message.delete()
    except Exception:
        pass
    cb = make_mock_callback(message, "screen:inventory")
    await show_inventory(cb, session)


@basic_router.message(F.text == "⚖️ Торговая площадь")
async def handle_nav_market(message: Message, session: AsyncSession) -> None:
    player_dal = PlayerDAL(session)
    try:
        player = await player_dal.get_player(message.from_user.id)
        if player.tutorial_step < 3:
            return
    except Exception:
        return

    try:
        await message.delete()
    except Exception:
        pass
    cb = make_mock_callback(message, "screen:market")
    await show_market(cb, session)


@basic_router.message(F.text == "🌑 Тёмный переулок")
async def handle_nav_slums(message: Message, session: AsyncSession) -> None:
    player_dal = PlayerDAL(session)
    try:
        player = await player_dal.get_player(message.from_user.id)
        if player.tutorial_step < 3:
            return
    except Exception:
        return

    try:
        await message.delete()
    except Exception:
        pass
    cb = make_mock_callback(message, "screen:slums")
    await show_slums(cb, session)


@basic_router.message(F.text == "🗺️ Ворота")
async def handle_nav_expeditions(message: Message, state: FSMContext, session: AsyncSession) -> None:
    player_dal = PlayerDAL(session)
    try:
        player = await player_dal.get_player(message.from_user.id)
        if player.tutorial_step < 3:
            return
    except Exception:
        return

    try:
        await message.delete()
    except Exception:
        pass
    cb = make_mock_callback(message, "screen:expeditions")
    await show_expeditions_screen(cb, state, session)
