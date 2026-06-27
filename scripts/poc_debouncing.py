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

from typing import Any

# Имитация быстрого In-Memory хранилища (В продакшене это Redis)
state: dict[str, Any] = {
    "clicks": 0,
    "last_rendered_clicks": 0,
    "chat_id": None,
    "msg_id": None,
}

# Lock нужен, чтобы избежать состояния гонки при конкурентных callback'ах
_lock = asyncio.Lock()


def get_kb() -> InlineKeyboardMarkup:
    # Делаем 3 кнопки, чтобы обходить блокировку UI Telegram (пока одна грузится, другие активны)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⚔️ УДАР 1", callback_data="hit"),
                InlineKeyboardButton(text="⚔️ УДАР 2", callback_data="hit"),
                InlineKeyboardButton(text="⚔️ УДАР 3", callback_data="hit"),
            ]
        ]
    )


# Фоновый воркер — проверяет стейт каждую секунду и делает ОДИН edit если были изменения
async def debouncer_worker() -> None:
    logging.info("Debouncer worker started")
    while True:
        await asyncio.sleep(1.0)  # Один тик = один максимальный запрос к Telegram

        async with _lock:
            msg_id = state["msg_id"]
            chat_id = state["chat_id"]
            current = state["clicks"]
            last = state["last_rendered_clicks"]

        if msg_id is None or current == last:
            continue  # Нечего обновлять

        # Фиксируем «отрендеренное» значение ДО запроса,
        # чтобы не пропустить клики, пришедшие во время самого edit
        async with _lock:
            state["last_rendered_clicks"] = current

        text = (
            f"🔥 **РЕЙД НА БОССА**\n"
            f"Счетчик урона: **{current}**\n\n"
            f"Даже если вы кликнули 50 раз за секунду — "
            f"API Telegram получил только 1 запрос на обновление."
        )

        try:
            await bot.edit_message_text(
                text,
                chat_id=chat_id,
                message_id=msg_id,
                reply_markup=get_kb(),
                parse_mode="Markdown",
            )
            logging.info("Rendered clicks=%d", current)
        except TelegramBadRequest as e:
            # Сообщение не изменилось или уже удалено — норма
            logging.debug("edit_message_text skipped: %s", e)


@dp.message(Command("debouncing"))
async def cmd_debouncing(message: Message) -> None:
    async with _lock:
        state["clicks"] = 0
        state["last_rendered_clicks"] = 0
        state["chat_id"] = message.chat.id
        state["msg_id"] = None  # сбрасываем до отправки нового сообщения

    text = "🔥 **РЕЙД НА БОССА**\nСчетчик урона: **0**\n\nСпамьте кнопку как можно быстрее!"
    sent = await message.answer(text, reply_markup=get_kb(), parse_mode="Markdown")

    async with _lock:
        state["msg_id"] = sent.message_id


async def _answer_cb(cb: CallbackQuery, text: str) -> None:
    """Fire-and-forget обёртка: не блокирует основной хендлер."""
    try:
        await cb.answer(text, show_alert=False)
    except Exception as e:
        # Глушим любые ошибки (в т.ч. TelegramRetryAfter), так как это фоновый UI-запрос
        pass


@dp.callback_query(F.data == "hit")
async def process_hit(cb: CallbackQuery) -> None:
    # Мгновенно обновляем счётчик в памяти — O(1), без запросов в Telegram
    async with _lock:
        state["clicks"] += 1
        total = state["clicks"]

    # cb.answer() — это HTTP round-trip ~100-180ms.
    # create_task() запускает его в фоне и сразу освобождает event loop,
    # позволяя обрабатывать следующий клик без ожидания ответа Telegram.
    asyncio.create_task(_answer_cb(cb, f"⚔️ {total}"))


async def main() -> None:
    print("▶ PoC: Система очередей (Debouncing)")
    print("Отправьте /debouncing в боте.")
    await bot.delete_webhook(drop_pending_updates=True)

    # asyncio.gather запускает воркер и поллинг ПАРАЛЛЕЛЬНО —
    # create_task до start_polling не давал воркеру получить управление
    await asyncio.gather(
        debouncer_worker(),
        dp.start_polling(bot),
    )


if __name__ == "__main__":
    asyncio.run(main())

