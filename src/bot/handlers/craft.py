from aiogram import F, Router, html
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.keyboards import get_crafting_keyboard
from src.database.dal import (
    CraftingDAL,
    InsufficientFundsError,
    PlayerDAL,
    PlayerNotFoundError,
)

craft_router = Router()


class CraftingStates(StatesGroup):
    choosing_ingredients = State()


def make_progress_bar(pct: int, length: int = 10) -> str:
    """
    Генерирует прогресс-бар из эмодзи.
    """
    filled = round((pct / 100) * length)
    # Ограничиваем в диапазоне [0, length]
    filled = max(0, min(length, filled))
    return "🟩" * filled + "⬜" * (length - filled)


def make_stat_bar(val: float, max_val: float = 20.0, length: int = 10) -> str:
    """
    Генерирует прогресс-бар для характеристик пива (по умолчанию макс значение 20).
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
        f"🌾 <b>Солод:</b> {malt}%  <code>[{make_progress_bar(malt)}]</code>\n"
        f"💧 <b>Вода:</b> {water}%  <code>[{make_progress_bar(water)}]</code>\n"
        f"🌿 <b>Хмель:</b> {hop}%  <code>[{make_progress_bar(hop)}]</code>\n"
        f"🍞 <b>Дрожжи:</b> {yeast}%  <code>[{make_progress_bar(yeast)}]</code>\n\n"
        f"{status_emoji} <b>Всего:</b> {total}% / 100% ({balance_status})"
    )
    return text


@craft_router.message(Command("brew"))
@craft_router.message(F.text == "🍺 Сварить пиво")
async def cmd_brew(
    message: Message, session: AsyncSession, state: FSMContext | None = None
) -> None:
    """
    Хэндлер команды /brew и кнопки "🍺 Сварить пиво".
    Если аргументы отсутствуют, запускает интерактивный режим.
    Иначе выполняет синтаксическую валидацию пропорций и делает быструю варку.
    """
    if not message.from_user:
        return

    # Разбираем аргументы команды
    args = []
    if message.text and message.text.startswith("/brew"):
        parts = message.text.split()
        args = parts[1:]

    # Интерактивный режим
    if len(args) == 0:
        if state is None:
            await message.answer(
                "⚠️ Ошибка: невозможно запустить интерактивный режим без FSM контекста.",
                parse_mode="HTML",
            )
            return

        tg_id = message.from_user.id
        player_dal = PlayerDAL(session)

        try:
            # Проверяем игрока
            await player_dal.get_player(tg_id)
        except PlayerNotFoundError:
            await message.answer(
                "⚠️ Вы не зарегистрированы в игре. Напишите /start, чтобы начать приключение!",
                parse_mode="HTML",
            )
            return

        # Инициализируем стейт
        await state.set_state(CraftingStates.choosing_ingredients)
        await state.update_data(malt=25, water=25, hop=25, yeast=25)

        text = get_crafting_text(25, 25, 25, 25)
        await message.answer(
            text,
            parse_mode="HTML",
            reply_markup=get_crafting_keyboard(25, 25, 25, 25),
        )
        return

    # Валидация количества аргументов для классического ручного режима
    if len(args) != 4:
        await message.answer(
            "⚠️ <b>Ошибка:</b> Неверное количество аргументов!\n"
            "Использование: <code>/brew &lt;солод&gt; &lt;вода&gt; &lt;хмель&gt; &lt;дрожжи&gt;</code>\n"
            "Пример: <code>/brew 50 30 10 10</code>",
            parse_mode="HTML",
        )
        return

    # Валидация типов
    try:
        m, w, h, y = map(int, args)
    except ValueError:
        await message.answer(
            "⚠️ <b>Ошибка:</b> Все аргументы должны быть целыми числами в диапазоне от 0 до 100!",
            parse_mode="HTML",
        )
        return

    # Валидация диапазонов
    if not all(0 <= val <= 100 for val in (m, w, h, y)):
        await message.answer(
            "⚠️ <b>Ошибка:</b> Каждое число должно быть в диапазоне от 0 до 100!",
            parse_mode="HTML",
        )
        return

    # Валидация суммы
    if m + w + h + y != 100:
        await message.answer(
            "⚠️ <b>Ошибка:</b> Сумма всех четырех ингредиентов должна быть строго равна 100%!",
            parse_mode="HTML",
        )
        return

    tg_id = message.from_user.id
    player_dal = PlayerDAL(session)
    crafting_dal = CraftingDAL(session)

    try:
        player = await player_dal.get_player(tg_id)
    except PlayerNotFoundError:
        await message.answer(
            "⚠️ Вы не зарегистрированы в игре. Напишите /start, чтобы начать приключение!",
            parse_mode="HTML",
        )
        return

    # Запрашиваем активного сотрудника с ролью 'master_alchemist'
    staff = await player_dal.get_active_staff(
        player.player_id, "master_alchemist"
    )
    if staff:
        skill = staff.skill
        fatigue = staff.fatigue
        staff_info = f"🧙‍♂️ Алхимик: <b>{html.quote(staff.name)}</b> (Навык: {skill}, Усталость: {fatigue}%)"
    else:
        skill = 1
        fatigue = 0
        staff_info = "🧙‍♂️ Алхимик: отсутствует (используются параметры по умолчанию: skill=1, fatigue=0)"

    try:
        # Запуск создания рецепта в DAL
        recipe = await crafting_dal.create_recipe(
            player.player_id,
            m,
            w,
            h,
            y,
            skill,
            fatigue,
            title="Экспериментальная варка",
        )
    except InsufficientFundsError as e:
        await message.answer(
            f"❌ <b>Ошибка списания:</b> {html.quote(str(e))}",
            parse_mode="HTML",
        )
        return
    except ValueError as e:
        await message.answer(
            f"❌ <b>Ошибка валидации:</b> {html.quote(str(e))}",
            parse_mode="HTML",
        )
        return

    # Красивый вывод результатов варки
    text = (
        f"🍺 <b>Успешная варка рецепта!</b>\n"
        f"Название: «{html.quote(recipe.title)}»\n\n"
        f"🌾 Солод: {recipe.malt_pct}%  <code>[{make_progress_bar(recipe.malt_pct)}]</code>\n"
        f"💧 Вода: {recipe.water_pct}%  <code>[{make_progress_bar(recipe.water_pct)}]</code>\n"
        f"🌿 Хмель: {recipe.hop_pct}%  <code>[{make_progress_bar(recipe.hop_pct)}]</code>\n"
        f"🍞 Дрожжи: {recipe.yeast_pct}%  <code>[{make_progress_bar(recipe.yeast_pct)}]</code>\n\n"
        f"{staff_info}\n\n"
        f"📊 <b>Характеристики полученного пива:</b>\n"
        f"💪 Крепость: <b>{recipe.strength:.2f}%</b>\n"
        f"<code>[{make_stat_bar(float(recipe.strength))}]</code>\n"
        f"👅 Горечь: <b>{recipe.bitterness:.2f} IBU</b>\n"
        f"<code>[{make_stat_bar(float(recipe.bitterness))}]</code>\n"
        f"👃 Аромат: <b>{recipe.aroma:.2f} pts</b>\n"
        f"<code>[{make_stat_bar(float(recipe.aroma))}]</code>\n"
        f"🛡️ Стабильность: <b>{recipe.stability}/100</b>\n"
        f"<code>[{make_progress_bar(recipe.stability)}]</code>\n"
    )
    await message.answer(text, parse_mode="HTML")


@craft_router.callback_query(
    CraftingStates.choosing_ingredients, F.data.startswith("brew_mod:")
)
async def process_brew_mod(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Обработчик кнопок изменения пропорций ингредиентов.
    """
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

    await state.update_data(**{ingredient: new_val})

    data = await state.get_data()
    m = data.get("malt", 25)
    w = data.get("water", 25)
    h = data.get("hop", 25)
    y = data.get("yeast", 25)

    text = get_crafting_text(m, w, h, y)

    from aiogram.exceptions import TelegramBadRequest

    try:
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=get_crafting_keyboard(m, w, h, y),
        )
    except TelegramBadRequest:
        pass

    await callback.answer()


