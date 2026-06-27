import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest

logging.basicConfig(level=logging.INFO)
from load_env import BOT_TOKEN
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

from typing import Any

# Имитация быстрого In-Memory хранилища (В продакшене это Redis)
state: dict[str, Any] = {
    "clicks": 0,
    "last_rendered_clicks": 0,
    "chat_id": None,
    "msg_id": None
}

def get_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚔️ АТАКОВАТЬ (СПАМЬ!)", callback_data="hit", **{"style": "danger"})]
    ])

# Фоновый воркер, который обрабатывает "очередь"
async def debouncer_worker():
    while True:
        await asyncio.sleep(1.0) # Проверяем стейт 1 раз в секунду
        
        if state["msg_id"] and state["clicks"] != state["last_rendered_clicks"]:
            # Состояние изменилось! Рендерим ОДИН раз за такт.
            state["last_rendered_clicks"] = state["clicks"]
            text = f"🔥 **РЕЙД НА БОССА**\nСчетчик урона: **{state['clicks']}**\n\nДаже если вы кликнули 50 раз за секунду, API Telegram получил только 1 запрос на обновление этого сообщения."
            
            try:
                await bot.edit_message_text(
                    text, 
                    chat_id=state["chat_id"], 
                    message_id=state["msg_id"], 
                    reply_markup=get_kb(),
                    parse_mode="Markdown"
                )
            except TelegramBadRequest:
                pass

@dp.message(Command("debouncing"))
async def cmd_debouncing(message: Message):
    state["clicks"] = 0
    state["last_rendered_clicks"] = 0
    state["chat_id"] = message.chat.id
    
    text = "🔥 **РЕЙД НА БОССА**\nСчетчик урона: **0**\n\nСпамьте кнопку как можно быстрее!"
    sent = await message.answer(text, reply_markup=get_kb(), parse_mode="Markdown")
    state["msg_id"] = sent.message_id

@dp.callback_query(F.data == "hit")
async def process_hit(cb: CallbackQuery):
    # Мгновенно обновляем стейт в памяти, НЕ отправляя запрос в Telegram (O(1) операция)
    state["clicks"] += 1
    
    # Отвечаем на callback, чтобы кнопка не зависала с часиками
    try:
        await cb.answer(f"Урон нанесен! ({state['clicks']})", show_alert=False)
    except TelegramBadRequest:
        pass

async def main():
    print("▶ PoC: Система очередей (Debouncing)")
    print("Отправьте /debouncing в боте.")
    await bot.delete_webhook(drop_pending_updates=True)
    
    # Запускаем фоновый воркер вместе с поллингом
    asyncio.create_task(debouncer_worker())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
