from aiogram import Router, html
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.dal import CraftingDAL, InsufficientFundsError, PlayerDAL, PlayerNotFoundError

craft_router = Router()


@craft_router.message(Command("brew"))
async def cmd_brew(message: Message, session: AsyncSession) -> None:
    """
    Хэндлер команды /brew <M> <W> <H> <Y>.
    Выполняет синтаксическую валидацию пропорций ингредиентов,
    запрашивает данные активного алхимика игрока и запускает варку рецепта через DAL.
    """
    if not message.from_user:
        return

    if not message.text:
        return

    # Разбираем аргументы команды
    parts = message.text.split()
    args = parts[1:]

    # Валидация количества аргументов
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
            "⚠️ <b>Ошибка:</b> Каждое число должно быть в диапазоне от 0 до 100!", parse_mode="HTML"
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
        # Проверяем игрока
        player = await player_dal.get_player(tg_id)
    except PlayerNotFoundError:
        await message.answer(
            "⚠️ Вы не зарегистрированы в игре. Напишите /start, чтобы начать приключение!",
            parse_mode="HTML",
        )
        return

    # Запрашиваем активного сотрудника с ролью 'master_alchemist'
    staff = await player_dal.get_active_staff(player.player_id, "master_alchemist")
    if staff:
        skill = staff.skill
        fatigue = staff.fatigue
        staff_info = (
            f"🧙‍♂️ Алхимик: <b>{html.quote(staff.name)}</b> (Навык: {skill}, Усталость: {fatigue}%)"
        )
    else:
        skill = 1
        fatigue = 0
        staff_info = (
            "🧙‍♂️ Алхимик: отсутствует (используются параметры по умолчанию: skill=1, fatigue=0)"
        )

    try:
        # Запуск создания рецепта в DAL
        recipe = await crafting_dal.create_recipe(
            player.player_id, m, w, h, y, skill, fatigue, title="Экспериментальная варка"
        )
    except InsufficientFundsError as e:
        await message.answer(f"❌ <b>Ошибка списания:</b> {html.quote(str(e))}", parse_mode="HTML")
        return
    except ValueError as e:
        await message.answer(f"❌ <b>Ошибка валидации:</b> {html.quote(str(e))}", parse_mode="HTML")
        return

    # Красивый вывод результатов варки (аналогично BeerStatsDTO)
    text = (
        f"🍺 <b>Успешная варка рецепта!</b>\n"
        f"Название: «{html.quote(recipe.title)}»\n\n"
        f"🌾 Солод: {recipe.malt_pct}%\n"
        f"💧 Вода: {recipe.water_pct}%\n"
        f"🌿 Хмель: {recipe.hop_pct}%\n"
        f"🍞 Дрожжи: {recipe.yeast_pct}%\n\n"
        f"{staff_info}\n\n"
        f"📊 <b>Характеристики полученного пива:</b>\n"
        f"💪 Крепость: <b>{recipe.strength:.2f}%</b>\n"
        f"👅 Горечь: <b>{recipe.bitterness:.2f} IBU</b>\n"
        f"👃 Аромат: <b>{recipe.aroma:.2f} pts</b>\n"
        f"🛡️ Стабильность: <b>{recipe.stability}/100</b>\n"
    )
    await message.answer(text, parse_mode="HTML")
