from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from src.llm_engine.schemas import EventChoice


def get_main_menu_keyboard(alerts: dict | None = None) -> InlineKeyboardMarkup:
    """
    Возвращает inline-клавиатуру главного меню.
    """
    builder = InlineKeyboardBuilder()

    if alerts:
        if alerts.get("ready_batches", 0) > 0:
            builder.row(
                InlineKeyboardButton(
                    text=f"🟢 Собрать пиво ({alerts['ready_batches']} шт)",
                    callback_data="inventory:collect_ready",
                )
            )
        if alerts.get("tired_staff", 0) > 0:
            builder.row(
                InlineKeyboardButton(
                    text=f"⚠️ Рабочие устали ({alerts['tired_staff']} чел)",
                    callback_data="screen:staff",
                )
            )

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

    for key, emoji in ingredients:
        builder.row(
            InlineKeyboardButton(text=f"{emoji} -10%", callback_data=f"brew_mod:{key}:-10"),
            InlineKeyboardButton(text="-1%", callback_data=f"brew_mod:{key}:-1"),
            InlineKeyboardButton(text="+1%", callback_data=f"brew_mod:{key}:1"),
            InlineKeyboardButton(text="+10%", callback_data=f"brew_mod:{key}:10"),
        )

    total = malt + water + hops + yeast
    if total == 100:
        builder.row(InlineKeyboardButton(text="🔥 Сварить!", callback_data="brew_action:start"))
    else:
        builder.row(
            InlineKeyboardButton(
                text=f"⚠️ Баланс неверен ({total}%)",
                callback_data="brew_action:invalid",
            )
        )

    builder.row(
        InlineKeyboardButton(text="🔄 Слить всё (0%)", callback_data="brew_action:reset"),
        InlineKeyboardButton(text="🍺 Базовый Лагер", callback_data="brew_action:preset_lager"),
    )
    builder.row(InlineKeyboardButton(text="🔙 Назад в меню", callback_data="screen:menu"))
    return builder.as_markup()


def get_building_keyboard(building_type: str, level: str) -> InlineKeyboardMarkup:
    """
    Возвращает inline-клавиатуру для детального экрана здания.
    """
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⬆️ Улучшить", callback_data=f"building:upgrade:{building_type}"))

    if building_type == "brewery":
        builder.row(InlineKeyboardButton(text="🔨 Сварить вручную", callback_data="building:brew_manual"))

    builder.row(InlineKeyboardButton(text="🔙 Назад к зданиям", callback_data="screen:buildings"))
    return builder.as_markup()


def get_event_choice_keyboard(choices: list[EventChoice]) -> InlineKeyboardMarkup:
    """
    Возвращает клавиатуру для выбора вариантов в событиях.
    """
    builder = InlineKeyboardBuilder()
    for choice in choices:
        builder.row(
            InlineKeyboardButton(text=choice.button_text, callback_data=f"event:choice:{choice.choice_id}")
        )
    return builder.as_markup()


def get_tutorial_start_keyboard() -> InlineKeyboardMarkup:
    """
    Клавиатура для первого шага онбординга.
    """
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔥 Сварить тестовый эль", callback_data="tutorial:brew")
    )
    return builder.as_markup()
