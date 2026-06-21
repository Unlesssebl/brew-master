import asyncio
import logging
import random
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.exceptions import TelegramAPIError

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = "8891264422:AAHhq1WEI2DwuKDb-eTxeOqmYeoGt3qHnWE"
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Хранилище сессий алхимии
alchemy_sessions = {}

def get_thermometer(temp):
    # Ограничиваем температуру 0-100
    temp = max(0, min(100, temp))
    blocks = temp // 10
    
    if temp < 40:
        emoji = "🟦"
        status = "Слишком холодно!"
    elif temp <= 70:
        emoji = "🟩"
        status = "ИДЕАЛЬНО!"
    else:
        emoji = "🟥"
        status = "ПЕРЕГРЕВ!"
        
    bar = emoji * blocks + "⬛" * (10 - blocks)
    return bar, status

def build_alchemy_message(session):
    if session["time_left"] <= 0:
        # Экран результатов
        score = session["score"]
        if score >= 12:
            result = "🏆 **ШЕДЕВРАЛЬНОЕ ЗЕЛЬЕ!**\nВы идеально контролировали жар."
        elif score >= 7:
            result = "👍 **НЕПЛОХОЕ ЗЕЛЬЕ**\nПить можно, но могло быть и лучше."
        else:
            result = "🤢 **ОМЕРЗИТЕЛЬНАЯ БУРДА**\nВы испортили ингредиенты."
            
        return (
            f"🧪 **Варка завершена!**\n\n"
            f"{result}\n\n"
            f"⏱ Время в идеальной зоне: {score} сек."
        )

    # Игровой экран
    bar, status = get_thermometer(session["temp"])
    
    return (
        f"🧪 **АЛХИМИЯ 2.0: Варка Эля**\n"
        f"Удерживайте температуру в зеленой зоне (40-70°C)!\n\n"
        f"🌡 **Температура:** {session['temp']}°C\n"
        f"`[{bar}]`\n"
        f"*{status}*\n\n"
        f"⏱ Осталось времени: {session['time_left']} сек.\n"
        f"🎯 Идеальных секунд: {session['score']}"
    )

def get_alchemy_keyboard(game_over=False):
    if game_over:
        return InlineKeyboardMarkup(inline_keyboard=[])
    
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔥 Подкинуть дров (+15°)", callback_data="alc_fire"),
        ],
        [
            InlineKeyboardButton(text="🧊 Добавить льда (-10°)", callback_data="alc_ice"),
        ]
    ])

async def alchemy_game_loop(chat_id, message_id, session):
    while session["time_left"] > 0:
        await asyncio.sleep(1.0) # Тик каждую секунду
        
        # Естественное остывание котла
        drop = random.randint(3, 8)
        session["temp"] = max(0, session["temp"] - drop)
        
        # Проверка идеальной зоны (40-70)
        if 40 <= session["temp"] <= 70:
            session["score"] += 1
            
        session["time_left"] -= 1
        
        # Обновляем UI
        text = build_alchemy_message(session)
        is_game_over = session["time_left"] <= 0
        
        try:
            await bot.edit_message_text(
                text=text,
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=get_alchemy_keyboard(game_over=is_game_over),
                parse_mode="Markdown",
            )
        except TelegramAPIError as e:
            if "message is not modified" not in str(e).lower():
                logging.warning(f"Tick error: {e}")

@dp.message(Command("alchemy"))
async def cmd_alchemy(message: Message):
    session = {
        "temp": 20,       # Стартовая температура
        "time_left": 15,  # Игра длится 15 секунд
        "score": 0,       # Секунды в идеальной зоне
    }
    
    text = build_alchemy_message(session)
    sent = await message.answer(text, reply_markup=get_alchemy_keyboard(), parse_mode="Markdown")
    
    alchemy_sessions[sent.message_id] = session
    
    # Запускаем фоновый цикл игры
    asyncio.create_task(alchemy_game_loop(sent.chat.id, sent.message_id, session))

@dp.callback_query(F.data.startswith("alc_"))
async def process_alchemy(callback: CallbackQuery):
    session = alchemy_sessions.get(callback.message.message_id)
    
    if not session or session["time_left"] <= 0:
        await callback.answer("Варка уже завершена!", show_alert=True)
        return
        
    action = callback.data
    
    if action == "alc_fire":
        session["temp"] = min(100, session["temp"] + 15)
        await callback.answer("🔥 Жар усилился!", show_alert=False)
    elif action == "alc_ice":
        session["temp"] = max(0, session["temp"] - 10)
        await callback.answer("🧊 Варево остывает...", show_alert=False)

    # Мгновенно обновляем интерфейс по клику
    text = build_alchemy_message(session)
    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_alchemy_keyboard(),
            parse_mode="Markdown"
        )
    except TelegramAPIError:
        pass

async def main():
    print("▶ PoC: Алхимия 2.0 (Температурный контроль)")
    print("Отправьте /alchemy в боте для старта мини-игры.")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
