from aiogram import F, Router, html
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.utils.keyboards import get_main_menu_keyboard
from src.database.dal import PlayerDAL, PlayerNotFoundError

basic_router = Router()


def get_profile_text(player) -> str:
    """
    Формирует текст профиля игрока.
    """
    level = player.tavern_level.value if player.tavern_level else "garage"
    return (
        f"👑 <b>Профиль пивовара</b>\n"
        f"<code>┌────────────────────────────</code>\n"
        f"💰 <b>Золото:</b> <code>{player.gold:.2f} gold</code>\n"
        f"⭐ <b>Репутация:</b> <code>{player.reputation}</code>\n"
        f"🔥 <b>Влияние:</b> <code>{player.influence}</code>\n"
        f"🍺 <b>Уровень таверны:</b> <code>{level.capitalize()}</code>\n"
        f"<code>└────────────────────────────</code>\n\n"
        f"Используйте кнопки ниже для управления вашей пивной империей!"
    )


@basic_router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession) -> None:
    """
    Хэндлер команды /start.
    Проверяет существование пользователя. Если его нет, регистрирует и начисляет стартовое золото.
    """
    if not message.from_user:
        return

    tg_id = message.from_user.id
    player_dal = PlayerDAL(session)

    try:
        player = await player_dal.get_player(tg_id)
        text = (
            f"Привет, {html.quote(message.from_user.full_name)}! Рады видеть тебя снова в Brew Master.\n\n"
            + get_profile_text(player)
        )
    except PlayerNotFoundError:
        player = await player_dal.create_player(tg_id)
        text = (
            f"Приветствуем тебя, {html.quote(message.from_user.full_name)}, в Brew Master!\n"
            f"Мы создали для тебя профиль пивовара и выдали стартовый капитал: <b>1000.00 gold</b> 💰\n\n"
            + get_profile_text(player)
        )

    await message.answer(text, parse_mode="HTML", reply_markup=get_main_menu_keyboard())


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
        await message.answer(text, parse_mode="HTML", reply_markup=get_main_menu_keyboard())
    except PlayerNotFoundError:
        await message.answer(
            "Вы не зарегистрированы в игре. Напишите /start, чтобы начать приключение!",
            parse_mode="HTML",
        )


@basic_router.message(Command("profile"))
@basic_router.message(F.text == "👑 Профиль")
async def cmd_profile(message: Message, session: AsyncSession) -> None:
    """
    Хэндлер команды /profile и кнопки "👑 Профиль".
    Выводит текущую статистику игрока в отформатированном виде.
    """
    if not message.from_user:
        return

    tg_id = message.from_user.id
    player_dal = PlayerDAL(session)

    try:
        player = await player_dal.get_player(tg_id)
        text = get_profile_text(player)
        await message.answer(text, parse_mode="HTML", reply_markup=get_main_menu_keyboard())
    except PlayerNotFoundError:
        await message.answer(
            "Вы не зарегистрированы в игре. Напишите /start, чтобы начать приключение!",
            parse_mode="HTML",
        )

