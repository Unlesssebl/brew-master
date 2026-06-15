from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """
    Базовый класс для всех моделей базы данных Beer Empire.
    Служит точкой входа для миграций Alembic.
    """

    pass
