import asyncio
import logging
from datetime import datetime, UTC, timedelta
from decimal import Decimal
from typing import cast
from aiogram import F, Router, html, Bot
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton, BufferedInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.dal import PlayerDAL, CraftingDAL, InsufficientFundsError, PlayerNotFoundError
from src.database.models import Recipe, Batch, Patent
from src.database.connection import async_session_factory
from src.bot.utils.hud import update_hud
from src.bot.utils.formatters import get_tavern_name
from src.llm_engine.generator import LLMPatentLoreGenerator
from src.llm_engine.api_client import generate_patent_image

logger = logging.getLogger(__name__)
brewery_hall_router = Router()


@brewery_hall_router.callback_query(F.data == "screen:brewery_hall")
async def show_brewery_hall(callback: CallbackQuery, session: AsyncSession) -> None:
    """
    Экран "Варочный Зал".
    """
    if not callback.from_user or not callback.message or not isinstance(callback.message, Message):
        await callback.answer()
        return

    tg_id = callback.from_user.id
    player_dal = PlayerDAL(session)

    try:
        player = await player_dal.get_player(tg_id)
        t_name = get_tavern_name(cast(int, player.reputation))

        text = (
            f"🔥 <b>Варочный Зал таверны «{t_name}»</b>\n\n"
            f"Здесь кипит работа! Пар валит из медных котлов, а воздух пропитан запахом хмеля и солода.\n\n"
            f"Выберите режим работы:\n"
            f"🧪 <b>Экспериментально</b> — создать новый рецепт, настраивая пропорции ингредиентов.\n"
            f"📋 <b>Серийно</b> — сварить 10 бочек пива по одному из ваших готовых рецептов.\n"
            f"📜 <b>Патентное бюро</b> — зарегистрировать патент на уникальный рецепт пива."
        )

        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="🧪 Экспериментально", callback_data="screen:brewing")
        )
        builder.row(
            InlineKeyboardButton(text="📋 Серийно из рецепта", callback_data="brewery_hall:serial_list")
        )
        builder.row(
            InlineKeyboardButton(text="📜 Патентное бюро", callback_data="brewery_hall:patent_bureau")
        )
        builder.row(
            InlineKeyboardButton(text="🔙 Вернуться в город", callback_data="screen:menu")
        )

        await callback.message.edit_text(
            text, parse_mode="HTML", reply_markup=builder.as_markup()
        )

        # Обновляем HUD
        await update_hud(callback.bot, player, session)

    except PlayerNotFoundError:
        await callback.answer("Профиль не найден.", show_alert=True)
    await callback.answer()


@brewery_hall_router.callback_query(F.data == "brewery_hall:serial_list")
async def show_serial_list(callback: CallbackQuery, session: AsyncSession) -> None:
    """
    Показывает список рецептов для серийной варки.
    """
    if not callback.from_user or not callback.message or not isinstance(callback.message, Message):
        await callback.answer()
        return

    tg_id = callback.from_user.id
    player_dal = PlayerDAL(session)

    try:
        player = await player_dal.get_player(tg_id)
        
        # Получаем рецепты игрока
        stmt = select(Recipe).where(Recipe.creator_id == cast(int, player.player_id)).order_by(Recipe.created_at.desc())
        res = await session.execute(stmt)
        recipes = res.scalars().all()

        text = "📋 <b>Серийная варка пива (10 бочек)</b>\n\n"
        
        builder = InlineKeyboardBuilder()

        if recipes:
            text += "Выберите рецепт для варки партии:\n\n"
            for r in recipes:
                # Посчитаем необходимые ресурсы для 10 бочек (процент ресурса = количество кг/л)
                text += (
                    f"• <b>«{html.quote(cast(str, r.title))}»</b>\n"
                    f"  💪 Крепость: <code>{r.strength:.1f}%</code> | 👅 Горечь: <code>{r.bitterness:.1f}</code> | 👃 Аромат: <code>{r.aroma:.1f}</code>\n"
                    f"  🌾 {r.malt_pct}кг | 💧 {r.water_pct}л | 🌿 {r.hop_pct}кг | 🍞 {r.yeast_pct}кг\n\n"
                )
                builder.row(
                    InlineKeyboardButton(
                        text=f"🔥 Сварить «{r.title}»",
                        callback_data=f"brewery_hall:serial_brew:{r.recipe_id}"
                    )
                )
        else:
            text += "У вас пока нет сохраненных рецептов. Сварите пиво в экспериментальном режиме!\n"

        builder.row(
            InlineKeyboardButton(text="🔙 Назад в зал", callback_data="screen:brewery_hall")
        )

        await callback.message.edit_text(
            text, parse_mode="HTML", reply_markup=builder.as_markup()
        )
    except PlayerNotFoundError:
        await callback.answer("Профиль не найден.", show_alert=True)
    await callback.answer()


