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

boss_sessions = {}

# ═══════════════════════════════════════════════════════════════
# СПРАЙТЫ ГОБЛИНА (13x13) - СТРОГИЕ КВАДРАТЫ
# Легенда: 🟩 кожа | ⬛ фон/тень/зрачки | ⬜ белки | 🟨 гнилые зубы/вспышка | 🟫 нос | 🟥 боль
# ═══════════════════════════════════════════════════════════════

FRAMES = {
    "idle": [
        "⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛",
        "⬛⬛⬛⬛🟩🟩🟩🟩🟩⬛⬛⬛⬛",
        "⬛⬛⬛🟩🟩🟩🟩🟩🟩🟩⬛⬛⬛",
        "⬛⬛🟩🟩🟩🟩🟩🟩🟩🟩🟩⬛⬛",
        "⬛🟩🟩⬛⬛⬛🟩⬛⬛⬛🟩🟩⬛",
        "⬛🟩🟩⬛⬜⬛🟩⬛⬜⬛🟩🟩⬛",
        "⬛🟩🟩🟩🟩🟩🟫🟩🟩🟩🟩🟩⬛",
        "⬛🟩🟩🟩🟩🟫🟫🟫🟩🟩🟩🟩⬛",
        "⬛⬛🟩🟩⬛⬛⬛⬛⬛🟩🟩⬛⬛",
        "⬛⬛🟩🟩🟨⬛🟨⬛🟨🟩🟩⬛⬛",
        "⬛⬛⬛🟩🟩🟩🟩🟩🟩🟩⬛⬛⬛",
        "⬛⬛⬛⬛🟩🟩🟩🟩🟩⬛⬛⬛⬛",
        "⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛",
    ],
    "blink_half": [
        "⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛",
        "⬛⬛⬛⬛🟩🟩🟩🟩🟩⬛⬛⬛⬛",
        "⬛⬛⬛🟩🟩🟩🟩🟩🟩🟩⬛⬛⬛",
        "⬛⬛🟩🟩🟩🟩🟩🟩🟩🟩🟩⬛⬛",
        "⬛🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩⬛",
        "⬛🟩🟩⬛⬛⬛🟩⬛⬛⬛🟩🟩⬛",
        "⬛🟩🟩🟩🟩🟩🟫🟩🟩🟩🟩🟩⬛",
        "⬛🟩🟩🟩🟩🟫🟫🟫🟩🟩🟩🟩⬛",
        "⬛⬛🟩🟩⬛⬛⬛⬛⬛🟩🟩⬛⬛",
        "⬛⬛🟩🟩🟨⬛🟨⬛🟨🟩🟩⬛⬛",
        "⬛⬛⬛🟩🟩🟩🟩🟩🟩🟩⬛⬛⬛",
        "⬛⬛⬛⬛🟩🟩🟩🟩🟩⬛⬛⬛⬛",
        "⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛",
    ],
    "blink_closed": [
        "⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛",
        "⬛⬛⬛⬛🟩🟩🟩🟩🟩⬛⬛⬛⬛",
        "⬛⬛⬛🟩🟩🟩🟩🟩🟩🟩⬛⬛⬛",
        "⬛⬛🟩🟩🟩🟩🟩🟩🟩🟩🟩⬛⬛",
        "⬛🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩⬛",
        "⬛🟩🟩⬛⬛⬛🟩⬛⬛⬛🟩🟩⬛",
        "⬛🟩🟩🟩🟩🟩🟫🟩🟩🟩🟩🟩⬛",
        "⬛🟩🟩🟩🟩🟫🟫🟫🟩🟩🟩🟩⬛",
        "⬛⬛🟩🟩⬛⬛⬛⬛⬛🟩🟩⬛⬛",
        "⬛⬛🟩🟩⬛⬛⬛⬛⬛🟩🟩⬛⬛",
        "⬛⬛⬛🟩🟩🟩🟩🟩🟩🟩⬛⬛⬛",
        "⬛⬛⬛⬛🟩🟩🟩🟩🟩⬛⬛⬛⬛",
        "⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛",
    ],
    "impact_flash": [
        "🟨🟨🟨🟨🟨🟨🟨🟨🟨🟨🟨🟨🟨",
        "🟨🟨⬜🟨🟨🟨🟨🟨🟨🟨⬜🟨🟨",
        "🟨🟨🟨🟨🟨🟨🟨🟨🟨🟨🟨🟨🟨",
        "🟨🟨🟨🟨⬜🟨🟨🟨⬜🟨🟨🟨🟨",
        "🟨⬜🟨🟨🟨🟨🟨🟨🟨🟨🟨⬜🟨",
        "🟨🟨🟨🟨🟨🟨🟨🟨🟨🟨🟨🟨🟨",
        "🟨🟨🟨🟨🟨🟨⬜🟨🟨🟨🟨🟨🟨",
        "🟨🟨🟨🟨🟨🟨🟨🟨🟨🟨🟨🟨🟨",
        "🟨⬜🟨🟨🟨🟨🟨🟨🟨🟨🟨⬜🟨",
        "🟨🟨🟨🟨⬜🟨🟨🟨⬜🟨🟨🟨🟨",
        "🟨🟨🟨🟨🟨🟨🟨🟨🟨🟨🟨🟨🟨",
        "🟨🟨⬜🟨🟨🟨🟨🟨🟨🟨⬜🟨🟨",
        "🟨🟨🟨🟨🟨🟨🟨🟨🟨🟨🟨🟨🟨",
    ],
    "recoil": [
        "⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛",
        "⬛⬛⬛⬛⬛🟩🟩🟩🟩🟩⬛⬛⬛",
        "⬛⬛⬛⬛🟩🟩🟩🟩🟩🟩🟩⬛⬛",
        "⬛⬛⬛🟩🟩🟩🟩🟩🟩🟩🟩🟩⬛",
        "⬛⬛🟩🟩⬛⬛⬛🟩⬛⬛⬛🟩⬛",
        "⬛⬛🟩🟩⬛⬜⬛🟩⬛⬜⬛🟩⬛",
        "⬛⬛🟩🟩🟩🟩🟩🟫🟩🟩🟩🟩⬛",
        "⬛⬛🟩🟩🟩🟩🟫🟫🟫🟩🟩🟩⬛",
        "⬛⬛⬛🟩🟩⬛⬛⬛⬛⬛🟩⬛⬛",
        "⬛⬛⬛🟩🟩⬛🟨⬛🟨⬛🟩⬛⬛",
        "⬛⬛⬛⬛🟩🟩🟩🟩🟩🟩🟩⬛⬛",
        "⬛⬛⬛⬛⬛🟩🟩🟩🟩🟩⬛⬛⬛",
        "⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛",
    ],
    "hurt_bright": [
        "⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛",
        "⬛⬛⬛⬛🟥🟥🟥🟥🟥⬛⬛⬛⬛",
        "⬛⬛⬛🟥🟥🟥🟥🟥🟥🟥⬛⬛⬛",
        "⬛⬛🟥🟥🟥🟥🟥🟥🟥🟥🟥⬛⬛",
        "⬛🟥🟥⬛⬛⬛🟥⬛⬛⬛🟥🟥⬛",
        "⬛🟥🟥⬛🟨⬛🟥⬛🟨⬛🟥🟥⬛",
        "⬛🟥🟥🟥🟥🟥🟫🟥🟥🟥🟥🟥⬛",
        "⬛🟥🟥🟥🟥🟫🟫🟫🟥🟥🟥🟥⬛",
        "⬛⬛🟥🟥⬛⬛⬛⬛⬛🟥🟥⬛⬛",
        "⬛⬛🟥🟥🟨⬛🟨⬛🟨🟥🟥⬛⬛",
        "⬛⬛⬛🟥🟥🟥🟥🟥🟥🟥⬛⬛⬛",
        "⬛⬛⬛⬛🟥🟥🟥🟥🟥⬛⬛⬛⬛",
        "⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛",
    ],
    "pain": [
        "⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛",
        "⬛⬛⬛⬛🟩🟩🟩🟩🟩⬛⬛⬛⬛",
        "⬛⬛⬛🟩🟩🟩🟩🟩🟩🟩⬛⬛⬛",
        "⬛⬛🟩🟩🟩🟩🟩🟩🟩🟩🟩⬛⬛",
        "⬛🟩🟩⬛⬛⬛🟩⬛⬛⬛🟩🟩⬛",
        "⬛🟩🟩🟩⬛🟩🟩🟩⬛🟩🟩🟩⬛",
        "⬛🟩🟩🟩🟩🟩🟫🟩🟩🟩🟩🟩⬛",
        "⬛🟩🟩🟩🟩🟫🟫🟫🟩🟩🟩🟩⬛",
        "⬛⬛🟩🟩⬛⬛⬛⬛⬛🟩🟩⬛⬛",
        "⬛⬛🟩🟩⬛🟨⬛🟨⬛🟩🟩⬛⬛",
        "⬛⬛⬛🟩🟩🟩🟩🟩🟩🟩⬛⬛⬛",
        "⬛⬛⬛⬛🟩🟩🟩🟩🟩⬛⬛⬛⬛",
        "⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛",
    ],
    "angry": [
        "⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛",
        "⬛⬛⬛⬛🟩🟩🟩🟩🟩⬛⬛⬛⬛",
        "⬛⬛⬛🟩⬛⬛🟩⬛⬛🟩⬛⬛⬛",
        "⬛⬛🟩⬛⬛⬛🟩⬛⬛⬛🟩⬛⬛",
        "⬛🟩🟩⬛⬜⬛🟩⬛⬜⬛🟩🟩⬛",
        "⬛🟩🟩🟩🟩🟩🟫🟩🟩🟩🟩🟩⬛",
        "⬛🟩🟩🟩🟩🟫🟫🟫🟩🟩🟩🟩⬛",
        "⬛⬛🟩🟩⬛⬛⬛⬛⬛🟩🟩⬛⬛",
        "⬛⬛🟩🟩🟨⬛🟨⬛🟨🟩🟩⬛⬛",
        "⬛⬛⬛🟩🟩🟩🟩🟩🟩🟩⬛⬛⬛",
        "⬛⬛⬛⬛🟩🟩🟩🟩🟩⬛⬛⬛⬛",
        "⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛",
    ],
    "dodge_lean": [
        "⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛",
        "⬛⬛⬛⬛⬛⬛🟩🟩🟩🟩🟩⬛⬛",
        "⬛⬛⬛⬛⬛🟩🟩🟩🟩🟩🟩🟩⬛",
        "⬛⬛⬛⬛🟩🟩🟩🟩🟩🟩🟩🟩🟩",
        "⬛⬛⬛🟩🟩⬛⬛⬛🟩⬛⬛⬛🟩",
        "⬛⬛⬛🟩🟩⬛⬛⬜🟩⬛⬛⬜🟩",
        "⬛⬛⬛🟩🟩🟩🟩🟩🟫🟩🟩🟩🟩",
        "⬛⬛⬛🟩🟩🟩🟩🟫🟫🟫🟩🟩🟩",
        "⬛⬛⬛⬛🟩🟩⬛⬛⬛⬛⬛🟩🟩",
        "⬛⬛⬛⬛🟩🟩🟨⬛🟨⬛🟨🟩🟩",
        "⬛⬛⬛⬛⬛🟩🟩🟩🟩🟩🟩🟩⬛",
        "⬛⬛⬛⬛⬛⬛🟩🟩🟩🟩🟩⬛⬛",
        "⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛",
    ],
    "dodge_blur": [
        "⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛",
        "⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛",
        "⬛⬛⬛⬜⬜⬜⬜⬜⬜⬜⬛⬛⬛",
        "⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛",
        "⬛⬛⬜⬜⬜⬜⬜⬜⬜⬜⬜⬛⬛",
        "⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛",
        "⬛⬛⬜⬜⬜⬜⬜⬜⬜⬜⬜⬛⬛",
        "⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛",
        "⬛⬛⬛⬜⬜⬜⬜⬜⬜⬜⬛⬛⬛",
        "⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛",
        "⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛",
        "⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛",
        "⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛",
    ],
    "dodge_appear": [
        "⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛",
        "⬛⬛🟩🟩🟩🟩🟩⬛⬛⬛⬛⬛⬛",
        "⬛🟩🟩🟩🟩🟩🟩🟩⬛⬛⬛⬛⬛",
        "🟩🟩🟩🟩🟩🟩🟩🟩🟩⬛⬛⬛⬛",
        "🟩⬛⬛⬛🟩⬛⬛⬛🟩🟩⬛⬛⬛",
        "🟩⬜⬛⬛🟩⬜⬛⬛🟩🟩⬛⬛⬛",
        "🟩🟩🟩🟩🟫🟩🟩🟩🟩🟩⬛⬛⬛",
        "🟩🟩🟩🟫🟫🟫🟩🟩🟩🟩⬛⬛⬛",
        "🟩🟩⬛⬛⬛⬛⬛🟩🟩⬛⬛⬛⬛",
        "🟩🟩🟨⬛🟨⬛🟨🟩🟩⬛⬛⬛⬛",
        "⬛🟩🟩🟩🟩🟩🟩🟩⬛⬛⬛⬛⬛",
        "⬛⬛🟩🟩🟩🟩🟩⬛⬛⬛⬛⬛⬛",
        "⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛",
    ],
    "dying_1": [
        "⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛",
        "⬛⬛⬛⬛🟩🟩🟩🟩🟩⬛⬛⬛⬛",
        "⬛⬛⬛🟩🟩🟩🟩🟩🟩🟩⬛⬛⬛",
        "⬛⬛🟩🟩🟩🟩🟩🟩🟩🟩🟩⬛⬛",
        "⬛🟩🟩⬛⬛⬛🟩⬛⬛⬛🟩🟩⬛",
        "⬛🟩🟩⬛⬜⬜🟩⬛⬜⬜🟩🟩⬛",
        "⬛🟩🟩🟩🟩🟩🟫🟩🟩🟩🟩🟩⬛",
        "⬛🟩🟩🟩🟩🟫🟫🟫🟩🟩🟩🟩⬛",
        "⬛⬛🟩🟩⬛⬛⬛⬛⬛🟩🟩⬛⬛",
        "⬛⬛🟩🟩⬛⬛⬛⬛⬛🟩🟩⬛⬛",
        "⬛⬛⬛🟩🟩🟩🟩🟩🟩🟩⬛⬛⬛",
        "⬛⬛⬛⬛🟩🟩🟩🟩🟩⬛⬛⬛⬛",
        "⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛",
    ],
    "dying_2": [
        "⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛",
        "⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛",
        "⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛",
        "⬛⬛⬛⬛🟩🟩🟩🟩🟩⬛⬛⬛⬛",
        "⬛⬛⬛🟩🟩🟩🟩🟩🟩🟩⬛⬛⬛",
        "⬛⬛🟩🟩⬛⬛⬛🟩⬛⬛⬛🟩⬛",
        "⬛⬛🟩🟩⬛⬜⬜🟩⬛⬜⬜🟩⬛",
        "⬛⬛🟩🟩🟩🟩🟩🟫🟩🟩🟩🟩⬛",
        "⬛⬛🟩🟩🟩🟩🟫🟫🟫🟩🟩🟩⬛",
        "⬛⬛⬛🟩🟩⬛⬛⬛⬛⬛🟩⬛⬛",
        "⬛⬛⬛🟩🟩⬛⬛⬛⬛⬛🟩⬛⬛",
        "⬛⬛⬛⬛🟩🟩🟩🟩🟩⬛⬛⬛⬛",
        "⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛",
    ],
    "dead": [
        "⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛",
        "⬛⬛⬛⬛⬜⬜⬜⬜⬜⬛⬛⬛⬛",
        "⬛⬛⬛⬜⬜⬜⬜⬜⬜⬜⬛⬛⬛",
        "⬛⬛⬜⬜⬜⬜⬜⬜⬜⬜⬜⬛⬛",
        "⬛⬜⬜⬛⬛⬛⬜⬛⬛⬛⬜⬜⬛",
        "⬛⬜⬜⬛⬛⬛⬜⬛⬛⬛⬜⬜⬛",
        "⬛⬜⬜⬜⬜⬜⬛⬜⬜⬜⬜⬜⬛",
        "⬛⬜⬜⬜⬜⬛⬛⬛⬜⬜⬜⬜⬛",
        "⬛⬛⬜⬜⬛⬛⬛⬛⬛⬜⬜⬛⬛",
        "⬛⬛⬛⬜⬜⬛⬜⬛⬜⬜⬛⬛⬛",
        "⬛⬛⬛⬛⬜⬛⬜⬛⬜⬛⬛⬛⬛",
        "⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛",
        "⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛",
    ],
}

