from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from src.llm_engine.schemas import EventChoice


def get_nav_reply_keyboard() -> ReplyKeyboardMarkup:
    """
    Возвращает нативную reply-клавиатуру для постоянной навигации по 6 локациям.
    """
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="🍻 Моя Таверна"),
        KeyboardButton(text="🔥 Варочный Зал"),
        KeyboardButton(text="🏺 Тёмный Погреб"),
    )
    builder.row(
        KeyboardButton(text="⚖️ Торговая площадь"),
        KeyboardButton(text="🌑 Тёмный переулок"),
        KeyboardButton(text="🗺️ Ворота"),
    )
    return builder.as_markup(resize_keyboard=True)


def get_main_menu_keyboard(alerts: dict | None = None) -> InlineKeyboardMarkup:
    """
    Возвращает inline-клавиатуру главного меню с алертами и Летописью Мастера.
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
        InlineKeyboardButton(text="📜 Летопись Мастера", callback_data="screen:chronicle")
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


def get_welcome_keyboard() -> InlineKeyboardMarkup:
    """
    Клавиатура для приветственного экрана.
    """
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🍺 Войти в таверну", callback_data="tutorial:start")
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


def add_global_navigation_footer(
    keyboard: InlineKeyboardMarkup,
    back_callback: str | None = None
) -> InlineKeyboardMarkup:
    """
    Добавляет в инлайн-клавиатуру глобальный футер с кнопками [Назад] и [В меню].
    Если back_callback не передан, то кнопка [Назад] опускается, и выводится только [🏠 В меню].
    """
    new_grid = [row.copy() for row in keyboard.inline_keyboard]
    
    footer_row = []
    if back_callback:
        footer_row.append(InlineKeyboardButton(text="🔙 Назад", callback_data=back_callback))
    footer_row.append(InlineKeyboardButton(text="🏠 В меню", callback_data="screen:menu"))
    
    new_grid.append(footer_row)
    return InlineKeyboardMarkup(inline_keyboard=new_grid)

