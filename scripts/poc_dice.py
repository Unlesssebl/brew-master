import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.exceptions import TelegramAPIError

logging.basicConfig(level=logging.INFO)

from load_env import BOT_TOKEN
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

EFFECT_FIRE = "5104841245755180586"
EFFECT_PARTY = "5046509860389126442"

def get_event_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎲 Обычный бросок (1d6)", callback_data="roll_1d6")],
        [InlineKeyboardButton(text="🎲+🎲 Бросок 2d6 (Сумма)", callback_data="roll_2d6")],
        [InlineKeyboardButton(text="🟢 Бросок с Преимуществом", callback_data="roll_adv")],
        [InlineKeyboardButton(text="🔴 Бросок с Помехой", callback_data="roll_disadv")]
    ])

@dp.message(Command("dice"))
async def cmd_dice(message: Message):
    text = (
        "📖 **Событие: Пьяный Стражник**\n\n"
        "Вы пытаетесь заговорить зубы стражнику. Выберите способ броска кубиков, чтобы проверить новую механику!\n\n"
        "Ваш модификатор Харизмы: `+1`"
    )
    await message.answer(text, reply_markup=get_event_keyboard(), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("roll_"))
async def process_roll(callback: CallbackQuery):
    if not callback.message or not isinstance(callback.message, Message):
        return
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except TelegramAPIError:
        pass

    action = callback.data
    chat_id = callback.message.chat.id
    modifier = 1
    
    result_text = ""
    total = 0
    status = ""
    effect = None
    dice2 = None
    
    # Логика в зависимости от типа броска
    if action == "roll_1d6":
        dc = 5
        dice1 = await bot.send_dice(chat_id=chat_id, emoji="🎲")
        await asyncio.sleep(3.5)
        
        val = dice1.dice.value if dice1.dice else 1
        total = val + modifier
        
        result_text = f"🎲 Выпало: **{val}**\n"
        
        if total >= dc:
            status = "✅ **УСПЕХ!** (Сложность 5)"
            effect = EFFECT_PARTY
        else:
            status = "❌ **ПРОВАЛ!** (Сложность 5)"
            effect = EFFECT_FIRE
            
    else:
        # Для остальных режимов кидаем два кубика
        dice1 = await bot.send_dice(chat_id=chat_id, emoji="🎲")
        dice2 = await bot.send_dice(chat_id=chat_id, emoji="🎲")
        await asyncio.sleep(3.5)
        
        val1 = dice1.dice.value if dice1.dice else 1
        val2 = dice2.dice.value if dice2.dice else 1
        
        if action == "roll_2d6":
            dc = 8
            total = val1 + val2 + modifier
            result_text = f"🎲 Выпало: **{val1}** и **{val2}** (Сумма кубиков: {val1+val2})\n"
            
            if total >= dc:
                status = "✅ **УСПЕХ!** (Сложность 8)"
                effect = EFFECT_PARTY
            else:
                status = "❌ **ПРОВАЛ!** (Сложность 8)"
                effect = EFFECT_FIRE
                
        elif action == "roll_adv":
            dc = 5
            best_val = max(val1, val2)
            total = best_val + modifier
            result_text = f"🎲 Выпало: **{val1}** и **{val2}**.\n🟢 **Преимущество:** берем наибольшее ({best_val})\n"
            
            if total >= dc:
                status = "✅ **УСПЕХ!** (Сложность 5)"
                effect = EFFECT_PARTY
            else:
                status = "❌ **ПРОВАЛ!** (Сложность 5)"
                effect = EFFECT_FIRE
                
        elif action == "roll_disadv":
            dc = 5
            worst_val = min(val1, val2)
            total = worst_val + modifier
            result_text = f"🎲 Выпало: **{val1}** и **{val2}**.\n🔴 **Помеха:** берем наименьшее ({worst_val})\n"
            
            if total >= dc:
                status = "✅ **УСПЕХ!** (Сложность 5)"
                effect = EFFECT_PARTY
            else:
                status = "❌ **ПРОВАЛ!** (Сложность 5)"
                effect = EFFECT_FIRE

    calculation = (
        f"{result_text}"
        f"📊 Модификатор героя: **+{modifier}**\n"
        f"🎯 Итог: **{total}**\n\n"
        f"{status}"
    )

    try:
        # Отвечаем на последний брошенный кубик
        target_msg_id = dice1.message_id if (action == "roll_1d6" or not dice2) else dice2.message_id
        await bot.send_message(
            chat_id=chat_id,
            text=calculation,
            reply_to_message_id=target_msg_id,
            parse_mode="Markdown",
            message_effect_id=effect
        )
    except TelegramAPIError:
        await bot.send_message(
            chat_id=chat_id,
            text=calculation,
            parse_mode="Markdown"
        )
        
    await callback.answer()

async def main():
    print("▶ PoC: Ролевая система проверок (1d6, 2d6, Advantage)")
    print("Отправьте /dice в боте для старта квеста.")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
