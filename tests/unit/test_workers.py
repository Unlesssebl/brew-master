import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.database.dal import EconomyDAL, QueueDAL
from src.database.models import Task
from src.llm_engine.schemas import EventChoice, GameEvent
from src.workers.queue_worker import run_queue_worker
from src.workers.royalty import run_royalty_worker


@pytest.mark.asyncio
async def test_queue_worker_success():
    session_maker = MagicMock()
    session = AsyncMock()
    session.__aenter__.return_value = session
    session_maker.return_value = session

    # Имитируем задачу llm_event
    mock_task = Task(task_id=1, task_type="llm_event", payload={"tg_id": 12345})

    QueueDAL.fetch_next_task = AsyncMock(side_effect=[mock_task, None])
    QueueDAL.create_task = AsyncMock()
    QueueDAL.complete_task = AsyncMock()

    llm_generator = AsyncMock()
    mock_event = GameEvent(
        event_title="Test Event",
        event_description="Test Description",
        choices=[
            EventChoice(
                choice_id="choice_1",
                button_text="Button",
                result_text="Result",
                gold_change=-10,
                reputation_change=5,
                influence_change=0,
            )
        ],
    )
    llm_generator.generate_event.return_value = mock_event

    original_sleep = asyncio.sleep

    async def mock_sleep(delay):
        if delay == 5:  # Это значит, что задача не найдена
            raise asyncio.CancelledError()
        await original_sleep(delay)

    asyncio.sleep = mock_sleep

    try:
        mock_bot = AsyncMock()
        await run_queue_worker(session_maker, llm_generator, mock_bot)
    except asyncio.CancelledError:
        pass
    finally:
        asyncio.sleep = original_sleep

    QueueDAL.fetch_next_task.assert_called()
    llm_generator.generate_event.assert_called_once_with({"tg_id": 12345})
    QueueDAL.create_task.assert_called_once()
    QueueDAL.complete_task.assert_called_with(session, 1, success=True)


@pytest.mark.asyncio
async def test_royalty_worker_iteration():
    session_maker = MagicMock()
    session = AsyncMock()
    session.__aenter__.return_value = session
    session.begin = MagicMock()
    session.begin.return_value = AsyncMock()
    session_maker.return_value = session

    EconomyDAL.get_unprocessed_royalties = AsyncMock(
        return_value=[{"recipe_id": 1, "total_revenue": 1000.0}]
    )
    EconomyDAL.get_active_patents_for_recipes = AsyncMock(
        return_value=[{"patent_id": 10, "player_id": 100, "royalty_earned_24h": 100.0}]
    )
    EconomyDAL.mark_transactions_processed = AsyncMock()

    original_sleep = asyncio.sleep

    async def mock_sleep(delay):
        raise asyncio.CancelledError()

    asyncio.sleep = mock_sleep

    with patch("src.workers.royalty.PlayerDAL") as mock_player_dal_class:
        mock_p_dal = mock_player_dal_class.return_value
        mock_p_dal.change_gold = AsyncMock()

        try:
            await run_royalty_worker(session_maker)
        except asyncio.CancelledError:
            pass
        finally:
            asyncio.sleep = original_sleep

        mock_player_dal_class.assert_called_once_with(session)
        # Ожидаемый налог: 50 + 100 * 0.15 = 65
        mock_p_dal.change_gold.assert_any_call(100, -65.0)
        # Ожидаемый роялти: 1000 * 0.05 = 50
        mock_p_dal.change_gold.assert_any_call(100, 50.0)

    EconomyDAL.get_unprocessed_royalties.assert_called_once()
    EconomyDAL.mark_transactions_processed.assert_called_once_with(session, [1])
