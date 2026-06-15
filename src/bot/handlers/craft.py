from decimal import Decimal
from aiogram import F, Router, html
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.dal import (
    CraftingDAL,
    InsufficientFundsError,
    PlayerDAL,
    PlayerNotFoundError,
)
from src.database.models import Player, Staff, StaffRole
from src.bot.keyboards.inline import get_brewing_keyboard
from src.bot.states import BrewingStates
from .brewing import make_progress_bar, make_stat_bar, get_crafting_text

craft_router = Router()


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
        await state.set_state(BrewingStates.choosing_ingredients)
        await state.update_data(malt=25, water=25, hop=25, yeast=25)

        text = get_crafting_text(25, 25, 25, 25)
        await message.answer(
            text,
            parse_mode="HTML",
            reply_markup=get_brewing_keyboard(25, 25, 25, 25),
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
        int(player.player_id), "master_alchemist"
    )
    if staff:
        skill = int(staff.skill)
        fatigue = int(staff.fatigue)
        staff_info = f"🧙‍♂️ Алхимик: <b>{html.quote(str(staff.name))}</b> (Навык: {skill}, Усталость: {fatigue}%)"
    else:
        skill = 1
        fatigue = 0
        staff_info = "🧙‍♂️ Алхимик: отсутствует (используются параметры по умолчанию: skill=1, fatigue=0)"

    try:
        # Запуск создания рецепта в DAL
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

    recipe_title = str(recipe.title)
    recipe_malt = int(recipe.malt_pct)
    recipe_water = int(recipe.water_pct)
    recipe_hop = int(recipe.hop_pct)
    recipe_yeast = int(recipe.yeast_pct)
    recipe_strength = float(recipe.strength)
    recipe_bitterness = float(recipe.bitterness)
    recipe_aroma = float(recipe.aroma)
    recipe_stability = int(recipe.stability)

    # Красивый вывод результатов варки
    text = (
        f"🍺 <b>Успешная варка рецепта!</b>\n"
        f"Название: «{html.quote(recipe_title)}»\n\n"
        f"🌾 Солод: {recipe_malt}%  <code>[{make_progress_bar(recipe_malt)}]</code>\n"
        f"💧 Вода: {recipe_water}%  <code>[{make_progress_bar(recipe_water)}]</code>\n"
        f"🌿 Хмель: {recipe_hop}%  <code>[{make_progress_bar(recipe_hop)}]</code>\n"
        f"🍞 Дрожжи: {recipe_yeast}%  <code>[{make_progress_bar(recipe_yeast)}]</code>\n\n"
        f"{staff_info}\n\n"
        f"📊 <b>Характеристики полученного пива:</b>\n"
        f"💪 Крепость: <b>{recipe_strength:.2f}%</b>\n"
        f"<code>[{make_stat_bar(recipe_strength)}]</code>\n"
        f"👅 Горечь: <b>{recipe_bitterness:.2f} IBU</b>\n"
        f"<code>[{make_stat_bar(recipe_bitterness)}]</code>\n"
        f"👃 Аромат: <b>{recipe_aroma:.2f} pts</b>\n"
        f"<code>[{make_stat_bar(recipe_aroma)}]</code>\n"
        f"🛡️ Стабильность: <b>{recipe_stability}/100</b>\n"
        f"<code>[{make_progress_bar(recipe_stability)}]</code>\n"
    )
    await message.answer(text, parse_mode="HTML")
