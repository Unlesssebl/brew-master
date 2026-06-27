import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest

from load_env import BOT_TOKEN
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

games = {}

def render_tapper(pos):
    matrix = ["🟫🟫🟫🟫🟫", "🟫🟫🟫🟫🟫"]
    bar = ["🟫", "🟫", "🟫", "🟫", "🟫"]
    if 0 <= pos < 5:
        bar[pos] = "🧝‍♂️"
    matrix[0] = "".join(bar)
    matrix[1] = "🍻🍻🍻🍻🍻"
    return "\n".join(matrix)

def get_kb(game_over=False):
    if game_over:
        return InlineKeyboardMarkup(inline_keyboard=[])
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🍺 Налить Светлое", callback_data="serve_beer")]
    ])

async def tapper_loop(chat_id, msg_id, game):
    while game["pos"] < 5 and not game["served"]:
        await asyncio.sleep(1.0)
        if game["served"]:
            break
        game["pos"] += 1
        
        if game["pos"] >= 5:
            text = "💢 **ПРОИГРЫШ!**\nЭльф ушел недовольным!\n\n" + render_tapper(5)
            try:
                await bot.edit_message_text(text, chat_id=chat_id, message_id=msg_id, reply_markup=get_kb(True))
            except TelegramBadRequest: 
                pass
            break
        else:
            text = "🍻 **БАРНАЯ СТОЙКА**\nУспей налить эльфу светлое!\n\n" + render_tapper(game["pos"])
            try:
                await bot.edit_message_text(text, chat_id=chat_id, message_id=msg_id, reply_markup=get_kb())
            except TelegramBadRequest: 
                pass

@dp.message(Command("tapper"))
async def cmd_tapper(message: Message):
    game = {"pos": 0, "served": False}
    text = "🍻 **БАРНАЯ СТОЙКА**\nУспей налить эльфу светлое!\n\n" + render_tapper(0)
    sent = await message.answer(text, reply_markup=get_kb())
    games[sent.message_id] = game
    asyncio.create_task(tapper_loop(message.chat.id, sent.message_id, game))

@dp.callback_query(F.data == "serve_beer")
async def serve_beer(cb: CallbackQuery):
    if not cb.message or not isinstance(cb.message, Message):
        return
    game = games.get(cb.message.message_id)
    if not game or game["served"] or game["pos"] >= 5:
        await cb.answer("Слишком поздно!", show_alert=True)
        return
    
    game["served"] = True
    text = "✅ **УСПЕХ!**\nЭльф выпил пиво и оставил 5 золота!\n\n" + render_tapper(game["pos"])
    
    try:
        await cb.message.edit_text(text, reply_markup=get_kb(True))
        await cb.answer("Вы успешно обслужили клиента!", show_alert=False)
    except TelegramBadRequest:
        pass

async def main():
    print("▶ PoC: Мини-игра Барная стойка (Tapper)")
    print("Отправьте /tapper в боте.")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
