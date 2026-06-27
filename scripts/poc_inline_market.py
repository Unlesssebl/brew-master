import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.types import InlineQuery, InlineQueryResultArticle, InputTextMessageContent, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest

logging.basicConfig(level=logging.INFO)
from load_env import BOT_TOKEN
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Обработчик инлайн-запросов (когда юзер пишет @botname sell 50 DarkAle 100g)
@dp.inline_query()
async def inline_market(inline_query: InlineQuery):
    query = inline_query.query.strip().lower()
    
    if not query.startswith("sell"):
        return
        
    parts = query.split()
    if len(parts) >= 4:
        amount = parts[1]
        item = parts[2]
        price = parts[3]
    else:
        amount = "10"
        item = "Эль"
        price = "50g"

    text = (f"📜 **КОНТРАКТ НА ПОКУПКУ**\n\n"
            f"Продавец: @{inline_query.from_user.username or inline_query.from_user.first_name}\n"
            f"Товар: {amount} {item.capitalize()}\n"
            f"Цена: {price}")
            
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Купить", callback_data=f"buy_contract_{inline_query.from_user.id}")]
    ])

    result = InlineQueryResultArticle(
        id="contract_1",
        title=f"Продать {amount} {item} за {price}",
        description="Отправить в чат торговый контракт",
        input_message_content=InputTextMessageContent(message_text=text, parse_mode="Markdown"),
        reply_markup=kb
    )
    
    await inline_query.answer([result], cache_time=1)

@dp.callback_query(F.data.startswith("buy_contract_"))
async def process_buy(cb: CallbackQuery):
    from aiogram.types import Message
    # seller_id = cb.data.split("_")[2] # ID продавца для БД
    buyer = cb.from_user.username or cb.from_user.first_name
    
    # В реальном приложении тут происходит транзакция в БД
    original_text = ""
    if cb.message and isinstance(cb.message, Message) and cb.message.text:
        original_text = cb.message.text
    else:
        original_text = "📜 **КОНТРАКТ НА ПОКУПКУ**"
        
    text = original_text + f"\n\n✅ **ПРОДАНО!**\nПокупатель: {buyer}"
    
    try:
        await bot.edit_message_text(text, inline_message_id=cb.inline_message_id)
        await cb.answer("Вы успешно купили товар!", show_alert=True)
    except TelegramBadRequest:
        pass

async def main():
    print("▶ PoC: Глобальный Черный Рынок (Inline Queries)")
    print("Откройте любой чат и напишите: @bot_username sell 10 Эль 50g")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
