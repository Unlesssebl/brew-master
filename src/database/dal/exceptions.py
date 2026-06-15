class DALError(Exception):
    """Базовый класс исключений для слоя DAL."""
    pass


class InsufficientFundsError(DALError):
    """Исключение, выбрасываемое при нехватке средств (золота) у игрока."""
    pass


class PlayerNotFoundError(DALError):
    """Исключение, выбрасываемое, если игрок не найден в базе данных."""
    pass


class RecipeNotFoundError(DALError):
    """Исключение, выбрасываемое, если рецепт не найден в базе данных."""
    pass


class TaskNotFoundError(DALError):
    """Исключение, выбрасываемое, если задача не найдена в базе данных."""
    pass
