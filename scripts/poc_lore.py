import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import Command

logging.basicConfig(level=logging.INFO)
BOT_TOKEN = "8891264422:AAHhq1WEI2DwuKDb-eTxeOqmYeoGt3qHnWE"
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(Command("lore"))
async def cmd_lore(message: Message):
    text = (
        "📜 Вы нашли древний манускрипт.\n\n"
        "<blockquote expandable>"
        "<b>Легенда о Темном Эле</b>\n\n"
        "Давным-давно, когда гоблины еще не контролировали Черный Рынок, великий пивовар создал рецепт Темного Эля. "
        "Говорят, что один глоток этого напитка заставлял забыть о налогах на целую неделю. "
        "Король послал инквизицию, чтобы уничтожить рецепт, но пивовар спрятал его в подземельях под своей таверной. "
        "С тех пор многие искатели приключений спускались туда, но возвращались лишь те, кто приносил с собой воду и солод. "
        "Вам предстоит разгадать загадку алхимического котла и найти тайную комнату, где хранится древний фолиант..."
        "</blockquote>\n\n"
        "<i>Нажмите на плашку выше, чтобы прочитать Легенду полностью.</i>"
    )
    
    # Для blockquote expandable обязательно нужно использовать HTML parse_mode
    await message.answer(text, parse_mode="HTML")

async def main():
    print("▶ PoC: Скрытый лор (blockquote expandable)")
    print("Отправьте /lore в боте.")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
