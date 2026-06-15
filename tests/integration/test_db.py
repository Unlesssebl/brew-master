import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from src.database.connection import engine
from src.database.models import Base


@pytest.mark.asyncio
async def test_db_engine():
    """
    Проверяет корректность инициализации SQLAlchemy движка и доступность метаданных моделей.
    """
    assert isinstance(engine, AsyncEngine)
    assert Base.metadata is not None
