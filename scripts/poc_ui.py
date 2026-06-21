import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Укажите ваш токен бота (для теста можно вписать прямо сюда)
BOT_TOKEN = "8891264422:AAHhq1WEI2DwuKDb-eTxeOqmYeoGt3qHnWE" 

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Мокаем сетку (Матрица эмодзи)
# Представим, что 🟫 - это стенки таверны, 🟩 - пол, 🍲 - котел
TAVERN_MAP_EMPTY = [
    "🟫🟫🟫🟫🟫",
    "🟫🟩🟩🟩🟫",
    "🟫🟩🍲🟩🟫",
    "🟫🟩🟩🟩🟫",
    "🟫🟫🟫🟫🟫"
]

TAVERN_MAP_FULL = [
    "🟫🟫🟫🟫🟫",
    "🟫🟩🟩🟩🟫",
    "🟫🟩🔥🟩🟫",
    "🟫🟩🟩🟩🟫",
    "🟫🟫🟫🟫🟫"
]

def render_map(matrix):
    return "\n".join(matrix)

# Клавиатура с новыми стилизованными кнопками
def get_craft_keyboard(is_brewing=False):
    if is_brewing:
        # Кнопка сгорает/атакует (danger) или успех (success)
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Остановить варку", callback_data="stop_brew", **{"style": "danger"})],
            [InlineKeyboardButton(text="Собрать партию", callback_data="collect", **{"style": "success"})]
        ])
    else:
        # Обычные действия
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Добавить воду 💧", callback_data="add_water", **{"style": "primary"})],
            [InlineKeyboardButton(text="Добавить солод 🌾", callback_data="add_malt", **{"style": "primary"})],
            [InlineKeyboardButton(text="🔥 НАЧАТЬ ВАРКУ", callback_data="start_brew", **{"style": "success"})]
        ])

@dp.message(Command("start"))
async def cmd_start(message: Message):
    text = "🍺 Добро пожаловать в Живую Таверну!\n\n" + render_map(TAVERN_MAP_EMPTY)
    await message.answer(text, reply_markup=get_craft_keyboard(is_brewing=False))

@dp.callback_query(F.data.startswith("add_"))
async def process_add_ingredient(callback: CallbackQuery):
    ingredient = "Вода" if callback.data and "water" in callback.data else "Солод"
    # Демонстрация микро-фидбэка через Toast (без перерисовки экрана)
    try:
        await callback.answer(f"✅ {ingredient} добавлена! Котел булькает...", show_alert=False)
    except TelegramBadRequest as e:
        if "query is too old" in e.message:
            logging.warning("Callback query expired, skipping answer")
        else:
            raise

@dp.callback_query(F.data == "start_brew")
async def start_brew(callback: CallbackQuery):
    if not isinstance(callback.message, Message):
        return
    # Обновляем матрицу эмодзи (зажигаем огонь под котлом)
    text = "🔥 Процесс пошел!\n\n" + render_map(TAVERN_MAP_FULL)
    try:
        await callback.message.edit_text(text, reply_markup=get_craft_keyboard(is_brewing=True))
        await callback.answer("Варка начата!", show_alert=True)  # Модальное окно
    except TelegramBadRequest as e:
        if "query is too old" in e.message:
            logging.warning("Callback query expired, skipping answer")
        elif "message is not modified" in e.message:
            pass
        else:
            raise

@dp.callback_query(F.data == "collect")
async def collect_brew(callback: CallbackQuery):
    if not isinstance(callback.message, Message):
        return
    text = "🍺 Партия готова!\n\n" + render_map(TAVERN_MAP_EMPTY)
    try:
        await callback.message.edit_text(text, reply_markup=get_craft_keyboard(is_brewing=False))
        await callback.answer("Получено +10 Золота!", show_alert=False)
    except TelegramBadRequest as e:
        if "query is too old" in e.message:
            logging.warning("Callback query expired, skipping answer")
        elif "message is not modified" in e.message:
            pass
        else:
            raise

@dp.callback_query(F.data == "stop_brew")
async def stop_brew(callback: CallbackQuery):
    if not isinstance(callback.message, Message):
        return
    text = "🚨 Варка экстренно остановлена!\n\n" + render_map(TAVERN_MAP_EMPTY)
    try:
        await callback.message.edit_text(text, reply_markup=get_craft_keyboard(is_brewing=False))
        await callback.answer("Ингредиенты потеряны...", show_alert=True)
    except TelegramBadRequest as e:
        if "query is too old" in e.message:
            logging.warning("Callback query expired, skipping answer")
        elif "message is not modified" in e.message:
            pass
        else:
            raise

async def main():
    print("Запуск PoC бота...")
    # Удаляем вебхуки, чтобы использовать Long Polling для теста
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
