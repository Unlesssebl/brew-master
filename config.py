from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.core.config import GameBalance as GameBalanceModel


class Settings(BaseSettings):
    """
    Централизованные настройки приложения Beer Empire.
    Загружаются из переменных окружения или .env файла.
    """

    BOT_TOKEN: str
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@db:5432/beer_empire"
    LLM_API_KEY: str | None = None
    GEMINI_API_KEY: str | None = None
    LOG_LEVEL: str = "INFO"
    GameBalance: GameBalanceModel = GameBalanceModel()

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="before")
    @classmethod
    def populate_llm_api_key(cls, data: dict) -> dict:
        # Если в данных/окружении есть GEMINI_API_KEY, используем его как fallback для LLM_API_KEY
        if isinstance(data, dict):
            if not data.get("LLM_API_KEY"):
                import os

                gemini_key = data.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")
                if gemini_key:
                    data["LLM_API_KEY"] = gemini_key
        return data


# Глобальный экземпляр настроек
settings = Settings()
