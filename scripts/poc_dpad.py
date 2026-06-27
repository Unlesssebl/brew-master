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

# Исходная карта (5x5)
# 0 - Пол, 1 - Стена, 2 - Солод, 3 - Вода
MAP_DATA = [
    [1, 1, 1, 1, 1],
    [1, 0, 2, 0, 1],
    [1, 0, 0, 3, 1],
    [1, 0, 0, 0, 1],
    [1, 1, 1, 1, 1],
]

EMOJI_MAP = {
    0: "🟩",
    1: "🟫",
    2: "🌾",
    3: "💧",
    "player": "🎯"
}

# Хранилище сессий (в реальности это был бы Redis)
# session_id -> {"x": int, "y": int, "inventory": dict, "map": list}
sessions = {}

def render_map(session_data):
    px, py = session_data["x"], session_data["y"]
    m = session_data["map"]
    lines = []
    for y, row in enumerate(m):
        line_emojis = []
        for x, cell in enumerate(row):
            if x == px and y == py:
                line_emojis.append(EMOJI_MAP["player"])
            else:
                line_emojis.append(EMOJI_MAP[cell])
        lines.append("".join(line_emojis))
    return "\n".join(lines)

def get_dpad_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=" ", callback_data="ignore"),
            InlineKeyboardButton(text="⬆️", callback_data="move_up", **{"style": "primary"}),
            InlineKeyboardButton(text=" ", callback_data="ignore")
        ],
        [
            InlineKeyboardButton(text="⬅️", callback_data="move_left", **{"style": "primary"}),
            InlineKeyboardButton(text="⬇️", callback_data="move_down", **{"style": "primary"}),
            InlineKeyboardButton(text="➡️", callback_data="move_right", **{"style": "primary"})
        ],
        [
            InlineKeyboardButton(text="✋ ВЗЯТЬ ПРЕДМЕТ", callback_data="action_take", **{"style": "success"})
        ]
    ])

@dp.message(Command("dpad"))
async def cmd_dpad(message: Message):
    session_id = f"{message.chat.id}"
    sessions[session_id] = {
        "x": 1, "y": 3,  # Стартовая позиция
        "inventory": {"malt": 0, "water": 0},
        "map": [row[:] for row in MAP_DATA] # Копия карты
    }
    
    text = f"🎮 **Склад таверны**\nСобери ингредиенты!\n\n{render_map(sessions[session_id])}\n\nИнвентарь: 🌾 {sessions[session_id]['inventory']['malt']} | 💧 {sessions[session_id]['inventory']['water']}"
    await message.answer(text, reply_markup=get_dpad_keyboard(), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("move_"))
async def process_move(callback: CallbackQuery):
    if not callback.message or not isinstance(callback.message, Message):
        return
    session_id = f"{callback.message.chat.id}"
    if session_id not in sessions:
        await callback.answer("Сессия устарела. Напишите /dpad", show_alert=True)
        return

    data = sessions[session_id]
    nx, ny = data["x"], data["y"]
    
    if callback.data == "move_up": ny -= 1
    elif callback.data == "move_down": ny += 1
    elif callback.data == "move_left": nx -= 1
    elif callback.data == "move_right": nx += 1

    # Проверка столкновения со стеной (1)
    if data["map"][ny][nx] != 1:
        data["x"], data["y"] = nx, ny
    else:
        await callback.answer("💥 Упс! Стена.", show_alert=False)
        return

    text = f"🎮 **Склад таверны**\nСобери ингредиенты!\n\n{render_map(data)}\n\nИнвентарь: 🌾 {data['inventory']['malt']} | 💧 {data['inventory']['water']}"
    try:
        await callback.message.edit_text(text, reply_markup=get_dpad_keyboard(), parse_mode="Markdown")
        await callback.answer()
    except TelegramBadRequest:
        pass

@dp.callback_query(F.data == "action_take")
async def process_take(callback: CallbackQuery):
    if not callback.message or not isinstance(callback.message, Message):
        return
    session_id = f"{callback.message.chat.id}"
    if session_id not in sessions:
        return
        
    data = sessions[session_id]
    px, py = data["x"], data["y"]
    cell = data["map"][py][px]

    if cell == 2:
        data["inventory"]["malt"] += 1
        data["map"][py][px] = 0
        msg = "✅ Вы подобрали Солод!"
    elif cell == 3:
        data["inventory"]["water"] += 1
        data["map"][py][px] = 0
        msg = "✅ Вы подобрали Воду!"
    else:
        await callback.answer("Тут нечего брать...", show_alert=False)
        return

    text = f"🎮 **Склад таверны**\nСобери ингредиенты!\n\n{render_map(data)}\n\nИнвентарь: 🌾 {data['inventory']['malt']} | 💧 {data['inventory']['water']}"
    try:
        await callback.message.edit_text(text, reply_markup=get_dpad_keyboard(), parse_mode="Markdown")
        await callback.answer(msg, show_alert=False)
    except TelegramBadRequest:
        pass

@dp.callback_query(F.data == "ignore")
async def process_ignore(callback: CallbackQuery):
    await callback.answer()

async def main():
    print("Запуск PoC D-pad...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
