from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """
    Базовый класс для всех моделей базы данных Beer Empire.
    Служит точкой входа для миграций Alembic.
    """

    pass


from .core_models import *  # noqa: F403, E402
from .crafting_models import *  # noqa: F403, E402
from .economy_models import *  # noqa: F403, E402
from .queue_models import *  # noqa: F403, E402

__all__ = ["Base"]


