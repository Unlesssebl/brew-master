from aiogram import Router, html
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

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
            f"Используй /profile для просмотра статистики или /brew для варки пива."
        )
    except PlayerNotFoundError:
        await player_dal.create_player(tg_id)
        text = (
            f"Приветствуем тебя, {html.quote(message.from_user.full_name)}, в Brew Master!\n"
            f"Мы создали для тебя профиль пивовара и выдали стартовый капитал: <b>1000.00 gold</b> 💰\n\n"
            f"Напиши /profile, чтобы посмотреть свою статистику, или /brew, чтобы сварить первую партию пива!"
        )

    await message.answer(text, parse_mode="HTML")


@basic_router.message(Command("profile"))
async def cmd_profile(message: Message, session: AsyncSession) -> None:
    """
    Хэндлер команды /profile.
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
        f"<b>👑 Профиль пивовара</b>\n\n"
        f"💰 <b>Золото:</b> {player.gold:.2f} gold\n"
        f"⭐ <b>Репутация:</b> {player.reputation}\n"
        f"🔥 <b>Влияние:</b> {player.influence}\n"
        f"🍺 <b>Уровень таверны:</b> {player.tavern_level.value.capitalize()}\n"
    )
    await message.answer(text, parse_mode="HTML")
