from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.database.dal import (
    CraftingDAL,
    EconomyDAL,
    InsufficientFundsError,
    PlayerDAL,
    PlayerNotFoundError,
    QueueDAL,
    TaskNotFoundError,
)
from src.database.models import Player, Recipe, Task, TavernTier, Resource, Staff


@pytest.mark.asyncio
async def test_player_dal_get_player_by_id_success():
    session = AsyncMock()
    mock_player = Player(player_id=1, gold=Decimal("100.00"))

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_player
    session.execute.return_value = mock_result

    player = await PlayerDAL(session).get_player_by_id(1)
    assert player == mock_player
    assert player.player_id == 1


@pytest.mark.asyncio
async def test_player_dal_get_player_by_tg_id_success():
    session = AsyncMock()
    mock_player = Player(player_id=1, tg_id=12345, gold=Decimal("100.00"))

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_player
    session.execute.return_value = mock_result

    player = await PlayerDAL(session).get_player_by_tg_id(12345)
    assert player == mock_player
    assert player.tg_id == 12345


@pytest.mark.asyncio
async def test_player_dal_get_player_not_found():
    session = AsyncMock()

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    session.execute.return_value = mock_result

    with pytest.raises(PlayerNotFoundError):
        await PlayerDAL(session).get_player_by_id(1)


@pytest.mark.asyncio
async def test_player_dal_change_gold_success():
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.rowcount = 1
    session.execute.return_value = mock_result

    dal = PlayerDAL(session)
    await dal.change_gold(1, 50.0)
    await dal.change_gold(1, -20.0)


@pytest.mark.asyncio
async def test_player_dal_change_gold_insufficient_funds():
    session = AsyncMock()

    mock_update_result = MagicMock()
    mock_update_result.rowcount = 0

    mock_check_result = MagicMock()
    mock_check_result.scalar_one_or_none.return_value = Decimal("10.00")

    session.execute.side_effect = [mock_update_result, mock_check_result]

    with pytest.raises(InsufficientFundsError):
        await PlayerDAL(session).change_gold(1, -50.0)


@pytest.mark.asyncio
async def test_player_dal_change_gold_player_not_found():
    session = AsyncMock()

    mock_update_result = MagicMock()
    mock_update_result.rowcount = 0

    mock_check_result = MagicMock()
    mock_check_result.scalar_one_or_none.return_value = None

    session.execute.side_effect = [mock_update_result, mock_check_result]

    with pytest.raises(PlayerNotFoundError):
        await PlayerDAL(session).change_gold(1, -50.0)


@pytest.mark.asyncio
async def test_crafting_dal_create_recipe():
    session = AsyncMock()
    session.add = MagicMock()

    recipe = await CraftingDAL(session).create_recipe(
        player_id=1,
        m=50,
        w=30,
        h=10,
        y=10,
        skill=50,
        fatigue=0,
        title="Тестовое Пиво",
    )

    assert isinstance(recipe, Recipe)
    assert recipe.creator_id == 1
    assert recipe.title == "Тестовое Пиво"
    assert recipe.malt_pct == 50
    assert recipe.water_pct == 30
    assert recipe.hop_pct == 10
    assert recipe.yeast_pct == 10
    assert recipe.strength > 0
    assert recipe.bitterness > 0
    assert recipe.aroma > 0
    assert recipe.stability > 0

    session.add.assert_called_once_with(recipe)
    session.flush.assert_called_once()


@pytest.mark.asyncio
async def test_queue_dal_fetch_next_task_found():
    session = AsyncMock()
    mock_task = Task(task_id=10, status="pending")

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_task
    session.execute.return_value = mock_result

    task = await QueueDAL.fetch_next_task(session)
    assert task == mock_task


@pytest.mark.asyncio
async def test_queue_dal_fetch_next_task_not_found():
    session = AsyncMock()

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    session.execute.return_value = mock_result

    task = await QueueDAL.fetch_next_task(session)
    assert task is None


