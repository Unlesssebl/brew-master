import asyncio
import logging
import math
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest

logging.basicConfig(level=logging.INFO)

from load_env import BOT_TOKEN
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Карта подземелья (12x12). 0 - Пол, 1 - Стена, 2 - Сундук с золотом
MAP_DATA = [
    [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
    [1, 0, 0, 0, 1, 0, 0, 0, 0, 0, 2, 1],
    [1, 0, 2, 0, 1, 0, 1, 1, 1, 0, 0, 1],
    [1, 0, 0, 0, 0, 0, 1, 2, 1, 0, 0, 1],
    [1, 1, 1, 0, 1, 1, 1, 0, 1, 0, 0, 1],
    [1, 0, 0, 0, 0, 0, 0, 0, 1, 1, 0, 1],
    [1, 0, 1, 1, 1, 0, 1, 0, 0, 0, 0, 1],
    [1, 0, 0, 0, 1, 0, 1, 1, 1, 1, 0, 1],
    [1, 1, 2, 0, 1, 0, 0, 0, 0, 0, 0, 1],
    [1, 0, 0, 0, 1, 1, 1, 1, 0, 1, 1, 1],
    [1, 0, 0, 0, 0, 0, 2, 0, 0, 0, 0, 1],
    [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
]

EMOJI_MAP = {
    0: "🟫", # Пол
    1: "🧱", # Стена
    2: "💰", # Сундук
    "player": "🧙‍♂️",
    "fog": "⬛"  # Туман войны
}

sessions = {}

# --- Логика Тумана Войны (Raycasting / Line of Sight) ---

def bresenham(x0, y0, x1, y1):
    """Алгоритм Брезенхема для построения линии обзора."""
    points = []
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    x, y = x0, y0
    sx = -1 if x0 > x1 else 1
    sy = -1 if y0 > y1 else 1
    
    if dx > dy:
        err = dx / 2.0
        while x != x1:
            points.append((x, y))
            err -= dy
            if err < 0:
                y += sy
                err += dx
            x += sx
    else:
        err = dy / 2.0
        while y != y1:
            points.append((x, y))
            err -= dx
            if err < 0:
                x += sx
                err += dy
            y += sy
    points.append((x, y))
    return points

def is_visible(px, py, tx, ty, map_data):
    """Проверяет, видно ли точку tx,ty из px,py (не перекрывают ли стены)."""
    line = bresenham(px, py, tx, ty)
    for x, y in line[:-1]: # Исключаем саму целевую точку
        if map_data[y][x] == 1: # Если на пути стена
            return False
    return True

def render_viewport(session_data, radius=3):
    """Рендерит 'камеру' 7x7 (радиус 3) вокруг игрока с учетом тумана войны."""
    px, py = session_data["x"], session_data["y"]
    m = session_data["map"]
    viewport = []
    
    for y in range(py - radius, py + radius + 1):
        row = []
        for x in range(px - radius, px + radius + 1):
            if 0 <= y < len(m) and 0 <= x < len(m[0]):
                # Проверяем дистанцию (круглый свет факела)
                dist = math.sqrt((px - x)**2 + (py - y)**2)
                
                # Если в пределах радиуса и нет стен на пути обзора
                if dist <= radius and is_visible(px, py, x, y, m):
                    if px == x and py == y:
                        row.append(EMOJI_MAP["player"])
                    else:
                        row.append(EMOJI_MAP[m[y][x]])
                else:
                    # Вне радиуса или за стеной - рисуем туман
                    row.append(EMOJI_MAP["fog"])
            else:
                # Границы мира (за картой)
                row.append(EMOJI_MAP["fog"])
        viewport.append("".join(row))
    return "\n".join(viewport)

def get_dpad_keyboard():
    # Кнопки используют кастомные **kwargs для style (если планируете внедрить потом через Mini Apps или кастомный клиент)
    # Стандартный Telegram клиент игнорирует style, но это часть вашего дизайна.
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
            InlineKeyboardButton(text="✋ ОТКРЫТЬ СУНДУК", callback_data="action_take", **{"style": "success"})
        ]
    ])

@dp.message(Command("fog"))
async def cmd_fog(message: Message):
    session_id = f"{message.chat.id}"
    sessions[session_id] = {
        "x": 1, "y": 1,  # Стартовая позиция в углу
        "gold": 0,
        "map": [row[:] for row in MAP_DATA]
    }
    
    text = f"🔦 **Экспедиция в Темные Подземелья**\nВы спускаетесь в подвал. У вас в руках факел с радиусом обзора 3 клетки.\n\n{render_viewport(sessions[session_id])}\n\nСобрано золота: 💰 {sessions[session_id]['gold']}"
    await message.answer(text, reply_markup=get_dpad_keyboard(), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("move_"))
async def process_move(callback: CallbackQuery):
    if not callback.message or not isinstance(callback.message, Message):
        return
    session_id = f"{callback.message.chat.id}"
    if session_id not in sessions:
        await callback.answer("Сессия устарела. Напишите /fog", show_alert=True)
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
        await callback.answer("💥 Упс! Вы ударились о стену.", show_alert=False)
        return

    text = f"🔦 **Экспедиция в Темные Подземелья**\nОсторожно, в темноте могут быть сундуки!\n\n{render_viewport(data)}\n\nСобрано золота: 💰 {data['gold']}"
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
        gold_found = 150
        data["gold"] += gold_found
        data["map"][py][px] = 0 # Сундук пропадает
        msg = f"✅ Вы открыли сундук и нашли {gold_found} золота!"
    else:
        await callback.answer("Здесь нечего открывать.", show_alert=False)
        return

    text = f"🔦 **Экспедиция в Темные Подземелья**\nОсторожно, в темноте могут быть сундуки!\n\n{render_viewport(data)}\n\nСобрано золота: 💰 {data['gold']}"
    try:
        await callback.message.edit_text(text, reply_markup=get_dpad_keyboard(), parse_mode="Markdown")
        await callback.answer(msg, show_alert=True) # Модалка для наглядности
    except TelegramBadRequest:
        pass

@dp.callback_query(F.data == "ignore")
async def process_ignore(callback: CallbackQuery):
    await callback.answer()

async def main():
    print("Запуск PoC Fog of War (Туман Войны)...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