ANIMATIONS = {
    "quick_hit": {
        "frames": ["impact_flash", "recoil", "hurt_bright", "pain", "angry", "idle"],
        "delays": [0.1,             0.25,     0.25,          0.3,    0.4,     0.0],
    },
    "heavy_hit": {
        "frames": ["impact_flash", "impact_flash", "hurt_bright", "recoil", "pain", "angry", "idle"],
        "delays": [0.1,             0.15,           0.3,           0.2,      0.35,   0.4,     0.0],
    },
    "dodge": {
        "frames": ["dodge_lean", "dodge_blur", "dodge_appear", "idle"],
        "delays": [0.2,           0.2,          0.2,            0.0],
    },
    "death": {
        "frames": ["impact_flash", "hurt_bright", "dying_1", "dying_2", "dying_2", "dead"],
        "delays": [0.15,            0.25,          0.3,       0.3,       0.4,       0.0],
    },
    "blink": {
        "frames": ["blink_half", "blink_closed", "blink_half", "idle"],
        "delays": [0.07,          0.1,             0.07,         0.0],
    },
}

BOSS_PHRASES = [
    "«Ах ты мелкий пивовар!»",
    "«Мое золото! Отдай мое золото!»",
    "«Ты пожалеешь!»",
    "«Я тебя раздавлю!»",
]

