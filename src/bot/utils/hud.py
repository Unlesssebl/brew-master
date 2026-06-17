from typing import cast
from aiogram import Bot
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from src.database.models import Player, Resource, Batch
from src.database.dal import PlayerDAL


async def update_hud(bot: Bot | None, player: Player, session: AsyncSession) -> None:
    """
    Обновляет закрепленное HUD-сообщение для игрока.
    """
    if bot is None:
        return

    player_dal = PlayerDAL(session)
    resources = await player_dal.get_resources(cast(int, player.player_id))
    
    # Считаем активные (созревающие) варки
    stmt_active = select(func.count(Batch.batch_id)).where(
        Batch.player_id == cast(int, player.player_id),
        Batch.is_completed.is_(False)
    )
    res_active = await session.execute(stmt_active)
    active_brews = res_active.scalar_one_or_none() or 0

    reputation_sign = "+" if cast(int, player.reputation) >= 0 else ""
    
    hud_text = (
        f"<b>⚜️ ИНФОРМАЦИОННАЯ ПАНЕЛЬ ПИВОВАРА ⚜️</b>\n"
        f"<code>┌──────────────────────────────────────────┐</code>\n"
        f"💰 <b>{player.gold:.2f}g</b> | 💎 <b>{player.prestige_crystals}</b> | 👑 <b>{player.influence}</b> вл. | ⭐ <b>{reputation_sign}{player.reputation}</b> реп.\n"
        f"🌾 <b>{resources.get('malt', 0):.1f}</b> | 💧 <b>{resources.get('water', 0):.1f}</b> | 🌿 <b>{resources.get('hops', 0):.1f}</b> | 🍞 <b>{resources.get('yeast', 0):.1f}</b>\n"
        f"⏳ <b>Активных варок в погребе:</b> <code>{active_brews}</code>\n"
        f"<code>└──────────────────────────────────────────┘</code>"
    )

    chat_id = cast(int, player.tg_id)
    
    if player.hud_message_id:
        try:
            # Пытаемся отредактировать существующее закрепленное сообщение
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=cast(int, player.hud_message_id),
                text=hud_text,
                parse_mode="HTML"
            )
            return
        except Exception:
            # Если сообщение было удалено или возникла другая ошибка, снимем ID
            player.hud_message_id = None
            
    # Если сообщения нет, отправляем новое, закрепляем и сохраняем ID
    try:
        new_msg = await bot.send_message(
            chat_id=chat_id,
            text=hud_text,
            parse_mode="HTML",
            disable_notification=True
        )
        player.hud_message_id = new_msg.message_id
        # Пытаемся закрепить
        try:
            await bot.pin_chat_message(
                chat_id=chat_id,
                message_id=new_msg.message_id,
                disable_notification=True
            )
        except Exception:
            pass
        session.add(player)
        await session.flush()
    except Exception:
        pass
