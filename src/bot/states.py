from aiogram.fsm.state import State, StatesGroup


class BrewingStates(StatesGroup):
    """
    Состояния процесса варки пива.
    """
    choosing_ingredients = State()  # Интерактивное изменение через inline-клавиатуру
    choosing_malt = State()
    choosing_water = State()
    choosing_hops = State()
    choosing_yeast = State()


class TutorialStates(StatesGroup):
    """
    Состояния обучения игрока.
    """
    first_brew = State()
    first_collect = State()
    first_sell = State()


class ExpeditionStates(StatesGroup):
    """
    Состояния рогалик-экспедиций.
    """
    awaiting_choice = State()


class StaffStates(StatesGroup):
    """
    Состояния управления персоналом.
    """
    managing = State()


class PatentStates(StatesGroup):
    viewing_bureau = State()
    naming_patent = State()


class MarketStates(StatesGroup):
    viewing_market = State()
    buying_ingredients = State()
    selling_barrels = State()


class PvPStates(StatesGroup):
    viewing_slums = State()
    targeting = State()
