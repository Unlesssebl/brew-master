from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_crafting_keyboard(
    malt: int, water: int, hop: int, yeast: int
) -> InlineKeyboardMarkup:
    """
    Возвращает инлайн-клавиатуру для интерактивного конфигурирования ингредиентов.
    """
    builder = InlineKeyboardBuilder()

    # Ингредиенты и их конфигурация кнопок
    ingredients = [
        ("malt", "🌾"),
        ("water", "💧"),
        ("hop", "🌿"),
        ("yeast", "🍞"),
    ]

    for key, emoji in ingredients:
        builder.row(
            InlineKeyboardButton(
                text=f"{emoji} -10%", callback_data=f"brew_mod:{key}:-10"
            ),
            InlineKeyboardButton(
                text="-1%", callback_data=f"brew_mod:{key}:-1"
            ),
            InlineKeyboardButton(text="+1%", callback_data=f"brew_mod:{key}:1"),
            InlineKeyboardButton(
                text="+10%", callback_data=f"brew_mod:{key}:10"
            ),
        )

    # Кнопка варки в зависимости от суммы
    total = malt + water + hop + yeast
    if total == 100:
        builder.row(
            InlineKeyboardButton(
                text="🍺 Сварить пиво!", callback_data="brew_action:start"
            )
        )
    else:
        builder.row(
            InlineKeyboardButton(
                text=f"⚠️ Баланс неверен (сейчас {total}%)",
                callback_data="brew_action:invalid",
            )
        )

    # Кнопка отмены
    builder.row(
        InlineKeyboardButton(text="❌ Отмена", callback_data="brew_action:cancel")
    )

    return builder.as_markup()
