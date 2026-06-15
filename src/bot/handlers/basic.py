from aiogram import F, Router, html
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.keyboards import get_main_menu
from src.database.dal import PlayerDAL, PlayerNotFoundError

basic_router = Router()


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
        await player_dal.get_player(tg_id)
        text = (
            f"Привет, {html.quote(message.from_user.full_name)}! Рады видеть тебя снова в Brew Master.\n"
            f"Используй меню ниже или напиши /brew для варки пива."
        )
    except PlayerNotFoundError:
        await player_dal.create_player(tg_id)
        text = (
            f"Приветствуем тебя, {html.quote(message.from_user.full_name)}, в Brew Master!\n"
            f"Мы создали для тебя профиль пивовара и выдали стартовый капитал: <b>1000.00 gold</b> 💰\n\n"
            f"Используй меню ниже, чтобы начать приключение!"
        )

    await message.answer(text, parse_mode="HTML", reply_markup=get_main_menu())


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
    except PlayerNotFoundError:
        await message.answer(
            "Вы не зарегистрированы в игре. Напишите /start, чтобы начать приключение!",
            parse_mode="HTML",
        )
        return

    text = (
        f"👑 <b>Профиль пивовара</b>\n"
        f"<code>┌────────────────────────────</code>\n"
        f"💰 <b>Золото:</b> <code>{player.gold:.2f} gold</code>\n"
        f"⭐ <b>Репутация:</b> <code>{player.reputation}</code>\n"
        f"🔥 <b>Влияние:</b> <code>{player.influence}</code>\n"
        f"🍺 <b>Уровень таверны:</b> <code>{player.tavern_level.value.capitalize()}</code>\n"
        f"<code>└────────────────────────────</code>"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=get_main_menu())