@brewery_hall_router.callback_query(F.data.startswith("brewery_hall:serial_brew:"))
async def process_serial_brew(callback: CallbackQuery, session: AsyncSession) -> None:
    """
    Запускает серийную варку выбранного рецепта.
    """
    if not callback.from_user or not callback.message or not isinstance(callback.message, Message) or not callback.data:
        await callback.answer()
        return

    recipe_id = int(callback.data.split(":")[2])
    tg_id = callback.from_user.id
    player_dal = PlayerDAL(session)

    try:
        player = await player_dal.get_player(tg_id)
        
        # Получаем рецепт
        stmt = select(Recipe).where(Recipe.recipe_id == recipe_id)
        res = await session.execute(stmt)
        recipe = res.scalar_one_or_none()

        if not recipe:
            await callback.answer("Рецепт не найден.", show_alert=True)
            return

        # Проверяем и списываем ресурсы (пропорции * 1 = единицы ресурсов на партию 10 бочек)
        req_resources = {
            "malt": Decimal(cast(int, recipe.malt_pct)),
            "water": Decimal(cast(int, recipe.water_pct)),
            "hops": Decimal(cast(int, recipe.hop_pct)),
            "yeast": Decimal(cast(int, recipe.yeast_pct)),
        }

        try:
            await player_dal.use_resources(cast(int, player.player_id), req_resources)
        except InsufficientFundsError:
            # Получаем текущие ресурсы для информирования
            curr_res = await player_dal.get_resources(cast(int, player.player_id))
            await callback.answer(
                f"❌ Недостаточно ресурсов для варки!\n"
                f"Требуется: 🌾{recipe.malt_pct}кг, 💧{recipe.water_pct}л, 🌿{recipe.hop_pct}кг, 🍞{recipe.yeast_pct}кг.\n"
                f"У вас: 🌾{curr_res.get('malt', 0):.1f}, 💧{curr_res.get('water', 0):.1f}, 🌿{curr_res.get('hops', 0):.1f}, 🍞{curr_res.get('yeast', 0):.1f}",
                show_alert=True
            )
            return

        # Получаем мастера-алхимика
        staff = await player_dal.get_active_staff(cast(int, player.player_id), "master_alchemist")
        if staff:
            skill = cast(int, staff.skill)
            fatigue = cast(int, staff.fatigue)
            staff.fatigue = min(100, fatigue + 10)
            staff_info = f"🧙‍♂️ Варкой руководил: <b>{html.quote(cast(str, staff.name))}</b> (навык увеличил качество)"
        else:
            skill = 1
            fatigue = 0
            staff_info = "🧙‍♂️ Варка прошла без мастера (качество базовое)"

        # Проверим активный дебафф "inspection"
        from src.database.models import PlayerEventLog
        stmt_debuff = select(PlayerEventLog).where(
            PlayerEventLog.player_id == cast(int, player.player_id),
            PlayerEventLog.event_type == "pvp_debuff_received"
        ).order_by(PlayerEventLog.created_at.desc()).limit(1)
        res_debuff = await session.execute(stmt_debuff)
        last_debuff = res_debuff.scalar_one_or_none()

        debuff_multiplier = Decimal("1.0")
        debuff_alert = ""
        if last_debuff:
            meta = last_debuff.metadata_json or {}
            if meta.get("debuff") == "inspection":
                expires_str = meta.get("expires_at")
                if expires_str:
                    expires = datetime.fromisoformat(expires_str)
                    if expires.tzinfo is None:
                        expires = expires.replace(tzinfo=UTC)
                    if expires > datetime.now(UTC):
                        debuff_multiplier = Decimal("0.8")
                        debuff_alert = "\n⚠️ <b>Внимание:</b> В вашей пивоварне проходит Внеплановая проверка! Качество партии снижено на 20%.\n"

        # Рассчитаем модификатор качества варки
        quality_mod = Decimal("1.00") + Decimal(str(skill / 200)) - Decimal(str(fatigue / 500))
        quality_mod = quality_mod * debuff_multiplier
        quality_mod = max(Decimal("0.50"), min(Decimal("2.00"), quality_mod))

        # Создаем батч (партия созревает 2 минуты)
        ready_time = datetime.now(UTC) + timedelta(minutes=2)
        batch = Batch(
            player_id=cast(int, player.player_id),
            recipe_id=recipe.recipe_id,
            quantity_barrels=10,
            quality_modifier=quality_mod,
            is_completed=False,
            ready_at=ready_time
        )
        session.add(batch)
        await session.flush()

        # Пишем в лог событий игрока
        summary = f"Сварил серийную партию «{recipe.title}» (10 бочек)"
        await player_dal.log_player_event(
            player_id=cast(int, player.player_id),
            event_type="serial_brew",
            summary=summary,
            metadata={"recipe_id": recipe.recipe_id, "title": recipe.title}
        )

        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="🏺 В погреб", callback_data="screen:inventory"))
        builder.row(InlineKeyboardButton(text="🔙 В варочный зал", callback_data="screen:brewery_hall"))

        await callback.message.edit_text(
            f"🟢 <b>Партия запущена!</b>\n\n"
            f"Пиво: <b>«{html.quote(cast(str, recipe.title))}»</b> (10 бочек)\n"
            f"Качество партии: <code>{quality_mod:.2f}x</code>\n"
            f"{staff_info}\n"
            f"{debuff_alert}\n"
            f"⏳ Партия будет готова к сбору через 2 минуты.",
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )
        
        # Обновим HUD
        await update_hud(callback.bot, player, session)

    except PlayerNotFoundError:
        await callback.answer("Профиль не найден.", show_alert=True)
    await callback.answer()


