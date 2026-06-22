import asyncio
import logging
import random
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest

logging.basicConfig(level=logging.INFO)
BOT_TOKEN = "8891264422:AAHhq1WEI2DwuKDb-eTxeOqmYeoGt3qHnWE"
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

sessions = {}

def get_qte_kb(show_qte=False, game_over=False):
    if game_over:
        return InlineKeyboardMarkup(inline_keyboard=[])
    if show_qte:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔥 СБРОСИТЬ ДАВЛЕНИЕ!", callback_data="qte_hit", **{"style": "danger"})]
        ])
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏳ Варка идет...", callback_data="ignore", **{"style": "primary"})]
    ])

async def qte_loop(chat_id, msg_id, session):
    qte_trigger_time = random.randint(3, 7) # QTE появится на 3-7 секунде
    
    for sec in range(1, 11): # Всего варим 10 секунд
        if session["status"] != "brewing":
            break
            
        if sec == qte_trigger_time:
            session["qte_active"] = True
            text = "🍲 **КОТЕЛ ЗАКИПАЕТ!**\nКритическое давление! Быстро сбросьте его!"
            try:
                await bot.edit_message_text(text, chat_id=chat_id, message_id=msg_id, reply_markup=get_qte_kb(show_qte=True))
            except TelegramBadRequest: pass
            
            # Ждем 3 секунды на реакцию
            await asyncio.sleep(3.0)
            
            if session["qte_active"]: # Не успел нажать
                session["status"] = "failed"
                text = "💥 **ВЗРЫВ!**\nВы не успели сбросить давление. Варево испорчено."
                try:
                    await bot.edit_message_text(text, chat_id=chat_id, message_id=msg_id, reply_markup=get_qte_kb(game_over=True))
                except TelegramBadRequest: pass
                break
        else:
            session["qte_active"] = False
            text = f"🍲 **ВАРКА ЗЕЛЬЯ ({sec}/10)**\nБуль-буль-буль..."
            try:
                await bot.edit_message_text(text, chat_id=chat_id, message_id=msg_id, reply_markup=get_qte_kb(show_qte=False))
            except TelegramBadRequest: pass
            await asyncio.sleep(1.0)
            
    if session["status"] == "brewing":
        session["status"] = "success"
        text = "✨ **ВАРКА ЗАВЕРШЕНА!**\nВы сварили отличное зелье."
        try:
            await bot.edit_message_text(text, chat_id=chat_id, message_id=msg_id, reply_markup=get_qte_kb(game_over=True))
        except TelegramBadRequest: pass

@dp.message(Command("qte"))
async def cmd_qte(message: Message):
    session = {"status": "brewing", "qte_active": False}
    sent = await message.answer("🍲 **ВАРКА ЗЕЛЬЯ (0/10)**\nБуль-буль-буль...", reply_markup=get_qte_kb())
    sessions[sent.message_id] = session
    asyncio.create_task(qte_loop(message.chat.id, sent.message_id, session))

@dp.callback_query(F.data == "qte_hit")
async def process_qte(cb: CallbackQuery):
    session = sessions.get(cb.message.message_id)
    if not session or not session.get("qte_active"):
        await cb.answer("Слишком поздно (или рано)!", show_alert=True)
        return
        
    session["qte_active"] = False
    session["status"] = "perfect" # Переводим в особый статус
    text = "🌟 **ИДЕАЛЬНАЯ ВАРКА!**\nВы вовремя сбросили давление. Зелье будет Шедевральным!"
    
    try:
        await cb.message.edit_text(text, reply_markup=get_qte_kb(game_over=True))
        await cb.answer("Отличная реакция!", show_alert=False)
    except TelegramBadRequest:
        pass

@dp.callback_query(F.data == "ignore")
async def process_ignore(cb: CallbackQuery):
    await cb.answer("Ждите...", show_alert=False)

async def main():
    print("▶ PoC: Активный крафт (QTE)")
    print("Отправьте /qte в боте.")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