@pytest.mark.asyncio
async def test_queue_dal_complete_task_success():
    session = AsyncMock()

    mock_result = MagicMock()
    mock_result.rowcount = 1
    session.execute.return_value = mock_result

    await QueueDAL.complete_task(session, 10, success=True)
    await QueueDAL.complete_task(session, 10, success=False)


@pytest.mark.asyncio
async def test_queue_dal_complete_task_not_found():
    session = AsyncMock()

    mock_result = MagicMock()
    mock_result.rowcount = 0
    session.execute.return_value = mock_result

    with pytest.raises(TaskNotFoundError):
        await QueueDAL.complete_task(session, 10, success=True)


@pytest.mark.asyncio
async def test_queue_dal_create_task():
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()

    task = await QueueDAL.create_task(
        session=session, task_type="bot_dispatch", payload={"foo": "bar"}, target_tg_id=12345
    )

    assert isinstance(task, Task)
    assert task.task_type == "bot_dispatch"
    assert task.payload == {"foo": "bar", "tg_id": 12345}
    session.add.assert_called_once_with(task)
    session.flush.assert_called_once()


@pytest.mark.asyncio
async def test_economy_dal_get_unprocessed_royalties():
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.all.return_value = [(1, Decimal("100.50")), (2, Decimal("200.00"))]
    session.execute.return_value = mock_result

    res = await EconomyDAL.get_unprocessed_royalties(session)
    assert len(res) == 2
    assert res[0] == {"recipe_id": 1, "total_revenue": 100.50}
    assert res[1] == {"recipe_id": 2, "total_revenue": 200.0}


@pytest.mark.asyncio
async def test_economy_dal_mark_transactions_processed():
    session = AsyncMock()
    await EconomyDAL.mark_transactions_processed(session, [1, 2])
    session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_economy_dal_get_active_patents_for_recipes():
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.all.return_value = [(10, 100, Decimal("50.00")), (11, 101, Decimal("0.00"))]
    session.execute.return_value = mock_result

    res = await EconomyDAL.get_active_patents_for_recipes(session, [1, 2])
    assert len(res) == 2
    assert res[0] == {"patent_id": 10, "player_id": 100, "royalty_earned_24h": 50.0}
    assert res[1] == {"patent_id": 11, "player_id": 101, "royalty_earned_24h": 0.0}


@pytest.mark.asyncio
async def test_player_dal_upgrade_tavern_level_success():
    session = AsyncMock()
    mock_player = Player(player_id=1, tavern_level=TavernTier.garage, gold=Decimal("1000.00"))

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_player
    session.execute.return_value = mock_result

    dal = PlayerDAL(session)
    next_tier = await dal.upgrade_tavern_level(1)
    assert next_tier == TavernTier.tavern


@pytest.mark.asyncio
async def test_player_dal_update_player_stats():
    session = AsyncMock()
    mock_player = Player(player_id=1, gold=Decimal("100.00"), reputation=10, influence=5)

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_player
    session.execute.return_value = mock_result

    dal = PlayerDAL(session)
    await dal.update_player_stats(1, gold_change=50, reputation_change=10, influence_change=-2)
    session.execute.assert_called()


@pytest.mark.asyncio
async def test_player_dal_create_staff():
    session = AsyncMock()
    dal = PlayerDAL(session)
    staff = await dal.create_staff(1, "Olaf", "master_alchemist", 45)
    assert isinstance(staff, Staff)
    assert staff.name == "Olaf"
    assert staff.role == "master_alchemist"
    assert staff.skill == 45
    session.add.assert_called_once_with(staff)
    session.flush.assert_called_once()


@pytest.mark.asyncio
async def test_player_dal_get_resources():
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    session.execute.return_value = mock_result

    dal = PlayerDAL(session)
    res = await dal.get_resources(1)
    assert "malt" in res
    assert "water" in res
    assert res["malt"] == Decimal("0.00")
