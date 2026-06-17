from datetime import UTC, datetime
from decimal import Decimal
from aiogram import F, Router, html
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from aiogram.exceptions import TelegramBadRequest

from src.bot.keyboards.inline import get_brewing_keyboard, add_global_navigation_footer
from src.bot.states import BrewingStates, TutorialStates
from src.database.dal import (
    CraftingDAL,
    InsufficientFundsError,
    PlayerDAL,
    PlayerNotFoundError,
)
from src.database.models import Batch
from src.bot.utils.hud import send_or_edit_dashboard

brewing_router = Router()


def make_progress_bar(pct: int, length: int = 10) -> str:
    """
    Генерирует прогресс-бар из эмодзи.
    """
    filled = round((pct / 100) * length)
    filled = max(0, min(length, filled))
    return "🟩" * filled + "⬜" * (length - filled)


def make_stat_bar(val: float, max_val: float = 20.0, length: int = 10) -> str:
    """
    Генерирует прогресс-бар для характеристик пива (макс значение 20).
    """
    pct = (val / max_val) * 100 if max_val > 0 else 0
    return make_progress_bar(int(pct), length)


def get_crafting_text(malt: int, water: int, hop: int, yeast: int) -> str:
    """
    Формирует текст сообщения интерактивной варки.
    """
    total = malt + water + hop + yeast
    balance_status = "баланс соблюден" if total == 100 else "баланс нарушен"
    status_emoji = "⚙️" if total == 100 else "⚠️"

    text = (
        f"🍺 <b>Интерактивная варка пива</b>\n\n"
        f"Определите пропорции ингредиентов (сумма должна составлять ровно 100%):\n\n"
        f"💡 Подсказка: можно отправить 4 числа в чат, например <code>50 30 10 10</code>.\n\n"
        f"🌾 <b>Солод:</b> {malt}%  <code>[{make_progress_bar(malt)}]</code>\n"
        f"💧 <b>Вода:</b> {water}%  <code>[{make_progress_bar(water)}]</code>\n"
        f"🌿 <b>Хмель:</b> {hop}%  <code>[{make_progress_bar(hop)}]</code>\n"
        f"🍞 <b>Дрожжи:</b> {yeast}%  <code>[{make_progress_bar(yeast)}]</code>\n\n"
        f"{status_emoji} <b>Всего:</b> {total}% / 100% ({balance_status})"
    )
    return text


