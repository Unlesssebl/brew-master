from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from src.llm_engine.schemas import EventChoice


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """
    Возвращает inline-клавиатуру главного меню.
    """
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🍺 Варка", callback_data="screen:brewing"),
        InlineKeyboardButton(text="🏢 Здания", callback_data="screen:buildings"),
    )
    builder.row(
        InlineKeyboardButton(text="🎒 Инвентарь", callback_data="screen:inventory"),
        InlineKeyboardButton(text="👥 Персонал", callback_data="screen:staff"),
    )
    builder.row(
        InlineKeyboardButton(text="⛵ Экспедиции", callback_data="screen:expeditions")
    )
    return builder.as_markup()


def get_brewing_keyboard(
    malt: int, water: int, hops: int, yeast: int
) -> InlineKeyboardMarkup:
    """
    Возвращает inline-клавиатуру для настройки пропорций ингредиентов при варке.
    """
    builder = InlineKeyboardBuilder()

    ingredients = [
        ("malt", "🌾"),
        ("water", "💧"),
        ("hop", "🌿"),
        ("yeast", "🍞"),
    ]

    # Для совместимости с текущей логикой, в качестве аргумента hops
    # мы используем то же имя 'hop' в callback_data
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

    # Проверка баланса
    total = malt + water + hops + yeast
    if total == 100:
        builder.row(
            InlineKeyboardButton(
                text="🔥 Сварить!", callback_data="brew_action:start"
            )
        )
    else:
        builder.row(
            InlineKeyboardButton(
                text=f"⚠️ Баланс неверен (сейчас {total}%)",
                callback_data="brew_action:invalid",
            )
        )

    builder.row(
        InlineKeyboardButton(text="🔙 Назад в меню", callback_data="screen:menu")
    )

    return builder.as_markup()


def get_building_keyboard(building_type: str, level: str) -> InlineKeyboardMarkup:
    """
    Возвращает inline-клавиатуру для детального экрана здания.
    """
    builder = InlineKeyboardBuilder()

    # Кнопка апгрейда
    builder.row(
        InlineKeyboardButton(
            text="⬆️ Улучшить", callback_data=f"building:upgrade:{building_type}"
        )
    )

    # Для пивоварни добавляем ручную варку
    if building_type == "brewery":
        builder.row(
            InlineKeyboardButton(
                text="🔨 Сварить вручную", callback_data="building:brew_manual"
            )
        )

    builder.row(
        InlineKeyboardButton(
            text="🔙 Назад к зданиям", callback_data="screen:buildings"
        )
    )

    return builder.as_markup()


def get_event_choice_keyboard(choices: list[EventChoice]) -> InlineKeyboardMarkup:
    """
    Возвращает клавиатуру для выбора вариантов в событиях.
    """
    builder = InlineKeyboardBuilder()
    for choice in choices:
        builder.row(
            InlineKeyboardButton(
                text=choice.button_text,
                callback_data=f"event:choice:{choice.choice_id}",
            )
        )
    return builder.as_markup()
