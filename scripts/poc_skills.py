import asyncio
import logging
import time
from typing import Any

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest

logging.basicConfig(level=logging.INFO)
from load_env import BOT_TOKEN

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Имитация хранилища боя (Redis/БД)
state: dict[str, Any] = {
    "chat_id": None,
    "msg_id": None,
    "hp": 5000,
    "skills_cd": {
        "attack": 0.0,
        "fireball": 0.0,
        "heal": 0.0
    },
    "last_render_hash": ""
}

# Настройки скиллов (баланс)
SKILLS = {
    "attack": {"name": "🗡 Обычный удар", "cd": 1, "damage": 50},
    "fireball": {"name": "🔥 Огненный шар", "cd": 5, "damage": 300},
    "heal": {"name": "💚 Лечение", "cd": 10, "damage": -200}, # отрицательный урон = хил
}

_lock = asyncio.Lock()


def get_kb() -> InlineKeyboardMarkup:
    now = time.time()
    buttons = []
    
    for skill_id, skill in SKILLS.items():
        cd_end = state["skills_cd"][skill_id]
        if now < cd_end:
            rem = int(cd_end - now) + 1
            text = f"⏳ {rem}с | {skill['name']}"
        else:
            text = skill["name"]
            
        buttons.append([InlineKeyboardButton(text=text, callback_data=f"skill_{skill_id}")])
        
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# Воркер, который раз в секунду синхронизирует состояние памяти с экраном пользователя
async def cd_updater_worker() -> None:
    logging.info("CD Updater worker started")
    while True:
        await asyncio.sleep(1.0)
        
        async with _lock:
            msg_id = state["msg_id"]
            chat_id = state["chat_id"]
            hp = state["hp"]
            # get_kb читает state, поэтому вызываем внутри лока (операция очень быстрая)
            kb = get_kb()
            
        if not msg_id:
            continue
            
        # Хешируем состояние и формируем текст СНАРУЖИ лока, чтобы не блокировать обработчики
        current_hash = f"{hp}_{kb.model_dump()}"
        
        async with _lock:
            if current_hash == state["last_render_hash"]:
                continue 
            state["last_render_hash"] = current_hash
            
        text = f"👾 **ЭПИЧЕСКИЙ БОСС**\nЗдоровье: ❤️ **{hp}**\n\nИспользуйте скиллы для победы! Следите за кулдаунами."

        try:
            await bot.edit_message_text(
                text=text,
                chat_id=chat_id,
                message_id=msg_id,
                reply_markup=kb,
                parse_mode="Markdown"
            )
            logging.info("Rendered HP=%d", hp)
        except TelegramBadRequest as e:
            logging.debug("edit_message_text skipped: %s", e)


@dp.message(Command("skills"))
async def cmd_skills(message: Message) -> None:
    async with _lock:
        state["chat_id"] = message.chat.id
        state["hp"] = 5000
        state["skills_cd"] = {"attack": 0, "fireball": 0, "heal": 0}
        state["last_render_hash"] = ""
        state["msg_id"] = None
        
    text = f"👾 **ЭПИЧЕСКИЙ БОСС**\nЗдоровье: ❤️ **5000**\n\nИспользуйте скиллы для победы! Следите за кулдаунами."
    sent = await message.answer(text, reply_markup=get_kb(), parse_mode="Markdown")
    
    async with _lock:
        state["msg_id"] = sent.message_id


async def _answer_cb(cb: CallbackQuery, text: str, show_alert: bool = False) -> None:
    """Fire-and-forget обёртка: не блокирует основной хендлер."""
    try:
        await cb.answer(text, show_alert=show_alert)
    except Exception:
        pass


@dp.callback_query(F.data.startswith("skill_"))
async def process_skill(cb: CallbackQuery) -> None:
    if not cb.data:
        return
    skill_id = cb.data.split("_")[1]
    skill = SKILLS[skill_id]
    
    async with _lock:
        now = time.time()
        cd_end = state["skills_cd"][skill_id]
        
        # 1. ПРОВЕРКА КУЛДАУНА
        if now < cd_end:
            rem = round(cd_end - now, 1)
            asyncio.create_task(_answer_cb(cb, f"⏳ Скилл на перезарядке!\nОсталось: {rem} сек.", show_alert=True))
            return
            
        # 2. КАСТ СКИЛЛА
        state["skills_cd"][skill_id] = now + skill["cd"]
        
        if skill["damage"] > 0:
            state["hp"] = max(0, state["hp"] - skill["damage"])
            msg = f"💥 Вы нанесли {skill['damage']} урона!"
        else:
            state["hp"] -= skill["damage"]
            msg = f"💚 Вы восстановили {-skill['damage']} ХП!"

    # Снаружи лока: показываем всплывашку юзеру.
    asyncio.create_task(_answer_cb(cb, msg))


async def main() -> None:
    print("▶ PoC: Система Кулдаунов (Dota/LoL style)")
    print("Отправьте /skills в боте.")
    await bot.delete_webhook(drop_pending_updates=True)
    
    await asyncio.gather(
        cd_updater_worker(),
        dp.start_polling(bot)
    )

if __name__ == "__main__":
    asyncio.run(main())
