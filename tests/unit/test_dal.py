import pytest
from unittest.mock import AsyncMock, MagicMock
from decimal import Decimal

from src.database.dal import (
    PlayerDAL,
    CraftingDAL,
    QueueDAL,
    EconomyDAL,
    InsufficientFundsError,
    PlayerNotFoundError,
    TaskNotFoundError,
)
from src.database.models import Player, Recipe, Task, Patent, TransactionLog



@pytest.mark.asyncio
async def test_player_dal_get_player_success():
    session = AsyncMock()
    mock_player = Player(player_id=1, gold=Decimal("100.00"))
    
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_player
    session.execute.return_value = mock_result
    
    player = await PlayerDAL.get_player(session, 1)
    assert player == mock_player
    assert player.player_id == 1


@pytest.mark.asyncio
async def test_player_dal_get_player_not_found():
    session = AsyncMock()
    
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    session.execute.return_value = mock_result
    
    with pytest.raises(PlayerNotFoundError):
        await PlayerDAL.get_player(session, 1)


@pytest.mark.asyncio
async def test_player_dal_change_gold_success():
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.rowcount = 1
    session.execute.return_value = mock_result
    
    await PlayerDAL.change_gold(session, 1, 50.0)
    await PlayerDAL.change_gold(session, 1, -20.0)


@pytest.mark.asyncio
async def test_player_dal_change_gold_insufficient_funds():
    session = AsyncMock()
    
    mock_update_result = MagicMock()
    mock_update_result.rowcount = 0
    
    mock_check_result = MagicMock()
    mock_check_result.scalar_one_or_none.return_value = Decimal("10.00")
    
    session.execute.side_effect = [mock_update_result, mock_check_result]
    
    with pytest.raises(InsufficientFundsError):
        await PlayerDAL.change_gold(session, 1, -50.0)


@pytest.mark.asyncio
async def test_player_dal_change_gold_player_not_found():
    session = AsyncMock()
    
    mock_update_result = MagicMock()
    mock_update_result.rowcount = 0
    
    mock_check_result = MagicMock()
    mock_check_result.scalar_one_or_none.return_value = None
    
    session.execute.side_effect = [mock_update_result, mock_check_result]
    
    with pytest.raises(PlayerNotFoundError):
        await PlayerDAL.change_gold(session, 1, -50.0)


@pytest.mark.asyncio
async def test_crafting_dal_create_recipe():
    session = AsyncMock()
    session.add = MagicMock()
    
    recipe = await CraftingDAL.create_recipe(
        session=session,
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
        session=session,
        task_type="bot_dispatch",
        payload={"foo": "bar"},
        target_tg_id=12345
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
    mock_result.all.return_value = [
        (1, Decimal("100.50")),
        (2, Decimal("200.00"))
    ]
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
    mock_result.all.return_value = [
        (10, 100, Decimal("50.00")),
        (11, 101, Decimal("0.00"))
    ]
    session.execute.return_value = mock_result

    res = await EconomyDAL.get_active_patents_for_recipes(session, [1, 2])
    assert len(res) == 2
    assert res[0] == {"patent_id": 10, "player_id": 100, "royalty_earned_24h": 50.0}
    assert res[1] == {"patent_id": 11, "player_id": 101, "royalty_earned_24h": 0.0}

