import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest

logging.basicConfig(level=logging.INFO)
BOT_TOKEN = "8891264422:AAHhq1WEI2DwuKDb-eTxeOqmYeoGt3qHnWE"
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

auction = {
    "price": 100,
    "leader": None,
    "time_left": 60,
    "active": False,
    "msg_id": None,
    "chat_id": None
}

def get_auction_kb(active):
    if not active:
        return InlineKeyboardMarkup(inline_keyboard=[])
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"💰 Перебить ставку: {auction['price'] + 50}", callback_data="bid")]
    ])

def render_auction():
    if not auction["active"]:
        leader_text = auction['leader'] if auction['leader'] else 'Никто'
        return f"🏆 **АУКЦИОН ЗАВЕРШЕН**\nЛот: Легендарный Солод 🌾\nПобедитель: {leader_text}\nФинальная цена: {auction['price']}"
    
    leader_text = auction['leader'] if auction['leader'] else "Нет ставок"
    return (f"⚖️ **ЖИВОЙ АУКЦИОН**\n"
            f"Лот: Легендарный Солод 🌾\n\n"
            f"Текущая ставка: **{auction['price']}**\n"
            f"Лидер: {leader_text}\n\n"
            f"⏱ Осталось: {auction['time_left']} сек.")

async def auction_loop():
    while auction["time_left"] > 0 and auction["active"]:
        await asyncio.sleep(2.0) # Обновляем раз в 2 секунды (Flood Control)
        auction["time_left"] -= 2
        
        if auction["time_left"] <= 0:
            auction["active"] = False
            auction["time_left"] = 0
        
        try:
            await bot.edit_message_text(
                chat_id=auction["chat_id"],
                message_id=auction["msg_id"],
                text=render_auction(),
                reply_markup=get_auction_kb(auction["active"]),
                parse_mode="Markdown"
            )
        except TelegramBadRequest:
            pass

@dp.message(Command("auction"))
async def cmd_auction(message: Message):
    auction["price"] = 100
    auction["leader"] = None
    auction["time_left"] = 60
    auction["active"] = True
    auction["chat_id"] = message.chat.id
    
    sent = await message.answer(render_auction(), reply_markup=get_auction_kb(True), parse_mode="Markdown")
    auction["msg_id"] = sent.message_id
    
    asyncio.create_task(auction_loop())

@dp.callback_query(F.data == "bid")
async def place_bid(cb: CallbackQuery):
    if not auction["active"]:
        await cb.answer("Аукцион завершен!", show_alert=True)
        return
        
    username = cb.from_user.username or cb.from_user.first_name
    if auction["leader"] == username:
        await cb.answer("Вы и так лидируете!", show_alert=True)
        return
        
    auction["price"] += 50
    auction["leader"] = username
    
    # Механика анти-снайпинга: если осталось мало времени, добавляем
    if auction["time_left"] < 10:
        auction["time_left"] += 10
        
    await cb.answer(f"Ставка принята! Новая цена: {auction['price']}", show_alert=False)
    
    try:
        await cb.message.edit_text(render_auction(), reply_markup=get_auction_kb(True), parse_mode="Markdown")
    except TelegramBadRequest:
        pass

async def main():
    print("▶ PoC: Живой Аукцион (Live Bidding)")
    print("Отправьте /auction в боте.")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
