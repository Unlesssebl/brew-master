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

sessions = {}

def get_engine_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Налево", callback_data="act_left"),
         InlineKeyboardButton(text="Направо", callback_data="act_right")]
    ])

@dp.message(Command("multi"))
async def cmd_multi(message: Message):
    # 1. Отправляем верхнее сообщение (Движок/Карта)
    msg_engine = await message.answer("🗺 **ИГРОВОЙ ДВИЖОК**\n\nВы стоите на развилке в подземелье.", reply_markup=get_engine_kb())
    
    # Пытаемся закрепить его (работает только если у бота есть права на закреп)
    try:
        await bot.pin_chat_message(message.chat.id, msg_engine.message_id)
    except TelegramBadRequest:
        pass # Бот может не иметь прав в личке без предварительной настройки
        
    # 2. Отправляем нижнее сообщение (Лог)
    msg_log = await message.answer("📜 **ЛОГ СОБЫТИЙ:**\n- Вы пришли на развилку.")
    
    # 3. Сохраняем связку (верхнее сообщение управляет нижним)
    sessions[msg_engine.message_id] = msg_log.message_id

@dp.callback_query(F.data.startswith("act_"))
async def process_action(cb: CallbackQuery):
    if not cb.message or not isinstance(cb.message, Message):
        return
    log_msg_id = sessions.get(cb.message.message_id)
    if not log_msg_id:
        await cb.answer("Связь потеряна. Напишите /multi", show_alert=True)
        return
        
    action = "налево" if cb.data == "act_left" else "направо"
    log_text = f"📜 **ЛОГ СОБЫТИЙ:**\n- Вы свернули {action}.\n- Вы нашли пару монет."
    
    # Мы обновляем ТОЛЬКО нижний лог, кнопки и верхнее меню не трогаются!
    # Это экономит трафик и создает эффект разделенного интерфейса.
    try:
        await bot.edit_message_text(log_text, chat_id=cb.message.chat.id, message_id=log_msg_id)
        await cb.answer("Действие выполнено!")
    except TelegramBadRequest:
        pass

async def main():
    print("▶ PoC: Разделенный интерфейс (Multi-message Layout)")
    print("Отправьте /multi в боте.")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