DODGE_TAUNTS = [
    "«Ха! Не попал!»",
    "«Медленно, пивовар!»",
    "«Это всё что ты умеешь?»",
]

def render_frame(frame_name):
    return "\n".join(FRAMES[frame_name])

def generate_progress_bar(current, total, length=13):
    percent = max(0, min(1, current / total))
    filled = int(percent * length)
    empty = length - filled
    if percent > 0.5:
        bar_emoji = "🟩"
    elif percent > 0.25:
        bar_emoji = "🟨"
    else:
        bar_emoji = "🟥"
    return bar_emoji * filled + "⬛" * empty

def build_message(boss, face, phrase=None):
    if phrase is None:
        phrase = random.choice(BOSS_PHRASES)
    sprite = render_frame(face)
    
    if boss["hp"] > 0:
        bar = generate_progress_bar(boss["hp"], boss["max_hp"])
        hp_line = f"❤️  {boss['hp']}/{boss['max_hp']}"
        return (
            f"🐲 **ГОБЛИН-БОСС**\n"
            f"*{phrase}*\n\n"
            f"{sprite}\n\n"
            f"{hp_line}\n"
            f"`[{bar}]`"
        )
    else:
        bar = generate_progress_bar(0, boss["max_hp"])
        return (
            f"💀 **ГОБЛИН ПОВЕРЖЕН!**\n"
            f"*«Мое... мое золото...»*\n\n"
            f"{sprite}\n\n"
            f"❤️  0/{boss['max_hp']}\n"
            f"`[{bar}]`\n\n"
            f"🎉 **ПОБЕДА!** Таверна в безопасности!"
        )