@brewery_hall_router.callback_query(F.data == "brewery_hall:patent_bureau")
async def show_patent_bureau(callback: CallbackQuery, session: AsyncSession) -> None:
    """
    Экран Патентного бюро.
    """
    if not callback.from_user or not callback.message or not isinstance(callback.message, Message):
        await callback.answer()
        return

    tg_id = callback.from_user.id
    player_dal = PlayerDAL(session)

    try:
        player = await player_dal.get_player(tg_id)
        
        # Получаем все патенты игрока
        stmt_patents = select(Patent).where(Patent.player_id == cast(int, player.player_id))
        res_patents = await session.execute(stmt_patents)
        patents = res_patents.scalars().all()

        # Получаем рецепты игрока для проверки условий патентования
        stmt_recipes = select(Recipe).where(Recipe.creator_id == cast(int, player.player_id))
        res_recipes = await session.execute(stmt_recipes)
        recipes = res_recipes.scalars().all()

        text = (
            f"📜 <b>Патентное бюро гильдии пивоваров</b>\n\n"
            f"Здесь вы можете закрепить за собой права на рецепты с выдающимися характеристиками "
            f"(<b>Крепость ≥ 8%</b> и <b>Аромат ≥ 7</b>).\n"
            f"Патентование стоит <b>50 gold</b>. Срок действия патента — 7 дней.\n\n"
        )

        builder = InlineKeyboardBuilder()

        # Выведем список активных патентов
        if patents:
            text += "📋 <b>Ваши активные патенты:</b>\n"
            for p in patents:
                stmt_r = select(Recipe).where(Recipe.recipe_id == p.recipe_id)
                res_r = await session.execute(stmt_r)
                rec = res_r.scalar_one_or_none()
                title = p.lore_name or (rec.title if rec else "Неизвестный рецепт")
                status = "🟢 Активен" if p.is_active else "🔴 Истек"
                text += f"• <b>«{title}»</b> — {status} (до {p.expires_at.strftime('%d.%m %H:%M')})\n"
            text += "\n"

        # Проверим, какие рецепты доступны для патентования
        available_recipes = []
        for r in recipes:
            # Проверяем статы: сила >= 8, аромат >= 7
            if r.strength >= Decimal("8.00") and r.aroma >= Decimal("7.00"):
                # Проверим, нет ли уже активного патента на этот рецепт
                stmt_active_pat = select(Patent).where(
                    Patent.recipe_id == r.recipe_id, Patent.is_active.is_(True)
                )
                res_active_pat = await session.execute(stmt_active_pat)
                active_pat = res_active_pat.scalar_one_or_none()
                if not active_pat:
                    available_recipes.append(r)

        if available_recipes:
            text += "🔒 <b>Доступно для патентования:</b>\n"
            for r in available_recipes:
                text += f"• <b>«{r.title}»</b> (Креп: <code>{r.strength:.1f}%</code>, Аромат: <code>{r.aroma:.1f}</code>)\n"
                builder.row(
                    InlineKeyboardButton(
                        text=f"🔒 Патент «{r.title}» (50g)",
                        callback_data=f"brewery_hall:patent_register:{r.recipe_id}"
                    )
                )
        else:
            text += "🔒 <i>У вас нет рецептов, удовлетворяющих условиям патентования (Крепость ≥ 8% и Аромат ≥ 7).</i>\n"

        builder.row(
            InlineKeyboardButton(text="🔙 Назад в зал", callback_data="screen:brewery_hall")
        )

        await callback.message.edit_text(
            text, parse_mode="HTML", reply_markup=builder.as_markup()
        )
    except PlayerNotFoundError:
        await callback.answer("Профиль не найден.", show_alert=True)
    await callback.answer()


