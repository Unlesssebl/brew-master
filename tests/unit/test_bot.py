from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.types import Message, User

from src.bot.handlers.basic import cmd_profile, cmd_start
from src.bot.handlers.craft import cmd_brew
from src.database.dal import PlayerNotFoundError
from src.database.models import Player, Staff, StaffRole, TavernTier


@pytest.mark.asyncio
async def test_cmd_start_existing_user() -> None:
    message = AsyncMock(spec=Message)
    message.from_user = MagicMock(spec=User)
    message.from_user.id = 12345
    message.from_user.full_name = "Test User"
    message.answer = AsyncMock()

    session = AsyncMock()
    mock_player = Player(
        player_id=1,
        tg_id=12345,
        gold=Decimal("1000.00"),
        tutorial_step=3,
        reputation=0,
        influence=0,
        tavern_level=TavernTier.garage,
    )

    with patch("src.bot.handlers.basic.PlayerDAL") as mock_dal_class:
        mock_dal_instance = mock_dal_class.return_value
        mock_dal_instance.get_player = AsyncMock(return_value=mock_player)

        await cmd_start(message, session)

        mock_dal_class.assert_called_once_with(session)
        mock_dal_instance.get_player.assert_called_once_with(12345)
        message.answer.assert_called_once()
        assert "С возвращением на завод" in message.answer.call_args[0][0]


@pytest.mark.asyncio
async def test_cmd_start_new_user() -> None:
    message = AsyncMock(spec=Message)
    message.from_user = MagicMock(spec=User)
    message.from_user.id = 12345
    message.from_user.full_name = "Test User"
    message.answer = AsyncMock()

    session = AsyncMock()
    mock_player = Player(player_id=1, tg_id=12345, gold=Decimal("1000.00"), tutorial_step=0)

    with patch("src.bot.handlers.basic.PlayerDAL") as mock_dal_class:
        mock_dal_instance = mock_dal_class.return_value
        mock_dal_instance.get_player = AsyncMock(side_effect=PlayerNotFoundError())
        mock_dal_instance.create_player = AsyncMock(return_value=mock_player)

        await cmd_start(message, session)

        mock_dal_class.assert_called_once_with(session)
        mock_dal_instance.get_player.assert_called_once_with(12345)
        mock_dal_instance.create_player.assert_called_once_with(12345)
        message.answer.assert_called_once()
        assert "дедовский гараж" in message.answer.call_args[0][0]


@pytest.mark.asyncio
async def test_cmd_profile() -> None:
    message = AsyncMock(spec=Message)
    message.from_user = MagicMock(spec=User)
    message.from_user.id = 12345
    message.answer = AsyncMock()

    session = AsyncMock()
    mock_player = Player(
        player_id=1,
        tg_id=12345,
        gold=Decimal("1200.50"),
        reputation=10,
        influence=5,
        tavern_level=TavernTier.garage,
    )

    with patch("src.bot.handlers.basic.PlayerDAL") as mock_dal_class:
        mock_dal_instance = mock_dal_class.return_value
        mock_dal_instance.get_player = AsyncMock(return_value=mock_player)

        await cmd_profile(message, session)

        mock_dal_instance.get_player.assert_called_once_with(12345)
        message.answer.assert_called_once()
        ans = message.answer.call_args[0][0]
        assert "1200.50" in ans
        assert "10" in ans
        assert "Garage" in ans


@pytest.mark.asyncio
async def test_cmd_brew_validation_failed() -> None:
    message = AsyncMock(spec=Message)
    message.from_user = MagicMock(spec=User)
    message.text = "/brew 10 20 30"
    message.answer = AsyncMock()

    session = AsyncMock()

    await cmd_brew(message, session)
    message.answer.assert_called_once()
    assert "Неверное количество аргументов" in message.answer.call_args[0][0]


@pytest.mark.asyncio
async def test_cmd_brew_success() -> None:
    message = AsyncMock(spec=Message)
    message.from_user = MagicMock(spec=User)
    message.from_user.id = 12345
    message.text = "/brew 50 30 10 10"
    message.answer = AsyncMock()

    session = AsyncMock()
    mock_player = Player(player_id=1, tg_id=12345)
    mock_staff = Staff(name="Alchemist", role=StaffRole.master_alchemist, skill=80, fatigue=10)

    mock_recipe = MagicMock()
    mock_recipe.title = "Экспериментальная варка"
    mock_recipe.malt_pct = 50
    mock_recipe.water_pct = 30
    mock_recipe.hop_pct = 10
    mock_recipe.yeast_pct = 10
    mock_recipe.strength = Decimal("5.5")
    mock_recipe.bitterness = Decimal("15.0")
    mock_recipe.aroma = Decimal("8.0")
    mock_recipe.stability = 90

    with (
        patch("src.bot.handlers.craft.PlayerDAL") as mock_player_dal_class,
        patch("src.bot.handlers.craft.CraftingDAL") as mock_crafting_dal_class,
    ):
        mock_p_dal = mock_player_dal_class.return_value
        mock_p_dal.get_player = AsyncMock(return_value=mock_player)
        mock_p_dal.get_active_staff = AsyncMock(return_value=mock_staff)

        mock_c_dal = mock_crafting_dal_class.return_value
        mock_c_dal.create_recipe = AsyncMock(return_value=mock_recipe)

        await cmd_brew(message, session)

        mock_p_dal.get_player.assert_called_once_with(12345)
        mock_p_dal.get_active_staff.assert_called_once_with(1, "master_alchemist")
        mock_c_dal.create_recipe.assert_called_once_with(
            1, 50, 30, 10, 10, 80, 10, title="Экспериментальная варка"
        )
        message.answer.assert_called_once()
        ans = message.answer.call_args[0][0]
        assert "Успешная варка" in ans
        assert "5.50%" in ans
        assert "15.00 IBU" in ans
        assert "90/100" in ans