@brewing_router.callback_query(F.data == "screen:brewing")
@brewing_router.callback_query(F.data == "building:brew_manual")
async def start_brewing_callback(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    """
    Callback для запуска интерактивной варки.
    """
    if not callback.from_user or not callback.message or not isinstance(callback.message, Message):
        await callback.answer()
        return

    tg_id = callback.from_user.id
    player_dal = PlayerDAL(session)

    try:
        await player_dal.get_player(tg_id)
    except PlayerNotFoundError:
        await callback.answer("⚠️ Вы не зарегистрированы. Напишите /start", show_alert=True)
        return

    await state.set_state(BrewingStates.choosing_ingredients)
    await state.update_data(malt=25, water=25, hop=25, yeast=25)

    text = get_crafting_text(25, 25, 25, 25)
    player = await player_dal.get_player(tg_id)
    await send_or_edit_dashboard(
        bot=callback.bot,
        player=player,
        session=session,
        text=text,
        reply_markup=add_global_navigation_footer(get_brewing_keyboard(25, 25, 25, 25), back_callback="screen:brewery_hall")
    )
    await callback.answer()


@brewing_router.callback_query(
    BrewingStates.choosing_ingredients, F.data.startswith("brew_mod:")
)
async def process_brew_mod(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Обработчик кнопок изменения пропорций ингредиентов.
    """
    if not callback.message or not isinstance(callback.message, Message) or not callback.data:
        await callback.answer()
        return

    parts = callback.data.split(":")
    if len(parts) < 3:
        await callback.answer()
        return

    ingredient = parts[1]
    try:
        value = int(parts[2])
    except ValueError:
        await callback.answer()
        return

    data = await state.get_data()
    current_val = data.get(ingredient, 25)

    new_val = current_val + value
    new_val = max(0, min(100, new_val))

    # Типобезопасное обновление данных FSM
    new_data = dict(data)
    new_data[ingredient] = new_val
    await state.set_data(new_data)

    m = int(new_data.get("malt", 25))
    w = int(new_data.get("water", 25))
    h = int(new_data.get("hop", 25))
    y = int(new_data.get("yeast", 25))

    text = get_crafting_text(m, w, h, y)
    player = await PlayerDAL(session).get_player(callback.from_user.id)

    try:
        await send_or_edit_dashboard(
            bot=callback.bot,
            player=player,
            session=session,
            text=text,
            reply_markup=add_global_navigation_footer(get_brewing_keyboard(m, w, h, y), back_callback="screen:brewery_hall")
        )
    except TelegramBadRequest:
        pass

    await callback.answer()


@brewing_router.callback_query(
    BrewingStates.choosing_ingredients, F.data == "brew_action:invalid"
)
async def process_brew_invalid(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Обработчик клика по кнопке при неверном балансе ингредиентов.
    """
    data = await state.get_data()
    m = int(data.get("malt", 25))
    w = int(data.get("water", 25))
    h = int(data.get("hop", 25))
    y = int(data.get("yeast", 25))
    total = m + w + h + y
    await callback.answer(
        f"⚠️ Сумма ингредиентов должна быть ровно 100%! Сейчас: {total}%",
        show_alert=True,
    )


@brewing_router.callback_query(F.data == "tutorial:brew")
async def process_tutorial_brew(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    """
    Запускает тестовую варку для первого шага обучения.
    """
    if not callback.from_user or not callback.message or not isinstance(callback.message, Message):
        await callback.answer()
        return

    tg_id = callback.from_user.id
    player_dal = PlayerDAL(session)
    crafting_dal = CraftingDAL(session)

    try:
        player = await player_dal.get_player(tg_id)
    except PlayerNotFoundError:
        await callback.answer("Профиль не найден. Напишите /start", show_alert=True)
        return

    if player.tutorial_step >= 1:
        await state.set_state(TutorialStates.first_collect)
        await callback.answer("Тестовая варка уже завершена.")
        return

    recipe = await crafting_dal.create_recipe(
        int(player.player_id),
        25,
        25,
        25,
        25,
        skill=1,
        fatigue=0,
        title="Тестовый базовый эль",
    )

    batch = Batch(
        player_id=int(player.player_id),
        recipe_id=int(recipe.recipe_id),
        quantity_barrels=3,
        quality_modifier=Decimal("1.00"),
        is_completed=False,
        ready_at=datetime.now(UTC),
    )
    session.add(batch)
    await session.flush()
    await player_dal.update_tutorial_step(tg_id, 1)
    await state.set_state(TutorialStates.first_collect)

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🟢 Собрать пиво", callback_data="inventory:collect_ready"))

    await callback.message.edit_text(
        "🔥 <b>Тестовый эль сварен!</b>\n\n"
        "Первая партия готова к сбору: <code>3 бочки</code>.\n"
        "Следующий шаг — собери ее, чтобы перенести пиво на склад.",
        parse_mode="HTML",
        reply_markup=builder.as_markup(),
    )
    await callback.answer("Тестовая варка готова!")


@brewing_router.callback_query(
    BrewingStates.choosing_ingredients, F.data == "brew_action:reset"
)
async def process_brew_reset(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Сбрасывает все ингредиенты в 0.
    """
    if not callback.message or not isinstance(callback.message, Message):
        await callback.answer()
        return

    await state.update_data(malt=0, water=0, hop=0, yeast=0)
    text = get_crafting_text(0, 0, 0, 0)
    player = await PlayerDAL(session).get_player(callback.from_user.id)
    await send_or_edit_dashboard(
        bot=callback.bot,
        player=player,
        session=session,
        text=text,
        reply_markup=add_global_navigation_footer(get_brewing_keyboard(0, 0, 0, 0), back_callback="screen:brewery_hall")
    )
    await callback.answer("Чан пуст!")


@brewing_router.callback_query(
    BrewingStates.choosing_ingredients, F.data == "brew_action:preset_lager"
)
async def process_brew_preset(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Заполняет чан по рецепту Лагера.
    """
    if not callback.message or not isinstance(callback.message, Message):
        await callback.answer()
        return

    await state.update_data(malt=60, water=20, hop=15, yeast=5)
    text = get_crafting_text(60, 20, 15, 5)
    player = await PlayerDAL(session).get_player(callback.from_user.id)
    await send_or_edit_dashboard(
        bot=callback.bot,
        player=player,
        session=session,
        text=text,
        reply_markup=add_global_navigation_footer(get_brewing_keyboard(60, 20, 15, 5), back_callback="screen:brewery_hall")
    )
    await callback.answer("Рецепт загружен!")


@brewing_router.callback_query(
    BrewingStates.choosing_ingredients, F.data == "brew_action:start"
)
async def process_brew_start(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    """
    Обработчик запуска варки пива при достижении баланса в 100%.
    """
    if not callback.from_user or not callback.message or not isinstance(callback.message, Message):
        await callback.answer()
        return

    data = await state.get_data()
    m = int(data.get("malt", 25))
    w = int(data.get("water", 25))
    h = int(data.get("hop", 25))
    y = int(data.get("yeast", 25))

    if m + w + h + y != 100:
        await callback.answer(
            f"⚠️ Ошибка: Сумма ингредиентов должна быть ровно 100%! Сейчас: {m + w + h + y}%",
            show_alert=True,
        )
        return

    tg_id = callback.from_user.id
    player_dal = PlayerDAL(session)
    crafting_dal = CraftingDAL(session)

    try:
        player = await player_dal.get_player(tg_id)
    except PlayerNotFoundError:
        await callback.message.edit_text(
            "⚠️ Вы не зарегистрированы в игре. Напишите /start, чтобы начать приключение!",
            parse_mode="HTML",
        )
        await state.clear()
        await callback.answer()
        return

    staff = await player_dal.get_active_staff(
        int(player.player_id), "master_alchemist"
    )
    if staff:
        skill = int(staff.skill)
        fatigue = int(staff.fatigue)
        staff_info = f"🧙‍♂️ Алхимик: <b>{html.quote(str(staff.name))}</b> (Навык: {skill}, Усталость: {fatigue}%)"
        staff.fatigue = min(100, fatigue + 10)
    else:
        skill = 1
        fatigue = 0
        staff_info = "🧙‍♂️ Алхимик: отсутствует (используются параметры по умолчанию: skill=1, fatigue=0)"

    try:
        recipe = await crafting_dal.create_recipe(
            int(player.player_id),
            m,
            w,
            h,
            y,
            skill,
            fatigue,
            title="Экспериментальная варка",
        )
    except InsufficientFundsError as e:
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="🔙 Назад в меню", callback_data="screen:menu"))
        await callback.message.edit_text(
            f"❌ <b>Ошибка списания:</b> {html.quote(str(e))}",
            parse_mode="HTML",
            reply_markup=builder.as_markup(),
        )
        await state.clear()
        await callback.answer()
        return
    except ValueError as e:
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="🔙 Назад в меню", callback_data="screen:menu"))
        await callback.message.edit_text(
            f"❌ <b>Ошибка валидации:</b> {html.quote(str(e))}",
            parse_mode="HTML",
            reply_markup=builder.as_markup(),
        )
        await state.clear()
        await callback.answer()
        return

    text = (
        f"🍺 <b>Успешная варка рецепта!</b>\n"
        f"Название: «{html.quote(str(recipe.title))}»\n\n"
        f"🌾 Солод: {int(recipe.malt_pct)}%  <code>[{make_progress_bar(int(recipe.malt_pct))}]</code>\n"
        f"💧 Вода: {int(recipe.water_pct)}%  <code>[{make_progress_bar(int(recipe.water_pct))}]</code>\n"
        f"🌿 Хмель: {int(recipe.hop_pct)}%  <code>[{make_progress_bar(int(recipe.hop_pct))}]</code>\n"
        f"🍞 Дрожжи: {int(recipe.yeast_pct)}%  <code>[{make_progress_bar(int(recipe.yeast_pct))}]</code>\n\n"
        f"{staff_info}\n\n"
        f"📊 <b>Характеристики полученного пива:</b>\n"
        f"💪 Крепость: <b>{recipe.strength:.2f}%</b>\n"
        f"<code>[{make_stat_bar(float(recipe.strength))}]</code>\n"
        f"👅 Горечь: <b>{recipe.bitterness:.2f} IBU</b>\n"
        f"<code>[{make_stat_bar(float(recipe.bitterness))}]</code>\n"
        f"👃 Аромат: <b>{recipe.aroma:.2f} pts</b>\n"
        f"<code>[{make_stat_bar(float(recipe.aroma))}]</code>\n"
        f"🛡️ Стабильность: <b>{int(recipe.stability)}/100</b>\n"
        f"<code>[{make_progress_bar(int(recipe.stability))}]</code>\n"
    )

    builder = InlineKeyboardBuilder()

    await send_or_edit_dashboard(
        bot=callback.bot,
        player=player,
        session=session,
        text=text,
        reply_markup=add_global_navigation_footer(builder.as_markup(), back_callback="screen:brewery_hall")
    )
    await state.clear()
    await callback.answer("Пиво сварено!")


@brewing_router.message(BrewingStates.choosing_ingredients, F.text)
async def process_text_brew_input(message: Message, state: FSMContext, session: AsyncSession) -> None:
    """
    Перехватывает текстовый ввод ингредиентов, например: "40 40 10 10".
    """
    if not message.text:
        return

    parts = message.text.split()
    if len(parts) != 4:
        await message.answer(
            "⚠️ Пожалуйста, введите ровно 4 числа через пробел "
            "(солод, вода, хмель, дрожжи).\n"
            "Например: <code>40 40 10 10</code>",
            parse_mode="HTML",
        )
        return

    try:
        m, w, h, y = map(int, parts)
    except ValueError:
        await message.answer("⚠️ Все значения должны быть числами!")
        return

    if m < 0 or w < 0 or h < 0 or y < 0:
        await message.answer("⚠️ Значения не могут быть отрицательными.")
        return

    await state.update_data(malt=m, water=w, hop=h, yeast=y)

    text = get_crafting_text(m, w, h, y)
    player = await PlayerDAL(session).get_player(message.from_user.id)
    await send_or_edit_dashboard(
        bot=message.bot,
        player=player,
        session=session,
        text="✅ Пропорции приняты!\n\n" + text,
        reply_markup=add_global_navigation_footer(get_brewing_keyboard(m, w, h, y), back_callback="screen:brewery_hall"),
        force_new=True
    )


# Оставляем cmd_brew для ручного вызова через текст (совместимость с тестами)
@brewing_router.message(Command("brew"))
async def cmd_brew(
    message: Message, session: AsyncSession, state: FSMContext | None = None
) -> None:
    """
    Текстовая команда /brew (поддержка CLI-аргументов для тестов).
    """
    if not message.from_user:
        return

    args = []
    if message.text and message.text.startswith("/brew"):
        parts = message.text.split()
        args = parts[1:]

    # Если аргументов нет, запускаем интерактивную варку в чате
    if len(args) == 0:
        if state is None:
            await message.answer("⚠️ Ошибка: невозможно запустить интерактивный режим без FSM.")
            return

        tg_id = message.from_user.id
        player_dal = PlayerDAL(session)

        try:
            player = await player_dal.get_player(tg_id)
        except PlayerNotFoundError:
            await message.answer("⚠️ Вы не зарегистрированы. Напишите /start")
            return

        await state.set_state(BrewingStates.choosing_ingredients)
        await state.update_data(malt=25, water=25, hop=25, yeast=25)

        text = get_crafting_text(25, 25, 25, 25)
        await send_or_edit_dashboard(
            bot=message.bot,
            player=player,
            session=session,
            text=text,
            reply_markup=add_global_navigation_footer(get_brewing_keyboard(25, 25, 25, 25), back_callback="screen:brewery_hall"),
            force_new=True
        )
        return

    # Валидация аргументов для быстрого режима
    if len(args) != 4:
        await message.answer(
            "⚠️ <b>Ошибка:</b> Неверное количество аргументов!\n"
            "Использование: <code>/brew &lt;солод&gt; &lt;вода&gt; &lt;хмель&gt; &lt;дрожжи&gt;</code>",
            parse_mode="HTML",
        )
        return

    try:
        m, w, h, y = map(int, args)
    except ValueError:
        await message.answer("⚠️ <b>Ошибка:</b> Все аргументы должны быть целыми числами!")
        return

    if not all(0 <= val <= 100 for val in (m, w, h, y)) or m + w + h + y != 100:
        await message.answer("⚠️ <b>Ошибка:</b> Сумма ингредиентов должна быть равна 100%!")
        return

    tg_id = message.from_user.id
    player_dal = PlayerDAL(session)
    crafting_dal = CraftingDAL(session)

    try:
        player = await player_dal.get_player(tg_id)
    except PlayerNotFoundError:
        await message.answer("⚠️ Вы не зарегистрированы.")
        return

    staff = await player_dal.get_active_staff(int(player.player_id), "master_alchemist")
    if staff:
        skill = int(staff.skill)
        fatigue = int(staff.fatigue)
        staff_info = f"🧙‍♂️ Алхимик: <b>{html.quote(str(staff.name))}</b>"
    else:
        skill = 1
        fatigue = 0
        staff_info = "🧙‍♂️ Алхимик: отсутствует"

    try:
        recipe = await crafting_dal.create_recipe(
            int(player.player_id), m, w, h, y, skill, fatigue, title="Экспериментальная варка"
        )
    except InsufficientFundsError as e:
        await message.answer(f"❌ <b>Ошибка списания:</b> {html.quote(str(e))}", parse_mode="HTML")
        return
    except ValueError as e:
        await message.answer(f"❌ <b>Ошибка:</b> {html.quote(str(e))}", parse_mode="HTML")
        return

    text = (
        f"🍺 <b>Успешная варка рецепта!</b>\n"
        f"Название: «{html.quote(str(recipe.title))}»\n\n"
        f"🌾 Солод: {int(recipe.malt_pct)}%  <code>[{make_progress_bar(int(recipe.malt_pct))}]</code>\n"
        f"💧 Вода: {int(recipe.water_pct)}%  <code>[{make_progress_bar(int(recipe.water_pct))}]</code>\n"
        f"🌿 Хмель: {int(recipe.hop_pct)}%  <code>[{make_progress_bar(int(recipe.hop_pct))}]</code>\n"
        f"🍞 Дрожжи: {int(recipe.yeast_pct)}%  <code>[{make_progress_bar(int(recipe.yeast_pct))}]</code>\n\n"
        f"{staff_info}\n\n"
        f"📊 <b>Характеристики полученного пива:</b>\n"
        f"💪 Крепость: <b>{recipe.strength:.2f}%</b>\n"
        f"👅 Горечь: <b>{recipe.bitterness:.2f} IBU</b>\n"
        f"👃 Аромат: <b>{recipe.aroma:.2f} pts</b>\n"
        f"🛡️ Стабильность: <b>{int(recipe.stability)}/100</b>\n"
    )
    
    builder = InlineKeyboardBuilder()
    await send_or_edit_dashboard(
        bot=message.bot,
        player=player,
        session=session,
        text=text,
        reply_markup=add_global_navigation_footer(builder.as_markup(), back_callback="screen:brewery_hall"),
        force_new=True
    )