def get_keyboard(disabled=False):
    if disabled:
        return InlineKeyboardMarkup(inline_keyboard=[])
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚔️ Быстрый (-10)", callback_data="atk_fast"),
            InlineKeyboardButton(text="🔥 Тяжелый (-25)", callback_data="atk_heavy"),
        ]
    ])

async def play_animation(chat_id, message_id, boss, anim_key, phrase=None):
    boss["animating"] = True
    anim = ANIMATIONS[anim_key]
    frames = anim["frames"]
    delays = anim["delays"]
    is_dead = boss["hp"] <= 0

    for i, (frame, delay) in enumerate(zip(frames, delays)):
        is_last = (i == len(frames) - 1)
        show_buttons = is_last and not is_dead

        text = build_message(boss, frame, phrase)
        try:
            await bot.edit_message_text(
                text=text,
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=get_keyboard(disabled=not show_buttons),
                parse_mode="Markdown",
            )
        except TelegramAPIError as e:
            if "message is not modified" not in str(e).lower():
                logging.warning(f"Frame {frame}: {e}")

        if delay > 0:
            await asyncio.sleep(delay)

    boss["animating"] = False

async def idle_blink_loop(chat_id, message_id, boss):
    while boss["hp"] > 0:
        # Увеличен интервал моргания, чтобы избежать Flood control от Telegram API
        await asyncio.sleep(random.uniform(10, 15))
        if not boss["animating"] and boss["hp"] > 0:
            await play_animation(chat_id, message_id, boss, "blink")

