from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import Task
from .exceptions import TaskNotFoundError


class QueueDAL:
    """
    Data Access Layer (DAL) для работы с очередью задач.
    """

    @staticmethod
    async def fetch_next_task(session: AsyncSession) -> Task | None:
        """
        Атомарно захватывает следующую задачу в обработку (Queue Worker Pattern).
        
        Использует FOR UPDATE SKIP LOCKED для предотвращения конкурентного захвата 
        одной и той же задачи несколькими воркерами.
        """
        subq = (
            select(Task.task_id)
            .where(Task.status == "pending")
            .order_by(Task.created_at.asc())
            .limit(1)
            .with_for_update(skip_locked=True)
            .scalar_subquery()
        )

        stmt = (
            update(Task)
            .where(Task.task_id == subq)
            .values(status="processing", picked_at=func.now())
            .returning(Task)
        )

        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def complete_task(session: AsyncSession, task_id: int, success: bool) -> None:
        """
        Помечает задачу как завершенную (completed) или проваленную (failed)
        и обновляет таймстемп processed_at.
        """
        status = "completed" if success else "failed"

        stmt = (
            update(Task)
            .where(Task.task_id == task_id)
            .values(status=status, processed_at=func.now())
        )
        result = await session.execute(stmt)

        if result.rowcount == 0:
            raise TaskNotFoundError(f"Task with ID {task_id} not found.")

    @staticmethod
    async def create_task(
        session: AsyncSession,
        task_type: str,
        payload: dict,
        target_tg_id: int | None = None,
    ) -> Task:
        """
        Создает новую задачу в очереди.
        """
        actual_payload = payload.copy()
        if target_tg_id is not None:
            actual_payload["tg_id"] = target_tg_id

        task = Task(
            task_type=task_type,
            payload=actual_payload,
            status="pending",
        )
        session.add(task)
        await session.flush()
        return task