@brewery_hall_router.callback_query(F.data.startswith("brewery_hall:patent_register:"))
async def register_patent(callback: CallbackQuery, session: AsyncSession) -> None:
    """
    Списывает золото и создает патент, запуская фоновую генерацию.
    """
    if not callback.from_user or not callback.message or not isinstance(callback.message, Message) or not callback.data:
        await callback.answer()
        return

    recipe_id = int(callback.data.split(":")[2])
    tg_id = callback.from_user.id
    player_dal = PlayerDAL(session)

    try:
        player = await player_dal.get_player(tg_id)

        # Списываем 50 золота за патент
        try:
            await player_dal.change_gold(cast(int, player.player_id), Decimal("-50.00"))
        except InsufficientFundsError:
            await callback.answer("❌ Недостаточно золота для регистрации патента (нужно 50 gold)!", show_alert=True)
            return

        # Получаем рецепт
        stmt = select(Recipe).where(Recipe.recipe_id == recipe_id)
        res = await session.execute(stmt)
        recipe = res.scalar_one_or_none()

        if not recipe:
            await callback.answer("Рецепт не найден.", show_alert=True)
            return

        # Создаем патент на 7 дней
        expires = datetime.now(UTC) + timedelta(days=7)
        patent = Patent(
            player_id=cast(int, player.player_id),
            recipe_id=recipe.recipe_id,
            is_active=True,
            daily_tax_base=Decimal("50.00"),
            royalty_earned_24h=Decimal("0.00"),
            expires_at=expires
        )
        session.add(patent)
        await session.flush()
        
        patent_id = cast(int, patent.patent_id)

        # Запускаем фоновую генерацию
        asyncio.create_task(
            generate_patent_card_task(
                patent_id=patent_id,
                chat_id=callback.message.chat.id,
                bot=callback.bot
            )
        )

        await callback.answer("🔒 Регистрация патента запущена! Летописец гильдии пишет историю...", show_alert=True)
        
        # Перерисовываем экран
        await show_patent_bureau(callback, session)

    except PlayerNotFoundError:
        await callback.answer("Профиль не найден.", show_alert=True)
    await callback.answer()