@dp.message(Command("boss"))
async def cmd_boss(message: Message):
    max_hp = 100
    boss = {"hp": max_hp, "max_hp": max_hp, "animating": False}

    text = build_message(boss, "idle")
    sent = await message.answer(text, reply_markup=get_keyboard(), parse_mode="Markdown")

    boss_sessions[sent.message_id] = boss
    asyncio.create_task(idle_blink_loop(sent.chat.id, sent.message_id, boss))

@dp.callback_query(F.data.startswith("atk_"))
async def process_combat(callback: CallbackQuery):
    boss = boss_sessions.get(callback.message.message_id)

    if not boss or boss["hp"] <= 0:
        await callback.answer("Этот босс уже мертв!", show_alert=True)
        return
    if boss["animating"]:
        await callback.answer("⏳ Подождите...", show_alert=False)
        return

    action = callback.data
    damage = 0
    toast = ""
    anim_key = "quick_hit"
    phrase = None

    if action == "atk_fast":
        damage = 10
        toast = "⚔️ Быстрый удар! −10 HP"
        anim_key = "quick_hit"
    elif action == "atk_heavy":
        if random.random() < 0.3:
            damage = 0
            toast = "💨 ПРОМАХ! Гоблин увернулся!"
            anim_key = "dodge"
            phrase = random.choice(DODGE_TAUNTS)
        else:
            damage = 25
            toast = "🔥 ТЯЖЕЛЫЙ УДАР! −25 HP"
            anim_key = "heavy_hit"

    if damage > 0:
        boss["hp"] = max(0, boss["hp"] - damage)

    if boss["hp"] <= 0:
        anim_key = "death"

    try:
        await callback.answer(toast, show_alert=False)
    except TelegramAPIError:
        pass

    asyncio.create_task(
        play_animation(
            callback.message.chat.id,
            callback.message.message_id,
            boss,
            anim_key,
            phrase,
        )
    )

async def main():
    print("▶ PoC: Анимированный Босс (Желтые зубы, защита от спама)")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
