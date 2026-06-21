import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, MessageReactionUpdated
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest

logging.basicConfig(level=logging.INFO)

# Используем токен из предыдущего скрипта
BOT_TOKEN = "8891264422:AAHhq1WEI2DwuKDb-eTxeOqmYeoGt3qHnWE" 
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Глобальное хранилище состояния боссов (в проде это будет Redis)
# message_id -> {"hp": 500, "max_hp": 500, "status": "alive"}
boss_sessions = {}

def generate_progress_bar(current, total, length=15):
    """Генератор псевдографического прогресс-бара здоровья."""
    percent = max(0, min(1, current / total))
    filled = int(percent * length)
    empty = length - filled
    return "🟥" * filled + "⬛" * empty

def render_boss(hp, max_hp, status="alive"):
    """Рендерит текстовый интерфейс босса."""
    bar = generate_progress_bar(hp, max_hp)
    if status == "alive":
        return (
            f"🐲 **ДРЕВНИЙ ДРАКОН-НАЛОГОВИК**\n"
            f"*«Я пришел за вашим золотом, трактирщик!»*\n\n"
            f"❤️ Здоровье: {hp}/{max_hp}\n"
            f"[{bar}]\n\n"
            f"👇 **СТАВЬТЕ РЕАКЦИИ НА ЭТО СООБЩЕНИЕ, ЧТОБЫ АТАКОВАТЬ!**\n"
            f"🔥 — Огненный шар (-15 HP)\n"
            f"⚡ — Удар молнии (-25 HP)\n"
            f"🧊 — Ледяное копье (-10 HP)\n"
            f"*(Вы можете ставить реакцию, убирать ее и ставить заново, чтобы спамить атаки!)*"
        )
    else:
        return (
            f"💀 **ДРАКОН ПОВЕРЖЕН!**\n"
            f"*«Мое... мое золото...»*\n\n"
            f"❤️ Здоровье: 0/{max_hp}\n"
            f"[{generate_progress_bar(0, max_hp)}]\n\n"
            f"🎉 **ПОБЕДА!** Вы отстояли свою таверну.\n"
            f"Награда: 💰 5000 золота добавлено в казну гильдии."
        )

@dp.message(Command("boss"))
async def cmd_boss(message: Message):
    max_hp = 250  # HP для теста, чтобы не закликивать слишком долго
    text = render_boss(max_hp, max_hp, "alive")
    
    # Отправляем сообщение
    sent_msg = await message.answer(text, parse_mode="Markdown")
    
    # Сохраняем стейт, используя ID сообщения как ключ
    boss_sessions[sent_msg.message_id] = {
        "hp": max_hp,
        "max_hp": max_hp,
        "status": "alive"
    }

@dp.message_reaction()
async def reaction_handler(reaction: MessageReactionUpdated):
    """Слушатель обновлений реакций на сообщения."""
    boss = boss_sessions.get(reaction.message_id)
    if not boss or boss["status"] == "dead":
        return

    # Извлекаем только эмодзи-реакции (игнорируем Custom Emojis для этого PoC)
    old_emojis = {r.emoji for r in reaction.old_reaction if r.type == "emoji"}
    new_emojis = {r.emoji for r in reaction.new_reaction if r.type == "emoji"}
    
    # Нас интересуют только добавленные (НОВЫЕ) реакции.
    # Если игрок снял реакцию - урон не наносится.
    added_emojis = new_emojis - old_emojis

    damage = 0
    for em in added_emojis:
        if em == "🔥":
            damage += 15
        elif em == "⚡":
            damage += 25
        elif em == "🧊":
            damage += 10
        elif em == "🌭": # Пасхалка
            damage += 100
        else:
            damage += 1 # Любая другая неопознанная реакция наносит 1 урона

    if damage > 0:
        boss["hp"] -= damage
        
        # Проверяем смерть босса
        if boss["hp"] <= 0:
            boss["hp"] = 0
            boss["status"] = "dead"
            
        text = render_boss(boss["hp"], boss["max_hp"], boss["status"])
        
        try:
            # Обновляем сообщение (рендерим новый HP-бар)
            await bot.edit_message_text(
                text=text,
                chat_id=reaction.chat.id,
                message_id=reaction.message_id,
                parse_mode="Markdown"
            )
        except TelegramBadRequest as e:
            # Игнорируем ошибку "message is not modified",
            # которая может возникнуть при очень быстром спаме одинаковых реакций
            if "message is not modified" not in e.message.lower():
                logging.error(f"Failed to update boss: {e}")

async def main():
    print("Запуск PoC Битвы с Боссом на Реакциях...")
    await bot.delete_webhook(drop_pending_updates=True)
    # В aiogram 3.x update types резолвятся автоматически (благодаря @dp.message_reaction), 
    # но можно указать явно для надежности.
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

if __name__ == "__main__":
    asyncio.run(main())
