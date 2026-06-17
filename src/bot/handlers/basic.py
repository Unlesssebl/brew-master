from typing import cast
from aiogram import Router, html
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.keyboards.inline import get_main_menu_keyboard, get_tutorial_start_keyboard
from src.bot.states import TutorialStates
from src.bot.utils.formatters import get_profile_text
from src.database.dal import PlayerDAL, PlayerNotFoundError

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

    if player.tutorial_step < 3:
        if state is not None:
            await state.set_state(TutorialStates.first_brew)
        await message.answer(
            f"Привет, {html.quote(message.from_user.full_name)}! Добро пожаловать в дедовский гараж. 🏭\n\n"
            f"У нас есть старый чан и немного ингредиентов. Прежде чем выходить на большой рынок, "
            f"давай сварим первую партию.\n\n"
            f"Нажми кнопку ниже, чтобы запустить тестовую варку базового эля (25/25/25/25).",
            reply_markup=get_tutorial_start_keyboard(),
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
    await message.answer(text, parse_mode="HTML", reply_markup=get_main_menu_keyboard(alerts))


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
        await message.answer(text, parse_mode="HTML", reply_markup=get_main_menu_keyboard(alerts))
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
        await message.answer(text, parse_mode="HTML", reply_markup=get_main_menu_keyboard(alerts))
    except PlayerNotFoundError:
        await message.answer(
            "Вы не зарегистрированы в игре. Напишите /start, чтобы начать приключение!",
            parse_mode="HTML",
        )
