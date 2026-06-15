from src.database.models import Player


def get_profile_text(player: Player) -> str:
    """
    Формирует отформатированный текст профиля игрока.
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
