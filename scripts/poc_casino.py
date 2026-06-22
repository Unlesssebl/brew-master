import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import Command

logging.basicConfig(level=logging.INFO)
BOT_TOKEN = "8891264422:AAHhq1WEI2DwuKDb-eTxeOqmYeoGt3qHnWE"
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

EFFECT_PARTY = "5046509860389126442" # 🎉

@dp.message(Command("casino"))
async def cmd_casino(message: Message):
    await message.answer("🎰 Добро пожаловать в Подпольное Казино!\nДергаем ручку...")
    dice = await bot.send_dice(chat_id=message.chat.id, emoji="🎰")
    
    # Ждем пока крутится рулетка Telegram (примерно 2 секунды)
    await asyncio.sleep(2.0)
    
    val = dice.dice.value
    # Telegram API возвращает значения от 1 до 64 для слотов
    # 64 - это джекпот (три семерки)
    if val == 64:
        text = "🎯 **ДЖЕКПОТ (64)! Три семерки!**\nВы выиграли Легендарный Рецепт!"
        await message.answer(text, reply_to_message_id=dice.message_id, message_effect_id=EFFECT_PARTY)
    elif val in [1, 22, 43]: # Три ягоды, лимона и т.д. (одинаковые символы)
        text = f"💰 **Выигрыш ({val})! Три одинаковых символа!**\nВаша ставка утроена."
        await message.answer(text, reply_to_message_id=dice.message_id)
    else:
        text = f"❌ **Проигрыш ({val}).**\nПовезет в следующий раз!"
        await message.answer(text, reply_to_message_id=dice.message_id)

async def main():
    print("▶ PoC: Однорукий бандит (Казино)")
    print("Отправьте /casino в боте.")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
