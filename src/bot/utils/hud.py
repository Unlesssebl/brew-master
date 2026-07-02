import logging

from typing import cast
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from src.database.models import Player, Resource, Batch
from src.database.dal import PlayerDAL

logger = logging.getLogger(__name__)


async def send_or_edit_dashboard(
    bot: Bot | None,
    player: Player,
    session: AsyncSession,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    force_new: bool = False,
    has_alerts: bool = False,
    reply_keyboard: ReplyKeyboardMarkup | None = None,
) -> None:
    """
    Отправляет новое или редактирует существующее сообщение дашборда с интегрированным HUD.
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
    alert_sign = " 🔴" if has_alerts else ""
    suspicion = getattr(player, 'suspicion', 0)
    
    hud_text = (
        f"<blockquote expandable><b>⚜️ ИНФОРМАЦИОННАЯ ПАНЕЛЬ ПИВОВАРА{alert_sign} ⚜️</b>\n"
        f"💰 <b>{player.gold:.2f}g</b> | 💎 <b>{player.prestige_crystals}</b> | 👑 <b>{player.influence}</b> вл. | ⭐ <b>{reputation_sign}{player.reputation}</b> реп. | 🕵️ <b>{suspicion}%</b> под.\n"
        f"🌾 <b>{resources.get('malt', 0):.1f}</b> | 💧 <b>{resources.get('water', 0):.1f}</b> | 🌿 <b>{resources.get('hops', 0):.1f}</b> | 🍞 <b>{resources.get('yeast', 0):.1f}</b>\n"
        f"⏳ <b>Активных варок в погребе:</b> <code>{active_brews}</code></blockquote>\n\n"
        f"{text}"
    )

    chat_id = cast(int, player.tg_id)

    # Если передана Reply Keyboard — обновить якорное сообщение.
    # Удаляем старый якорь, отправляем новый и сохраняем его ID.
    # Reply Keyboard в Telegram живёт независимо от сообщений —
    # она остаётся видимой даже после удаления сообщения, которое её установило.
    if reply_keyboard:
        if player.nav_message_id:
            try:
                await bot.delete_message(chat_id=chat_id, message_id=cast(int, player.nav_message_id))
            except Exception:
                pass
            player.nav_message_id = None

        try:
            nav_msg = await bot.send_message(
                chat_id=chat_id,
                text="🗺️",
                reply_markup=reply_keyboard
            )
            player.nav_message_id = nav_msg.message_id
            session.add(player)
            await session.flush()
        except Exception as e:
            logger.debug(f"Failed to apply reply keyboard: {e}")

    if force_new and player.hud_message_id:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=cast(int, player.hud_message_id))
        except Exception as e:
            logger.debug(f"Failed to delete message: {e}")
        player.hud_message_id = None

    if player.hud_message_id:
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=cast(int, player.hud_message_id),
                text=hud_text,
                reply_markup=reply_markup,
                parse_mode="HTML"
            )
            return
        except TelegramBadRequest as e:
            if "message is not modified" in str(e).lower():
                return
            logger.warning(f"TelegramBadRequest in edit_message_text: {e}")
            # Если сообщение удалено пользователем или возникла другая ошибка API, сбросим ID
            player.hud_message_id = None
        except Exception as e:
            logger.exception("Error editing dashboard message")
            player.hud_message_id = None
            
    # Если сообщения нет или принудительно создаем новое
    try:
        new_msg = await bot.send_message(
            chat_id=chat_id,
            text=hud_text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
        player.hud_message_id = new_msg.message_id
        session.add(player)
        await session.flush()
    except Exception as e:
        logger.exception("Error sending new dashboard message")