async def generate_patent_card_task(patent_id: int, chat_id: int, bot: Bot | None) -> None:
    """
    Фоновый таск: генерация лора и картинки Imagen 3, отправка карточки.
    """
    if bot is None:
        return

    await asyncio.sleep(1)  # Слегка подождем коммита транзакции в хендлере
    
    async with async_session_factory() as session:
        try:
            player_dal = PlayerDAL(session)
            
            # Загрузим патент
            stmt = select(Patent).where(Patent.patent_id == patent_id)
            res = await session.execute(stmt)
            patent = res.scalar_one_or_none()
            
            if not patent:
                logger.error(f"Патент {patent_id} не найден в фоновой задаче.")
                return
                
            # Загрузим рецепт
            stmt_recipe = select(Recipe).where(Recipe.recipe_id == patent.recipe_id)
            res_recipe = await session.execute(stmt_recipe)
            recipe = res_recipe.scalar_one_or_none()
            
            if not recipe:
                logger.error(f"Рецепт для патента {patent_id} не найден.")
                return

            # Получаем историю игрока
            events = await player_dal.get_recent_events(cast(int, patent.player_id), limit=5)
            history_strings = [cast(str, e.summary) for e in events]

            # 1. Генерируем Лор через LLM
            lore_gen = LLMPatentLoreGenerator()
            recipe_stats = {
                "strength": float(cast(Decimal, recipe.strength)),
                "bitterness": float(cast(Decimal, recipe.bitterness)),
                "aroma": float(cast(Decimal, recipe.aroma)),
                "stability": cast(int, recipe.stability),
                "quality_modifier": 1.0
            }
            
            patent_lore = await lore_gen.generate_patent_lore(recipe_stats, history_strings, style="пиво")
            
            # Сохраняем лор в БД
            patent.lore_name = patent_lore.name
            patent.lore_text = patent_lore.lore
            
            # 2. Генерируем Картинку через Imagen 3
            image_prompt = (
                f"Fantasy cartoon Hearthstone card style illustration, "
                f"showing a premium magical potion of beer called '{patent_lore.name}'. "
                f"Vibrant colors, game art design, golden frame, epic lighting."
            )
            
            image_bytes = await generate_patent_image(image_prompt)
            
            # Формируем итоговое сообщение
            caption = (
                f"🎉 <b>НОВЫЙ ПАТЕНТ ЗАРЕГИСТРИРОВАН!</b>\n\n"
                f"📜 <b>«{html.quote(patent_lore.name)}»</b>\n"
                f"<code>┌────────────────────────────</code>\n"
                f"💪 Крепость: <code>{recipe.strength:.1f}%</code>\n"
                f"👅 Горечь: <code>{recipe.bitterness:.1f} IBU</code>\n"
                f"👃 Аромат: <code>{recipe.aroma:.1f}</code>\n"
                f"🛡️ Стабильность: <code>{recipe.stability}%</code>\n"
                f"<code>└────────────────────────────</code>\n\n"
                f"<i>{html.quote(patent_lore.lore)}</i>"
            )
            
            # Отправляем
            if image_bytes:
                try:
                    photo_file = BufferedInputFile(image_bytes, filename=f"patent_{patent_id}.jpg")
                    msg = await bot.send_photo(
                        chat_id=chat_id,
                        photo=photo_file,
                        caption=caption,
                        parse_mode="HTML"
                    )
                    # Кэшируем telegram file_id
                    if msg.photo:
                        patent.card_image_file_id = msg.photo[-1].file_id
                except Exception as e:
                    logger.error(f"Не удалось отправить сгенерированное фото: {e}")
                    await bot.send_message(chat_id=chat_id, text=caption, parse_mode="HTML")
            else:
                await bot.send_message(chat_id=chat_id, text=caption, parse_mode="HTML")
                
            # Пишем событие в лог событий игрока
            summary = f"Зарегистрировал патент на сорт «{patent_lore.name}»"
            await player_dal.log_player_event(
                player_id=cast(int, patent.player_id),
                event_type="patent_registered",
                summary=summary,
                metadata={"patent_id": patent_id, "name": patent_lore.name}
            )
            
            await session.commit()
            
            # Обновим HUD
            player = await player_dal.get_player_by_id(cast(int, patent.player_id))
            await update_hud(bot, player, session)

        except Exception as e:
            logger.error(f"Критическая ошибка в фоновой задаче патентования: {e}", exc_info=True)
            await session.rollback()
