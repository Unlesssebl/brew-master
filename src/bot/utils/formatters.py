from typing import cast
from src.database.models import Player

def get_reputation_title(reputation: int) -> str:
    """
    Возвращает фэнтезийный титул пивовара на основе его репутации.
    """
    if reputation > 50:
        return "Почитаемый купец"
    elif reputation > 10:
        return "Уважаемый пивовар"
    elif reputation < -50:
        return "Враг короны"
    elif reputation < -10:
        return "Подозрительный шинкарь"
    else:
        return "Начинающий мастер"

def get_tavern_name(reputation: int) -> str:
    """
    Возвращает название таверны в зависимости от репутации.
    """
    if reputation > 50:
        return "Королевский Кубок"
    elif reputation < -10:
        return "Приют Разбойника"
    else:
        return "Пьяный Gоблин"

def get_profile_text(player: Player) -> str:
    """
    Формирует отформатированный текст профиля игрока.
    """
    level = player.tavern_level.value if player.tavern_level else "garage"
    rep_title = get_reputation_title(cast(int, player.reputation))
    t_name = get_tavern_name(cast(int, player.reputation))
    return (
        f"👑 <b>Профиль пивовара</b>\n"
        f"<code>┌────────────────────────────</code>\n"
        f"🏰 Таверна: <b>«{t_name}»</b>\n"
        f"💰 <b>Золото:</b> <code>{player.gold:.2f} gold</code>\n"
        f"⭐ <b>Репутация:</b> <code>{player.reputation}</code> ({rep_title})\n"
        f"🔥 <b>Влияние:</b> <code>{player.influence}</code>\n"
        f"🍺 <b>Уровень таверны:</b> <code>{level.capitalize()}</code>\n"
        f"<code>└────────────────────────────</code>\n\n"
        f"Используйте кнопки ниже для управления вашей пивной империей!"
    )
