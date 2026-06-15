from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder


def get_main_menu() -> ReplyKeyboardMarkup:
    """
    Возвращает Reply-клавиатуру главного меню.
    """
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="👑 Профиль"))
    builder.add(KeyboardButton(text="🍺 Сварить пиво"))
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)