@craft_router.callback_query(
    CraftingStates.choosing_ingredients, F.data == "brew_action:invalid"
)
async def process_brew_invalid(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Обработчик клика по кнопке при неверном балансе ингредиентов.
    """
    data = await state.get_data()
    m = data.get("malt", 25)
    w = data.get("water", 25)
    h = data.get("hop", 25)
    y = data.get("yeast", 25)
    total = m + w + h + y
    await callback.answer(
        f"⚠️ Сумма ингредиентов должна быть ровно 100%! Сейчас: {total}%",
        show_alert=True,
    )


@craft_router.callback_query(
    CraftingStates.choosing_ingredients, F.data == "brew_action:cancel"
)
async def process_brew_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Обработчик отмены процесса варки.
    """
    await state.clear()
    await callback.message.edit_text("❌ Варка пива отменена.")
    await callback.answer("Варка отменена")


@craft_router.callback_query(
    CraftingStates.choosing_ingredients, F.data == "brew_action:start"
)
async def process_brew_start(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    """
    Обработчик запуска варки пива при достижении баланса в 100%.
    """
    if not callback.from_user:
        await callback.answer()
        return

    data = await state.get_data()
    m = data.get("malt", 25)
    w = data.get("water", 25)
    h = data.get("hop", 25)
    y = data.get("yeast", 25)

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
        await callback.message.answer(
            "⚠️ Вы не зарегистрированы в игре. Напишите /start, чтобы начать приключение!",
            parse_mode="HTML",
        )
        await state.clear()
        await callback.answer()
        return

    staff = await player_dal.get_active_staff(
        player.player_id, "master_alchemist"
    )
    if staff:
        skill = staff.skill
        fatigue = staff.fatigue
        staff_info = f"🧙‍♂️ Алхимик: <b>{html.quote(staff.name)}</b> (Навык: {skill}, Усталость: {fatigue}%)"
    else:
        skill = 1
        fatigue = 0
        staff_info = "🧙‍♂️ Алхимик: отсутствует (используются параметры по умолчанию: skill=1, fatigue=0)"

    try:
        recipe = await crafting_dal.create_recipe(
            player.player_id,
            m,
            w,
            h,
            y,
            skill,
            fatigue,
            title="Экспериментальная варка",
        )
    except InsufficientFundsError as e:
        await callback.message.answer(
            f"❌ <b>Ошибка списания:</b> {html.quote(str(e))}",
            parse_mode="HTML",
        )
        await state.clear()
        await callback.answer()
        return
    except ValueError as e:
        await callback.message.answer(
            f"❌ <b>Ошибка валидации:</b> {html.quote(str(e))}",
            parse_mode="HTML",
        )
        await state.clear()
        await callback.answer()
        return

    text = (
        f"🍺 <b>Успешная варка рецепта!</b>\n"
        f"Название: «{html.quote(recipe.title)}»\n\n"
        f"🌾 Солод: {recipe.malt_pct}%  <code>[{make_progress_bar(recipe.malt_pct)}]</code>\n"
        f"💧 Вода: {recipe.water_pct}%  <code>[{make_progress_bar(recipe.water_pct)}]</code>\n"
        f"🌿 Хмель: {recipe.hop_pct}%  <code>[{make_progress_bar(recipe.hop_pct)}]</code>\n"
        f"🍞 Дрожжи: {recipe.yeast_pct}%  <code>[{make_progress_bar(recipe.yeast_pct)}]</code>\n\n"
        f"{staff_info}\n\n"
        f"📊 <b>Характеристики полученного пива:</b>\n"
        f"💪 Крепость: <b>{recipe.strength:.2f}%</b>\n"
        f"<code>[{make_stat_bar(float(recipe.strength))}]</code>\n"
        f"👅 Горечь: <b>{recipe.bitterness:.2f} IBU</b>\n"
        f"<code>[{make_stat_bar(float(recipe.bitterness))}]</code>\n"
        f"👃 Аромат: <b>{recipe.aroma:.2f} pts</b>\n"
        f"<code>[{make_stat_bar(float(recipe.aroma))}]</code>\n"
        f"🛡️ Стабильность: <b>{recipe.stability}/100</b>\n"
        f"<code>[{make_progress_bar(recipe.stability)}]</code>\n"
    )

    try:
        await callback.message.delete()
    except TelegramBadRequest:
        pass

    await callback.message.answer(text, parse_mode="HTML")
    await state.clear()
    await callback.answer("Пиво сварено!")
